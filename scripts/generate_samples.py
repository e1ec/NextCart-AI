"""
Generate small sample CSVs from the raw data for CI use.
Run: python scripts/generate_samples.py
Output: data/samples/orders_sample.csv, products_sample.csv, order_products_sample.csv
"""

import os
import sys
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "../data/raw")
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../data/samples")
SAMPLE_SIZE = 1000


def sample_file(filename: str, n: int = SAMPLE_SIZE) -> None:
    src = os.path.join(RAW_DIR, filename)
    dst = os.path.join(SAMPLES_DIR, filename.replace(".csv", "_sample.csv"))
    if not os.path.exists(src):
        print(f"  SKIP {filename} — not found in data/raw/")
        return
    df = pd.read_csv(src, nrows=n)
    df.to_csv(dst, index=False)
    print(f"  OK   {filename} → {os.path.basename(dst)} ({len(df)} rows)")


if __name__ == "__main__":
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    print("Generating samples...")
    sample_file("orders.csv")
    sample_file("order_products__prior.csv")
    sample_file("order_products__train.csv")
    sample_file("products.csv")
    sample_file("aisles.csv")
    sample_file("departments.csv")
    print("Done.")
