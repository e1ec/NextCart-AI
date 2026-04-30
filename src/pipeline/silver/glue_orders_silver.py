"""
Glue ETL Job — Orders Silver Transform
Reads bronze Parquet, validates, cleans, and writes to silver zone.

Glue job arguments:
  --lake_bucket   S3 bucket name
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import FloatType, IntegerType, ShortType, StringType

args = getResolvedOptions(sys.argv, ["JOB_NAME", "lake_bucket"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

LAKE_BUCKET = args["lake_bucket"]
BRONZE_PREFIX = f"s3://{LAKE_BUCKET}/bronze/orders"
SILVER_PREFIX = f"s3://{LAKE_BUCKET}/silver/orders"


def transform_orders(df):
    initial_count = df.count()

    df = (
        df
        # Cast to correct types
        .withColumn("order_id",              F.col("order_id").cast(IntegerType()))
        .withColumn("user_id",               F.col("user_id").cast(IntegerType()))
        .withColumn("eval_set",              F.col("eval_set").cast(StringType()))
        .withColumn("order_number",          F.col("order_number").cast(IntegerType()))
        .withColumn("order_dow",             F.col("order_dow").cast(ShortType()))
        .withColumn("order_hour_of_day",     F.col("order_hour_of_day").cast(ShortType()))
        .withColumn("days_since_prior_order", F.col("days_since_prior_order").cast(FloatType()))
        # Drop mandatory-null rows
        .filter(F.col("order_id").isNotNull() & F.col("user_id").isNotNull())
        # Deduplicate
        .dropDuplicates(["order_id"])
        # Validate domain
        .filter(F.col("order_dow").between(0, 6))
        .filter(F.col("order_hour_of_day").between(0, 23))
        # Add audit column
        .withColumn("_silver_ts", F.current_timestamp())
    )

    final_count = df.count()
    dropped = initial_count - final_count
    print(f"orders: {initial_count:,} → {final_count:,} rows ({dropped:,} dropped by DQ)")
    return df


def transform_order_products(df, table_name: str):
    initial_count = df.count()

    df = (
        df
        .withColumn("order_id",          F.col("order_id").cast(IntegerType()))
        .withColumn("product_id",        F.col("product_id").cast(IntegerType()))
        .withColumn("add_to_cart_order", F.col("add_to_cart_order").cast(ShortType()))
        .withColumn("reordered",         F.col("reordered").cast(ShortType()))
        .filter(F.col("order_id").isNotNull() & F.col("product_id").isNotNull())
        .filter(F.col("reordered").isin(0, 1))
        .filter(F.col("add_to_cart_order") >= 1)
        .dropDuplicates(["order_id", "product_id"])
        .withColumn("_silver_ts", F.current_timestamp())
    )

    final_count = df.count()
    print(f"{table_name}: {initial_count:,} → {final_count:,} rows")
    return df


# ── Process each table ───────────────────────────────────────
for table, transform_fn, partition_cols in [
    ("orders",                lambda df: transform_orders(df),                      ["eval_set"]),
    ("order_products_prior",  lambda df: transform_order_products(df, "order_products_prior"), []),
    ("order_products_train",  lambda df: transform_order_products(df, "order_products_train"), []),
]:
    print(f"\nProcessing {table}...")

    bronze_df = spark.read.parquet(f"{BRONZE_PREFIX}/{table}/")
    silver_df = transform_fn(bronze_df)

    # Write quarantine records before filtering (rows with null mandatory keys)
    quarantine_df = bronze_df.filter(
        F.col("order_id").isNull()
        | F.col("user_id" if table == "orders" else "product_id").isNull()
    )
    if quarantine_df.count() > 0:
        (
            quarantine_df
            .withColumn("_rejection_reason", F.lit(f"null_mandatory_key in {table}"))
            .withColumn("_quarantine_ts", F.current_timestamp())
            .write.mode("append")
            .parquet(f"s3://{LAKE_BUCKET}/quarantine/orders/{table}/")
        )
        print(f"  {table}: {quarantine_df.count()} rows quarantined")

    writer = silver_df.write.mode("overwrite").format("parquet")
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.save(f"{SILVER_PREFIX}/{table}/")

    print(f"  {table}: written to {SILVER_PREFIX}/{table}/")

job.commit()
print("\nOrders silver job complete")
