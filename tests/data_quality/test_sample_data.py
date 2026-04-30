"""Basic schema checks on sample CSVs — runs in CI without AWS."""

import os
import pytest
import pandas as pd

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../../data/samples")


def _sample_path(filename: str) -> str:
    return os.path.join(SAMPLES_DIR, filename)


def _sample_exists(filename: str) -> bool:
    return os.path.exists(_sample_path(filename))


@pytest.mark.skipif(
    not _sample_exists("orders_sample.csv"),
    reason="orders_sample.csv not yet generated — run: make generate-samples",
)
def test_orders_sample_schema():
    df = pd.read_csv(_sample_path("orders_sample.csv"))
    required_cols = {"order_id", "user_id", "eval_set", "order_number", "order_dow"}
    assert required_cols.issubset(df.columns), f"Missing columns: {required_cols - set(df.columns)}"
    assert df["order_id"].notna().all(), "order_id must not be null"
    assert df["user_id"].notna().all(), "user_id must not be null"
    assert df["reordered"].isin([0, 1, None]).all() if "reordered" in df.columns else True


@pytest.mark.skipif(
    not _sample_exists("products_sample.csv"),
    reason="products_sample.csv not yet generated",
)
def test_products_sample_schema():
    df = pd.read_csv(_sample_path("products_sample.csv"))
    required_cols = {"product_id", "product_name", "aisle_id", "department_id"}
    assert required_cols.issubset(df.columns)
    assert df["product_id"].notna().all()
