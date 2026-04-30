"""
Glue ETL Job — Source 1 Bronze
Reads orders tables from RDS PostgreSQL via JDBC and writes Parquet to S3 bronze zone.

Glue job arguments:
  --lake_bucket       S3 bucket name (nextcart-dev-lake)
  --orders_connection Glue JDBC connection name
"""

import json
import sys
from datetime import datetime

import boto3
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, ["JOB_NAME", "lake_bucket", "orders_secret_arn"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

LAKE_BUCKET = args["lake_bucket"]
RUN_DATE = datetime.utcnow().strftime("%Y/%m/%d")

# Fetch credentials from Secrets Manager at runtime
_secret = json.loads(
    boto3.client("secretsmanager").get_secret_value(
        SecretId=args["orders_secret_arn"]
    )["SecretString"]
)
JDBC_URL  = f"jdbc:postgresql://{_secret['host']}:5432/{_secret['dbname']}"
JDBC_PROPS = {
    "user":     _secret["username"],
    "password": _secret["password"],
    "driver":   "org.postgresql.Driver",
    "sslmode":  "require",
}

# (table, partition_col, num_partitions, upper_bound)
TABLES = [
    ("orders",               "order_id", 4,  3_500_000),
    ("order_products_prior", "order_id", 16, 3_500_000),
    ("order_products_train", "order_id", 4,  3_500_000),
]

for table, part_col, num_parts, upper in TABLES:
    print(f"Extracting {table}...")

    df = spark.read.jdbc(
        url=JDBC_URL,
        table=table,
        column=part_col,
        lowerBound=1,
        upperBound=upper,
        numPartitions=num_parts,
        properties=JDBC_PROPS,
    )
    dyf = DynamicFrame.fromDF(df, glueContext, f"source_{table}")

    row_count = dyf.count()
    print(f"  {table}: {row_count:,} rows extracted")

    glueContext.write_dynamic_frame.from_options(
        frame=dyf,
        connection_type="s3",
        connection_options={
            "path": f"s3://{LAKE_BUCKET}/bronze/orders/{table}/run_date={RUN_DATE}/",
            "partitionKeys": [],
        },
        format="parquet",
        format_options={"compression": "snappy"},
        transformation_ctx=f"sink_{table}",
    )

    print(f"  {table}: written to s3://{LAKE_BUCKET}/bronze/orders/{table}/")

job.commit()
print("Source1 bronze job complete")
