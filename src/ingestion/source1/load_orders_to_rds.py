"""
Source 1 — Load Instacart order CSVs into RDS PostgreSQL (nextcart-orders DB).

Usage:
  python load_orders_to_rds.py --env local          # local Docker PostgreSQL
  python load_orders_to_rds.py --env dev --sample   # AWS RDS, sample 1000 rows
  python load_orders_to_rds.py --env dev            # AWS RDS, full data
"""

import argparse
import json
import logging
import os
import time

import boto3
import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../../data")
CHUNK_SIZE = 50_000


def get_connection_params(env: str) -> dict:
    if env == "local":
        return {
            "host": os.getenv("LOCAL_DB_HOST", "localhost"),
            "port": int(os.getenv("LOCAL_DB_PORT", "5433")),
            "dbname": "orders",
            "user": "nextcart_admin",
            "password": os.getenv("LOCAL_DB_PASSWORD", "localpassword"),
        }
    secret_arn = os.environ["ORDERS_DB_SECRET_ARN"]
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
            CREATE TABLE IF NOT EXISTS orders (
                order_id              INTEGER PRIMARY KEY,
                user_id               INTEGER NOT NULL,
                eval_set              VARCHAR(10) NOT NULL,
                order_number          INTEGER NOT NULL,
                order_dow             SMALLINT NOT NULL,
                order_hour_of_day     SMALLINT NOT NULL,
                days_since_prior_order FLOAT
            );

            CREATE TABLE IF NOT EXISTS order_products_prior (
                order_id          INTEGER NOT NULL,
                product_id        INTEGER NOT NULL,
                add_to_cart_order SMALLINT NOT NULL,
                reordered         SMALLINT NOT NULL,
                PRIMARY KEY (order_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS order_products_train (
                order_id          INTEGER NOT NULL,
                product_id        INTEGER NOT NULL,
                add_to_cart_order SMALLINT NOT NULL,
                reordered         SMALLINT NOT NULL,
                PRIMARY KEY (order_id, product_id)
            );

            CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_eval_set ON orders (eval_set);
            CREATE INDEX IF NOT EXISTS idx_opp_product_id ON order_products_prior (product_id);
            CREATE INDEX IF NOT EXISTS idx_opt_product_id ON order_products_train (product_id);
        """)
    conn.commit()
    log.info("Tables and indexes created (or already exist)")


def load_csv(
    conn: psycopg2.extensions.connection,
    csv_path: str,
    table: str,
    columns: list[str],
    nrows: int | None = None,
) -> None:
    log.info("Loading %s → %s", os.path.basename(csv_path), table)
    total = 0
    for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE, nrows=nrows):
        chunk = chunk[columns]
        rows = [tuple(row) for row in chunk.itertuples(index=False)]
        with conn.cursor() as cur:
            execute_values(
                cur,
                sql.SQL("INSERT INTO {} ({}) VALUES %s ON CONFLICT DO NOTHING").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                ),
                rows,
            )
        conn.commit()
        total += len(rows)
        log.info("  %s: %d rows inserted", table, total)
    log.info("Finished %s: %d total rows", table, total)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["local", "dev", "prod"], default="local")
    parser.add_argument("--sample", action="store_true", help="Load only 1000 rows per table")
    args = parser.parse_args()

    nrows = 1000 if args.sample else None
    raw_dir = os.path.join(DATA_DIR, "raw" if not args.sample else "samples")

    params = get_connection_params(args.env)
    log.info("Connecting to %s:%s/%s", params["host"], params["port"], params["dbname"])

    start = time.time()
    with psycopg2.connect(**params) as conn:
        create_tables(conn)

        load_csv(
            conn,
            os.path.join(DATA_DIR, "raw", "orders.csv"),
            "orders",
            ["order_id", "user_id", "eval_set", "order_number",
             "order_dow", "order_hour_of_day", "days_since_prior_order"],
            nrows=nrows,
        )
        load_csv(
            conn,
            os.path.join(DATA_DIR, "raw", "order_products__prior.csv"),
            "order_products_prior",
            ["order_id", "product_id", "add_to_cart_order", "reordered"],
            nrows=nrows,
        )
        load_csv(
            conn,
            os.path.join(DATA_DIR, "raw", "order_products__train.csv"),
            "order_products_train",
            ["order_id", "product_id", "add_to_cart_order", "reordered"],
            nrows=nrows,
        )

    log.info("All tables loaded in %.1fs", time.time() - start)


if __name__ == "__main__":
    main()
