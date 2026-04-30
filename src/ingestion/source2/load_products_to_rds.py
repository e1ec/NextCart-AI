"""
Source 2 — Load product metadata CSVs into RDS PostgreSQL (nextcart-products DB).

Usage:
  python load_products_to_rds.py --env local
  python load_products_to_rds.py --env dev
"""

import argparse
import json
import logging
import os
import time

import boto3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../../data/raw")


def get_connection_params(env: str) -> dict:
    if env == "local":
        return {
            "host": os.getenv("LOCAL_DB_HOST", "localhost"),
            "port": int(os.getenv("LOCAL_DB_PORT", "5434")),
            "dbname": "products",
            "user": "nextcart_admin",
            "password": os.getenv("LOCAL_DB_PASSWORD", "localpassword"),
        }
    secret_arn = os.environ["PRODUCTS_DB_SECRET_ARN"]
    secret = json.loads(
        boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)["SecretString"]
    )
    return {
        "host": secret["host"],
        "port": secret["port"],
        "dbname": secret["dbname"],
        "user": secret["username"],
        "password": secret["password"],
        "sslmode": "require",
    }


def create_tables(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_id   SMALLINT PRIMARY KEY,
                department      VARCHAR(100) NOT NULL
            );

            CREATE TABLE IF NOT EXISTS aisles (
                aisle_id    SMALLINT PRIMARY KEY,
                aisle       VARCHAR(200) NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id      INTEGER PRIMARY KEY,
                product_name    VARCHAR(500) NOT NULL,
                aisle_id        SMALLINT REFERENCES aisles(aisle_id),
                department_id   SMALLINT REFERENCES departments(department_id)
            );

            CREATE INDEX IF NOT EXISTS idx_products_aisle ON products (aisle_id);
            CREATE INDEX IF NOT EXISTS idx_products_dept ON products (department_id);
        """)
    conn.commit()
    log.info("Tables created (or already exist)")


def load_all(conn: psycopg2.extensions.connection) -> None:
    # Load in FK order: departments → aisles → products
    for filename, table, cols in [
        ("departments.csv", "departments", ["department_id", "department"]),
        ("aisles.csv",      "aisles",      ["aisle_id", "aisle"]),
        ("products.csv",    "products",    ["product_id", "product_name", "aisle_id", "department_id"]),
    ]:
        df = pd.read_csv(os.path.join(DATA_DIR, filename))
        rows = [tuple(r) for r in df[cols].itertuples(index=False)]
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s ON CONFLICT DO NOTHING",
                rows,
            )
        conn.commit()
        log.info("Loaded %s: %d rows", table, len(rows))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["local", "dev", "prod"], default="local")
    args = parser.parse_args()

    params = get_connection_params(args.env)
    log.info("Connecting to %s:%s/%s", params["host"], params["port"], params["dbname"])

    start = time.time()
    with psycopg2.connect(**params) as conn:
        create_tables(conn)
        load_all(conn)

    log.info("Products DB loaded in %.1fs", time.time() - start)


if __name__ == "__main__":
    main()
