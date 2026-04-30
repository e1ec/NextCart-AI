# Architecture Overview

## Data Flow

```
Source 1: orders.csv / order_products__prior.csv / order_products__train.csv
          └─► RDS PostgreSQL (nextcart-orders)
                └─► Lambda / Glue → S3 bronze/orders/

Source 2: products.csv / aisles.csv / departments.csv
          └─► RDS PostgreSQL (nextcart-products)
                └─► FastAPI (GET /products etc.)
                      └─► Lambda → S3 bronze/products/

Source 3: Python simulator → Kinesis Data Stream
                              └─► Lambda consumer → S3 bronze/clickstream/

S3 bronze → Glue/PySpark (Silver transforms + Great Expectations)
         → S3 silver/ (validated Parquet, partitioned)
              → EMR PySpark (Gold feature engineering, cross-source joins)
                   → S3 gold/ (ML-ready features)
                        → SageMaker Training (LightGBM / ALS)
                              → Model Registry
                                    → Lambda + API Gateway (recommendation serving)
```

## Medallion Zones

| Zone | S3 Prefix | Format | Purpose |
|------|-----------|--------|---------|
| Bronze | `bronze/` | JSON / CSV as-is | Raw copy of source data |
| Silver | `silver/` | Parquet (snappy) | Cleaned, validated, typed |
| Gold | `gold/` | Parquet (snappy) | Feature-engineered, ML-ready |
| Quarantine | `quarantine/` | Original + metadata | Failed DQ records |

## AWS Services

| Service | Role |
|---------|------|
| S3 | Data lake (all zones) |
| RDS PostgreSQL | Source 1 (orders) + Source 2 (products) storage |
| Kinesis Data Stream | Source 3 clickstream ingestion |
| AWS Lambda | Bronze ingestion + recommendation serving |
| AWS Glue | ETL jobs + Data Catalog + DQ rules |
| Amazon EMR | PySpark gold feature engineering + ALS training |
| SageMaker | LightGBM/XGBoost training + HPO + Model Registry + Monitor |
| API Gateway | Public endpoint for recommendation API |
| Step Functions | Pipeline orchestration (bronze → silver → gold → training) |
| CloudWatch | Monitoring + alerts |
| Secrets Manager | Database passwords + API keys |
| Terraform | IaC for all of the above |
| GitHub Actions | CI (lint, test, tf-validate) + CD (dev auto / prod gated) |
