"""
Lambda — Source 2 Bronze Extractor
Calls the Product API (API Gateway → Lambda) and writes paginated responses
to S3 bronze zone as Parquet via PyArrow.

Environment variables:
  LAKE_BUCKET   S3 bucket name
  API_BASE_URL  Base URL of Source 2 API
                (e.g. https://xxxx.execute-api.ap-southeast-2.amazonaws.com/dev)
"""

import io
import json
import logging
import os
from datetime import datetime, timezone

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import urllib.request

log = logging.getLogger()
log.setLevel(logging.INFO)

LAKE_BUCKET = os.environ["LAKE_BUCKET"]
API_BASE_URL = os.environ["API_BASE_URL"].rstrip("/")
RUN_DATE = datetime.now(timezone.utc).strftime("%Y/%m/%d")

s3 = boto3.client("s3")

SCHEMAS = {
    "products": pa.schema([
        pa.field("product_id",    pa.int32()),
        pa.field("product_name",  pa.string()),
        pa.field("aisle_id",      pa.int16()),
        pa.field("department_id", pa.int16()),
    ]),
    "aisles": pa.schema([
        pa.field("aisle_id", pa.int16()),
        pa.field("aisle",    pa.string()),
    ]),
    "departments": pa.schema([
        pa.field("department_id", pa.int16()),
        pa.field("department",    pa.string()),
    ]),
}


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def _write_parquet(records: list[dict], schema: pa.Schema, s3_key: str) -> None:
    table = pa.Table.from_pylist(records, schema=schema)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    s3.put_object(Bucket=LAKE_BUCKET, Key=s3_key, Body=buf.getvalue())
    log.info("Written %d rows to s3://%s/%s", len(records), LAKE_BUCKET, s3_key)


def extract_simple(endpoint: str) -> None:
    data = _fetch_json(f"{API_BASE_URL}/{endpoint}")
    key = f"bronze/products/{endpoint}/run_date={RUN_DATE}/data.parquet"
    _write_parquet(data, SCHEMAS[endpoint], key)


def extract_products() -> None:
    page, all_rows = 1, []
    while True:
        resp = _fetch_json(f"{API_BASE_URL}/products?page={page}&page_size=1000")
        items = resp["items"]
        all_rows.extend(items)
        log.info("Products page %d: %d items (total so far: %d)", page, len(items), len(all_rows))
        if len(all_rows) >= resp["total"]:
            break
        page += 1

    key = f"bronze/products/products/run_date={RUN_DATE}/data.parquet"
    _write_parquet(all_rows, SCHEMAS["products"], key)


def lambda_handler(event: dict, context) -> dict:
    log.info("Starting Source 2 bronze extraction, run_date=%s", RUN_DATE)

    extract_simple("aisles")
    extract_simple("departments")
    extract_products()

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "run_date": RUN_DATE}),
    }
