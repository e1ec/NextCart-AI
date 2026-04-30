"""
Glue ETL Job — Products Silver Transform
Joins products + aisles + departments into a denormalised product table.
Reads from S3 bronze/products, writes to S3 silver/products.

Glue job arguments:
  --lake_bucket   S3 bucket name
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, ShortType, StringType

args = getResolvedOptions(sys.argv, ["JOB_NAME", "lake_bucket"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

LAKE_BUCKET = args["lake_bucket"]
BRONZE = f"s3://{LAKE_BUCKET}/bronze/products"
SILVER = f"s3://{LAKE_BUCKET}/silver/products"

# ── Read bronze tables ───────────────────────────────────────
products_df     = spark.read.parquet(f"{BRONZE}/products/")
aisles_df       = spark.read.parquet(f"{BRONZE}/aisles/")
departments_df  = spark.read.parquet(f"{BRONZE}/departments/")

print(
    f"Bronze counts: products={products_df.count():,}  "
    f"aisles={aisles_df.count():,}  depts={departments_df.count():,}"
)

# ── Cast types ───────────────────────────────────────────────
products_df = (
    products_df
    .withColumn("product_id",    F.col("product_id").cast(IntegerType()))
    .withColumn("product_name",  F.col("product_name").cast(StringType()))
    .withColumn("aisle_id",      F.col("aisle_id").cast(ShortType()))
    .withColumn("department_id", F.col("department_id").cast(ShortType()))
)

aisles_df = (
    aisles_df
    .withColumn("aisle_id", F.col("aisle_id").cast(ShortType()))
    .withColumn("aisle",    F.trim(F.lower(F.col("aisle"))))
)

departments_df = (
    departments_df
    .withColumn("department_id", F.col("department_id").cast(ShortType()))
    .withColumn("department",    F.trim(F.lower(F.col("department"))))
)

# ── Drop nulls and duplicates ────────────────────────────────
products_df = (
    products_df
    .filter(F.col("product_id").isNotNull() & F.col("product_name").isNotNull())
    .dropDuplicates(["product_id"])
)

# ── Normalise product name ───────────────────────────────────
products_df = products_df.withColumn(
    "product_name_clean",
    F.trim(F.regexp_replace(F.lower(F.col("product_name")), r"\s+", " "))
)

# ── Join into denormalised table ─────────────────────────────
enriched_df = (
    products_df
    .join(aisles_df.select("aisle_id", "aisle"), on="aisle_id", how="left")
    .join(departments_df.select("department_id", "department"), on="department_id", how="left")
    .withColumn("_silver_ts", F.current_timestamp())
)

final_count = enriched_df.count()
print(f"Silver products: {final_count:,} rows")

# ── Validate join coverage ───────────────────────────────────
null_aisle = enriched_df.filter(F.col("aisle").isNull()).count()
null_dept  = enriched_df.filter(F.col("department").isNull()).count()
if null_aisle > 0:
    print(f"WARNING: {null_aisle} products with no matching aisle")
if null_dept > 0:
    print(f"WARNING: {null_dept} products with no matching department")

# ── Write silver ─────────────────────────────────────────────
(
    enriched_df
    .write
    .mode("overwrite")
    .partitionBy("department_id")
    .parquet(f"{SILVER}/")
)

print(f"Products silver written to {SILVER}/")

job.commit()
print("Products silver job complete")
