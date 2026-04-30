# NextCart — Instacart Market Basket Analysis
## Data Engineering & ML Platform · Medallion Architecture · AWS · Terraform · GitHub Actions

---

## Project Overview

End-to-end data engineering and machine learning project built on the Instacart dataset.
Solves two business problems via a unified AWS pipeline:

| Task | Problem | Model | Target Metric |
|------|---------|-------|---------------|
| A — Reorder Prediction | Users waste time re-searching items they always buy | LightGBM (primary), XGBoost (baseline) | F1 ≥ 0.38 |
| B — Product Recommendation | Platform misses upsell opportunities mid-session | ALS + Content-Based Hybrid | Precision@10 ≥ 0.30 |

**Team**: 3 people · **Duration**: 6 weeks · **Cloud**: AWS · **IaC**: Terraform

---

## Directory Structure

```
NextCart/
├── CLAUDE.md                        # This file — project bible
├── Makefile                         # Top-level shortcuts (make lint, make test, etc.)
├── pyproject.toml                   # Python project metadata & tool config
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Dev/test dependencies (pytest, flake8, etc.)
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # PR validation: lint + unit tests + data quality
│       ├── deploy-dev.yml           # Auto-deploy to dev on push to `develop`
│       └── deploy-prod.yml          # Deploy to prod on push to `main` (manual approval gate)
│
├── infra/
│   └── terraform/
│       ├── modules/                 # Reusable Terraform modules
│       │   ├── rds/                 # RDS PostgreSQL (source1 & source2 databases)
│       │   ├── s3/                  # S3 buckets (bronze / silver / gold zones)
│       │   ├── kinesis/             # Kinesis Data Stream (source3 clickstream)
│       │   ├── glue/                # Glue Crawlers + ETL Jobs
│       │   ├── emr/                 # EMR cluster for PySpark feature engineering
│       │   ├── sagemaker/           # SageMaker Training Jobs + Model Registry + Endpoints
│       │   ├── lambda/              # Lambda functions (API fetcher, stream consumer)
│       │   ├── step_functions/      # Step Functions orchestration workflow
│       │   ├── api_gateway/         # API Gateway for recommendation serving
│       │   └── iam/                 # IAM roles and policies
│       ├── environments/
│       │   ├── dev/
│       │   │   ├── main.tf          # Dev environment root
│       │   │   ├── variables.tf
│       │   │   └── terraform.tfvars # Dev-specific values (smaller instance sizes)
│       │   └── prod/
│       │       ├── main.tf          # Prod environment root
│       │       ├── variables.tf
│       │       └── terraform.tfvars # Prod-specific values
│       ├── backend.tf               # S3 remote state + DynamoDB lock table
│       └── versions.tf              # Provider version constraints
│
├── data/
│   ├── raw/                         # Original Kaggle CSVs (gitignored — large files)
│   │   ├── orders.csv
│   │   ├── order_products__prior.csv
│   │   ├── order_products__train.csv
│   │   ├── products.csv
│   │   ├── aisles.csv
│   │   └── departments.csv
│   └── samples/                     # Small samples for local dev & CI tests (committed)
│       ├── orders_sample.csv        # 1000 rows
│       ├── order_products_sample.csv
│       └── products_sample.csv
│
├── src/
│   ├── ingestion/                   # Load raw data into source systems
│   │   ├── source1/
│   │   │   └── load_orders_to_rds.py    # CSV → RDS orders database
│   │   ├── source2/
│   │   │   ├── load_products_to_rds.py  # CSV → RDS products database
│   │   │   └── api/                     # FastAPI layer over the products RDS
│   │   │       ├── main.py              # FastAPI app (GET /products, /aisles, etc.)
│   │   │       ├── models.py            # Pydantic schemas
│   │   │       ├── database.py          # SQLAlchemy connection
│   │   │       ├── Dockerfile
│   │   │       └── requirements.txt
│   │   └── source3/
│   │       └── clickstream_simulator.py # Generates fake events → Kinesis stream
│   │
│   ├── pipeline/                    # Medallion Architecture ETL
│   │   ├── bronze/                  # Raw ingestion into S3 (as-is, schema preserved)
│   │   │   ├── rds_source1_to_s3.py     # RDS orders → s3://…/bronze/orders/
│   │   │   ├── api_source2_to_s3.py     # API products → s3://…/bronze/products/
│   │   │   └── kinesis_to_s3.py         # Kinesis consumer → s3://…/bronze/clickstream/
│   │   ├── silver/                  # Cleaned, validated, Parquet, partitioned
│   │   │   ├── orders_silver.py         # Deduplicate, null-check, cast types
│   │   │   ├── products_silver.py       # Normalise categories, fill missing prices
│   │   │   └── clickstream_silver.py    # Parse events, sessionise, validate schema
│   │   └── gold/                    # Feature-engineered tables ready for ML
│   │       ├── reorder_features.py      # Task A: user-product reorder features
│   │       ├── recommendation_features.py # Task B: interaction matrix, item vectors
│   │       └── analytics_aggregates.py  # Business KPI aggregates for reporting
│   │
│   ├── ml/
│   │   ├── reorder/                 # Task A — Reorder Prediction
│   │   │   ├── train_xgboost.py         # Phase 1 baseline
│   │   │   ├── train_lightgbm.py        # Phase 2 primary model
│   │   │   ├── hpo_config.py            # SageMaker HPO search space
│   │   │   └── evaluate.py              # F1, SHAP analysis, confusion matrix
│   │   └── recommendation/          # Task B — Product Recommendation
│   │       ├── train_als.py             # PySpark MLlib ALS on EMR
│   │       ├── content_based.py         # Cosine similarity on product embeddings
│   │       ├── hybrid.py                # Weighted merge of ALS + content scores
│   │       └── evaluate.py              # Precision@K, Recall@K, NDCG
│   │
│   ├── serving/
│   │   ├── recommendation_handler.py    # Lambda handler for recommendation API
│   │   └── batch_reorder_scorer.py      # Batch SageMaker inference job
│   │
│   └── monitoring/
│       ├── data_quality_checks.py       # Great Expectations suites
│       └── model_drift_monitor.py       # SageMaker Model Monitor baseline + alerts
│
├── tests/
│   ├── unit/                        # Pure-Python, no AWS, no DB
│   │   ├── test_silver_transforms.py
│   │   ├── test_feature_engineering.py
│   │   └── test_api_models.py
│   ├── integration/                 # Requires localstack or real AWS dev account
│   │   ├── test_rds_loader.py
│   │   └── test_pipeline_end_to_end.py
│   └── data_quality/
│       └── test_great_expectations.py
│
└── notebooks/
    ├── 01_eda.ipynb                 # Exploratory data analysis
    ├── 02_feature_engineering.ipynb # Feature experiments
    └── 03_model_experiments.ipynb   # Model comparison & tuning
```

---

## Data Sources

### Source 1 — Historical Orders (RDS PostgreSQL · Batch)

**Files**: `orders.csv`, `order_products__prior.csv`, `order_products__train.csv`
**Database**: `nextcart-orders` RDS instance
**Schema tables**:

| Table | Key Columns | Row Count (approx) |
|-------|------------|-------------------|
| `orders` | order_id, user_id, eval_set, order_number, order_dow, order_hour_of_day, days_since_prior_order | 3.4M |
| `order_products_prior` | order_id, product_id, add_to_cart_order, reordered | 32M |
| `order_products_train` | order_id, product_id, add_to_cart_order, reordered | 1.4M |

**Extraction**: Full-load snapshot via `src/pipeline/bronze/rds_source1_to_s3.py` → S3 bronze zone as Parquet, partitioned by `eval_set`.

---

### Source 2 — Product Metadata (RDS PostgreSQL + REST API · Batch/On-demand)

**Files**: `products.csv`, `aisles.csv`, `departments.csv`
**Database**: `nextcart-products` RDS instance (separate from Source 1)
**API**: FastAPI service deployed as Docker container, sits in front of the products RDS

| Table | Key Columns |
|-------|------------|
| `products` | product_id, product_name, aisle_id, department_id |
| `aisles` | aisle_id, aisle |
| `departments` | department_id, department |

**API Endpoints** (served by `src/ingestion/source2/api/`):

```
GET /products                → paginated product list
GET /products/{product_id}   → single product with aisle + department joined
GET /aisles                  → all aisles
GET /departments             → all departments
GET /health                  → liveness probe
```

**Extraction**: Lambda function calls the API, writes JSON responses → S3 bronze zone → Parquet in silver.

---

### Source 3 — Clickstream Events (Kinesis Data Stream · Near Real-time)

**Simulated by**: `src/ingestion/source3/clickstream_simulator.py`
**Stream**: `nextcart-clickstream` Kinesis Data Stream (1 shard dev / 4 shards prod)
**Event schema**:

```json
{
  "event_id": "uuid",
  "user_id": 12345,
  "session_id": "uuid",
  "event_type": "view | add_to_cart | remove_from_cart | purchase",
  "product_id": 196,
  "timestamp": "2024-01-15T10:23:45Z",
  "metadata": { "page": "search", "query": "organic milk" }
}
```

**Consumption**: Kinesis → Lambda consumer → S3 bronze/clickstream/ (hourly partitioned).

---

## Medallion Architecture Layers

```
Source 1 (RDS orders)  ─┐
Source 2 (API products) ─┼─► BRONZE (S3 raw JSON/CSV) ─► SILVER (S3 Parquet, validated) ─► GOLD (S3 ML features)
Source 3 (Kinesis)     ─┘
```

| Layer | S3 Prefix | Format | Partitioning | SLA |
|-------|-----------|--------|-------------|-----|
| Bronze | `s3://nextcart-{env}-lake/bronze/` | JSON / CSV as-is | `source=X/year=Y/month=M/day=D/` | Write within 1h of source |
| Silver | `s3://nextcart-{env}-lake/silver/` | Parquet (snappy) | `table=X/year=Y/month=M/` | Daily batch |
| Gold | `s3://nextcart-{env}-lake/gold/` | Parquet (snappy) | `dataset=X/version=V/` | Triggered by silver update |

**Data Quality Gates** (between layers):
- Bronze → Silver: null rate, schema conformance, referential integrity (Great Expectations)
- Silver → Gold: feature completeness, value range checks, join cardinality

Failed records go to `s3://nextcart-{env}-lake/quarantine/` with a rejection reason tag.

---

## Infrastructure Principles (Terraform)

### State Management
- Remote state: `s3://nextcart-terraform-state-{account_id}/` (versioning enabled)
- Lock table: `nextcart-terraform-locks` (DynamoDB)
- Workspace per environment: `terraform workspace select dev|prod`

### Module Design
Each module under `infra/terraform/modules/` follows this pattern:
```
modules/rds/
├── main.tf       # Resources
├── variables.tf  # Input variables (no defaults for required values)
├── outputs.tf    # Exported values consumed by other modules
└── README.md     # Module purpose + usage example
```

### Environment Separation
- `environments/dev/` — smaller instances, single-AZ, auto-shutdown after office hours
- `environments/prod/` — Multi-AZ RDS, EMR auto-scaling, CloudWatch alarms wired to SNS

### Naming Convention
All resources: `nextcart-{env}-{service}[-{qualifier}]`
Examples: `nextcart-dev-rds-orders`, `nextcart-prod-s3-lake`, `nextcart-dev-kinesis-clickstream`

### Tagging (mandatory on every resource)
```hcl
tags = {
  Project     = "nextcart"
  Environment = var.environment   # dev | prod
  ManagedBy   = "terraform"
  Owner       = "data-eng-team"
}
```

### Security Rules
- RDS: no public access, VPC-internal only, credentials via AWS Secrets Manager
- S3: block all public access, SSE-S3 encryption, versioning on lake bucket
- IAM: least-privilege — each Lambda/Glue/EMR gets its own role with only the permissions it needs
- Kinesis: server-side encryption enabled
- No hardcoded credentials anywhere — all secrets via `aws_secretsmanager_secret`

### Cost Controls (Dev)
- RDS `db.t3.micro`, Multi-AZ disabled
- EMR: single-node, `m5.xlarge`, terminate after job completion
- SageMaker: `ml.m5.large` training, no persistent endpoints (use batch transform)
- Kinesis: 1 shard, enhanced fan-out disabled

---

## CI/CD Strategy (GitHub Actions)

### Branch Model
```
main          ← production releases (protected, requires PR + 1 approval)
  └── develop ← integration branch (auto-deploys to dev)
        └── feature/ABC-123-short-description
        └── fix/bug-description
        └── data/source-name-change
```

### Workflow: `ci.yml` (runs on every PR)
```
Trigger: pull_request → develop | main

Jobs:
  lint:        flake8 src/ tests/  (max-line 100)
  type-check:  mypy src/  (strict = false for now)
  unit-tests:  pytest tests/unit/ --cov=src --cov-fail-under=80
  data-quality: pytest tests/data_quality/ (uses sample data only)
  tf-validate: terraform validate + tflint on changed modules
  tf-plan-dev: terraform plan (dev workspace) — output posted as PR comment
```

### Workflow: `deploy-dev.yml` (auto-deploy)
```
Trigger: push → develop

Jobs:
  tf-apply-dev:  terraform apply -auto-approve (dev workspace)
  glue-sync:     aws s3 sync src/pipeline/ s3://nextcart-dev-glue-scripts/
  api-deploy:    docker build + push to ECR → update ECS task definition
  smoke-test:    hit /health endpoint, run 1 pipeline step end-to-end
```

### Workflow: `deploy-prod.yml` (gated)
```
Trigger: push → main

Jobs:
  tf-plan-prod:    terraform plan (prod workspace) — requires manual approval
  [MANUAL GATE]    GitHub Environment "production" approval required
  tf-apply-prod:   terraform apply
  model-promote:   if ML code changed → trigger SageMaker Training Job
                   compare new model vs registry champion (F1 / Precision@10)
                   promote only if metrics improve
  rollback-check:  on failure → CDK rollback + Model Registry version revert
```

### Environment Secrets (GitHub Secrets)
```
AWS_ACCESS_KEY_ID          (OIDC preferred — use aws-actions/configure-aws-credentials)
AWS_SECRET_ACCESS_KEY
AWS_REGION                 = ap-southeast-2
TF_STATE_BUCKET
DB_PASSWORD_SECRET_ARN
```

### Model CI/CD Rules
- A PR touching `src/ml/` or `src/pipeline/gold/` triggers a SageMaker Training Job in dev
- New model must beat existing registry champion on held-out test set before promotion
- Metrics logged to MLflow or SageMaker Experiments; artifact stored in Model Registry

---

## Development Standards

### Python
- Version: **3.11**
- Formatter: **black** (line length 100)
- Linter: **flake8** (line length 100, ignore E203, W503)
- Type hints: required on all function signatures in `src/`
- Import style: absolute imports only

### Code Structure
- One responsibility per file — a Glue ETL job does not also do ML
- No business logic in Lambda handlers — handlers call functions from `src/`
- All SQL queries in `.sql` files or named constants, never f-strings with user data
- PySpark jobs must be runnable locally with `--local` flag (uses sample data)

### Testing Rules
- Unit tests: no AWS calls, no DB connections — mock at the boundary
- Integration tests: tagged `@pytest.mark.integration` — skipped in CI unless `RUN_INTEGRATION=true`
- Data quality tests: use sample CSVs in `data/samples/` — always runnable in CI
- Minimum coverage: **80%** on `src/pipeline/` and `src/ml/`
- Never mock the database in integration tests — use a real test DB or LocalStack

### Git Commit Format
```
type(scope): short description

Types: feat | fix | data | infra | ci | docs | test | chore
Scope: source1 | source2 | source3 | bronze | silver | gold | ml | api | infra

Examples:
  feat(silver): add null imputation for days_since_prior_order
  infra(rds): increase dev instance to t3.small for EMR join tests
  data(source3): add remove_from_cart event type to simulator
  ci(deploy): add manual approval gate to prod workflow
```

### Notebook Rules
- Notebooks are for **exploration only** — no production code lives in `.ipynb`
- Before merging a notebook, clear all outputs (`nbstripout` pre-commit hook)
- Reusable logic from notebooks must be extracted to `src/` before the sprint ends

---

## Key Commands (Makefile)

```bash
make install          # pip install -r requirements-dev.txt
make lint             # flake8 + black --check
make format           # black src/ tests/
make test             # pytest tests/unit/ tests/data_quality/
make test-all         # pytest tests/ (includes integration — needs AWS)
make tf-init-dev      # terraform -chdir=infra/terraform/environments/dev init
make tf-plan-dev      # terraform plan (dev)
make tf-apply-dev     # terraform apply (dev)
make load-source1     # python src/ingestion/source1/load_orders_to_rds.py
make load-source2     # python src/ingestion/source2/load_products_to_rds.py
make api-up           # docker-compose up src/ingestion/source2/api/
make simulate-stream  # python src/ingestion/source3/clickstream_simulator.py --duration 60
make run-bronze       # Run all three bronze ingestion scripts in sequence
make run-silver       # Run all three silver transform scripts
make run-gold         # Run gold feature engineering
make train-xgboost    # python src/ml/reorder/train_xgboost.py --env local
make train-lightgbm   # python src/ml/reorder/train_lightgbm.py --env local
make train-als        # Submit PySpark ALS job to EMR (requires AWS)
```

---

## Week-by-Week Delivery Plan

| Week | Focus | Key Output |
|------|-------|-----------|
| 1 | EDA + AWS environment + Terraform base + CI scaffold | Working dev AWS account, CI runs on PRs |
| 2 | Source 1 & 2 RDS loaders + Product API + Bronze pipeline | Data in S3 bronze from all 3 sources |
| 3 | Silver transforms (Great Expectations) + EMR PySpark Gold features | Validated Parquet in silver/gold |
| 4 | XGBoost baseline (Task A) → LightGBM + SageMaker Model Registry | F1 ≥ 0.38 logged in Model Registry |
| 5 | ALS (Task B) + Content-Based Hybrid + CD pipeline (prod deploy) | Recommendation API live in staging |
| 6 | SageMaker HPO + Model Monitor + final evaluation report | Full pipeline end-to-end in prod |

---

## Local Development Setup

```bash
# 1. Python environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. AWS credentials (dev account)
aws configure --profile nextcart-dev
export AWS_PROFILE=nextcart-dev

# 3. Terraform init (dev)
cd infra/terraform/environments/dev
terraform init
terraform workspace new dev  # or select if exists

# 4. Start product API locally
cd src/ingestion/source2/api
docker-compose up   # or: uvicorn main:app --reload

# 5. Run unit tests
pytest tests/unit/ -v

# 6. Load sample data locally (uses data/samples/ CSVs)
python src/ingestion/source1/load_orders_to_rds.py --env local --sample
```

---

## What NOT to Do

- Do not put credentials in any source file, `.env`, or notebook
- Do not run `terraform apply` on prod without the PR review gate
- Do not push to `main` directly — always go through a PR
- Do not run ML training jobs in CI (too slow/expensive) — CI only runs unit tests
- Do not use `SELECT *` in production queries — always name columns explicitly
- Do not commit the `data/raw/` directory — files are large and gitignored
- Do not use Kinesis for the batch sources (Source 1 & 2) — they are RDS/API-based by design
