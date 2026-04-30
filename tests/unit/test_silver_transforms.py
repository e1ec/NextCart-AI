"""
Unit tests for silver transform logic.
Uses small in-memory DataFrames — no AWS, no real Glue context.
"""

import pytest

pytest.importorskip("pyspark", reason="PySpark not installed — skipping Spark unit tests")

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


@pytest.fixture(scope="module")
def spark():
    return (
        SparkSession.builder
        .master("local[1]")
        .appName("nextcart-test")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )


def test_orders_null_filter(spark):
    df = spark.createDataFrame(
        [(1, 100, "prior", 1, 0, 10, 3.0),
         (None, 101, "prior", 2, 1, 9, None),   # null order_id — should be dropped
         (3, 102, "train", 1, 3, 8, 7.0)],
        ["order_id", "user_id", "eval_set", "order_number",
         "order_dow", "order_hour_of_day", "days_since_prior_order"],
    )
    filtered = df.filter(F.col("order_id").isNotNull() & F.col("user_id").isNotNull())
    assert filtered.count() == 2


def test_orders_deduplication(spark):
    df = spark.createDataFrame(
        [(1, 100, "prior"), (1, 100, "prior"), (2, 101, "prior")],
        ["order_id", "user_id", "eval_set"],
    )
    deduped = df.dropDuplicates(["order_id"])
    assert deduped.count() == 2


def test_order_dow_domain(spark):
    df = spark.createDataFrame(
        [(1, 0), (2, 3), (3, 6), (4, 7)],   # dow=7 is invalid
        ["order_id", "order_dow"],
    )
    valid = df.filter(F.col("order_dow").between(0, 6))
    assert valid.count() == 3


def test_reordered_domain(spark):
    df = spark.createDataFrame(
        [(1, 1, 0), (2, 1, 1), (3, 1, 2)],   # reordered=2 is invalid
        ["order_id", "product_id", "reordered"],
    )
    valid = df.filter(F.col("reordered").isin(0, 1))
    assert valid.count() == 2


def test_product_name_normalisation(spark):
    df = spark.createDataFrame(
        [(1, "  Organic  Milk  ")],
        ["product_id", "product_name"],
    )
    normalised = df.withColumn(
        "product_name_clean",
        F.trim(F.regexp_replace(F.lower(F.col("product_name")), r"\s+", " "))
    )
    result = normalised.collect()[0]["product_name_clean"]
    assert result == "organic milk"
