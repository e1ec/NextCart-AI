# NextCart — Project Plan

**Status**: 🔵 In Progress — Week 1–3 (Silver) complete; next: Gold features + ML
**Last Updated**: 2026-04-30
**Team Size**: 3
**Duration**: 6 Weeks

---

## Quick Status Dashboard

| Area | Status | Notes |
|------|--------|-------|
| AWS Environment | ✅ Done | VPC, RDS ×2, S3, Lambda, Glue, API GW, VPC endpoints deployed |
| CI/CD Scaffold | ✅ Done | CI green; deploy-dev/prod workflows configured with backend-config |
| Source 1 — RDS Orders | ✅ Done | 3.4M orders + 32M prior + 1.4M train rows loaded |
| Source 2 — Product API | ✅ Done | 49,688 products loaded; Lambda API working (`/health`, `/departments`) |
| Source 3 — Kinesis Simulator | ⏸ Paused | Deferred — not in current scope |
| Bronze Pipeline | ✅ Done | Glue (S1) + Lambda (S2) writing Parquet to S3 bronze zone |
| Silver Pipeline | ✅ Done | Orders + Products Glue jobs complete; Parquet in silver zone |
| Gold / Feature Engineering | ⬜ Not Started | EMR PySpark cross-source join — **next priority** |
| Task A — XGBoost Baseline | ⬜ Not Started | Requires Gold features |
| Task A — LightGBM | ⬜ Not Started | F1 ≥ 0.38 target |
| Task B — ALS | ⬜ Not Started | Requires interaction matrix from Gold |
| Task B — Hybrid | ⬜ Not Started | ALS + Content-Based |
| CD Pipeline (Prod Deploy) | 🔵 In Progress | Workflows written; dev Secrets configured; prod env empty |
| HPO + Model Monitor | ⬜ Not Started | Week 6 |
| Final Report | ⬜ Not Started | Week 6 |

**Status Legend**: ⬜ Not Started · 🔵 In Progress · ✅ Done · 🔴 Blocked · ⏸ Paused

---

## Goals & Success Criteria

### Task A — Reorder Prediction
> Users waste time re-searching items they always buy.
> ~59% of all purchases are reorders across 49,000+ SKUs.

| Metric | Minimum | Target |
|--------|---------|--------|
| F1-score (test set) | ≥ 0.38 | ~0.40–0.42 |
| Multi-source feature lift vs single-source | ≥ +5% F1 | — |

### Task B — Product Recommendation
> Platform misses upsell opportunities mid-session due to no recommendation mechanism.

| Metric | Minimum | Target |
|--------|---------|--------|
| Precision@10 | ≥ 0.30 | — |
| Recall@10 | Measured | — |
| Cold-start coverage (Content-Based fallback) | Measured | — |

### Engineering
- All 3 data sources flowing into S3 Medallion lake ✅ (Source 1 + 2 done; Source 3 deferred)
- Full IaC via Terraform (dev deployed ✅, prod pending)
- CI runs on every PR ✅; CD deploys to dev automatically 🔵
- Prod deploy requires manual approval gate 🔵

---

## Week 1 — Foundation ✅ Complete

**Theme**: EDA · AWS environment · Terraform base · CI scaffold

### Tasks

#### 1.1 EDA & Data Understanding
- [ ] Load all 6 CSVs locally, run shape/dtypes/null analysis
- [ ] Document key statistics: order count, reorder rate, product long-tail distribution
- [ ] Identify join keys across the 6 files (product_id, order_id, user_id)
- [x] Create `data/samples/` — 1,000-row subsets of orders + products for CI use
- [ ] Commit EDA findings to `notebooks/01_eda.ipynb`

#### 1.2 AWS Environment ✅
- [x] Configure GitHub Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `TF_STATE_BUCKET`
- [x] Create Terraform state S3 bucket + DynamoDB lock table (Phase 0)
- [x] Verify AWS CLI access: `aws sts get-caller-identity`
- [x] Run `terraform init -backend-config=backend.tfvars` — no errors

#### 1.3 Terraform Base ✅
- [x] `infra/terraform/backend.tf` — S3 state + DynamoDB lock config
- [x] `infra/terraform/versions.tf` — AWS provider ~5.0, Terraform ~1.7
- [x] `infra/terraform/modules/vpc/` — VPC, subnets, SGs, S3 + Secrets Manager VPC endpoints
- [x] `infra/terraform/modules/s3/` — lake bucket (bronze/silver/gold/quarantine zones)
- [x] `infra/terraform/modules/iam/` — Lambda, Glue, EMR roles
- [x] `infra/terraform/modules/rds/` — parameterised RDS module (orders + products)
- [x] `infra/terraform/modules/lambda/` — Source2 API + Bronze extractor + API GW
- [x] `infra/terraform/modules/glue/` — JDBC connection, crawlers, ETL jobs
- [x] `infra/terraform/environments/dev/main.tf` — wires all modules
- [x] `terraform apply` succeeds end-to-end in dev account

#### 1.4 GitHub Actions — CI/CD ✅
- [x] `.github/workflows/ci.yml` — lint (flake8 + black) + unit tests + tf-validate (green)
- [x] `.github/workflows/deploy-dev.yml` — auto-deploy on push to develop
- [x] `.github/workflows/deploy-prod.yml` — gated prod deploy with manual approval
- [x] `pyproject.toml` — black/flake8/pytest/mypy config
- [x] `.flake8` — max-line-length=100, E221/E272 ignored (alignment style)
- [x] `requirements-dev.txt` — full dev dependencies

#### 1.5 Repository Setup ✅
- [x] `.gitignore` — data/raw/, .terraform/, *.tfstate, Lambda build artifacts, backend.tfvars
- [x] Full directory skeleton with `__init__.py` files
- [x] Pushed to GitHub; CI green on PRs

---

## Week 2 — Data Ingestion (Source 1 + 2 → Bronze) ✅ Complete

**Theme**: RDS loaders · Product API · Bronze pipeline

### Tasks

#### 2.1 Source 1 — Orders RDS ✅
- [x] `nextcart-dev-rds-orders` deployed (public subnet, `publicly_accessible=true` for dev)
- [x] `src/ingestion/source1/load_orders_to_rds.py` — chunked insert, 50K rows/batch
- [x] Data loaded: orders (3.4M), order_products_prior (32M), order_products_train (1.4M)

#### 2.2 Source 2 — Products RDS + FastAPI ✅
- [x] `nextcart-dev-rds-products` deployed
- [x] `src/ingestion/source2/load_products_to_rds.py` — departments (21) → aisles (134) → products (49,688)
- [x] `src/ingestion/source2/api/` — FastAPI + Mangum Lambda adapter, all 5 endpoints working
- [x] Lambda deployed with deps layer (built via Docker, uploaded to S3, referenced via s3_bucket/s3_key)
- [x] API Gateway deployed; `curl /health` and `curl /departments` confirmed working

#### 2.3 Source 3 — Kinesis Simulator ⏸ Paused
- Deferred per scope decision. Will revisit in Week 5 if time permits.

#### 2.4 Bronze Pipeline ✅
- [x] `src/pipeline/bronze/glue_source1_bronze.py` — uses `spark.read.jdbc` with explicit bounds; boto3 fetches secret
- [x] `src/pipeline/bronze/lambda_source2_bronze.py` — paginates Product API → S3 bronze Parquet
- [x] Glue Source1 Bronze job ran successfully (3 tables → S3)
- [x] Source2 Bronze Lambda invoked successfully (products + aisles + departments → S3)

---

## Week 3 — Silver + Gold (EMR PySpark Feature Engineering)

**Theme**: Data quality · Silver transforms · EMR cross-source joins · Feature Store
**Goal**: Validated Parquet in silver ✅; ML-ready feature tables in gold ⬜

### Tasks

#### 3.1 Silver — Orders (Source 1) ✅
- [x] `src/pipeline/silver/glue_orders_silver.py` — type casting, dedup, null filter + quarantine, domain validation
- [x] `tests/unit/test_silver_transforms.py` — 5 PySpark unit tests
- [x] `nextcart-dev-orders-silver` Glue job ran successfully → Parquet in `s3://.../silver/orders/`

#### 3.2 Silver — Products (Source 2) ✅
- [x] `src/pipeline/silver/glue_products_silver.py` — denormalised join, name normalisation
- [x] `nextcart-dev-products-silver` Glue job ran successfully → Parquet in `s3://.../silver/products/`

#### 3.3 Silver — Clickstream (Source 3) ⏸ Paused
- Deferred along with Source 3.

#### 3.4 EMR Cluster ⬜
- [ ] Write `infra/terraform/modules/emr/` — single-node `m5.xlarge`, auto-terminate after job
- [ ] Wire EMR module into `environments/dev/main.tf`
- [ ] Test: submit a simple PySpark job to verify EMR connectivity

#### 3.5 Gold — Task A Features (Reorder Prediction) ⬜
- [ ] Write `src/pipeline/gold/reorder_features.py` (PySpark on EMR)
  - [ ] Join: orders + order_products_prior + products (cross-source join via silver)
  - [ ] Features: `user_product_reorder_rate`, `days_since_last_purchase`, `user_avg_order_size`, `product_global_reorder_rate`, `add_to_cart_order_mean`, `order_dow`, `order_hour_of_day`, `is_organic`, `department_encoded`, `aisle_encoded`
  - [ ] Label: `reordered` from `order_products_train`
  - [ ] Output: `s3://.../gold/reorder_features/` Parquet

#### 3.6 Gold — Task B Features (Recommendation) ⬜
- [ ] Write `src/pipeline/gold/recommendation_features.py` (PySpark on EMR)
  - [ ] Build `user_id × product_id` interaction matrix (implicit purchase count)
  - [ ] TF-IDF product content vectors (name + department + aisle)
  - [ ] Output: `s3://.../gold/interaction_matrix/` + `s3://.../gold/product_vectors/`

#### 3.7 Data Quality Gate ⬜
- [ ] Write `src/monitoring/data_quality_checks.py`
  - [ ] Bronze → Silver: null rate threshold, schema conformance
  - [ ] Silver → Gold: join cardinality check
- [ ] Wire Great Expectations into `tests/data_quality/`

**Week 3 Exit Criteria**:
- Silver Parquet for orders + products passes data quality checks ✅ (quarantine writes in place)
- Gold feature table for Task A has all features populated ⬜
- Gold interaction matrix for Task B is non-empty ⬜
- EMR job submits and completes without error ⬜

---

## Week 4 — Task A Models (XGBoost Baseline → LightGBM)

**Theme**: Train-test split · XGBoost baseline · LightGBM primary · Model Registry
**Goal**: LightGBM model with F1 ≥ 0.38 registered in SageMaker Model Registry.

### Tasks

#### 4.1 Train/Test Split Strategy
- [ ] Define split: use `eval_set = 'train'` orders as test labels; prior orders as training data
- [ ] Write `src/ml/reorder/prepare_dataset.py` — load gold, 80/20 stratified split, save to S3

#### 4.2 XGBoost Baseline (Phase 1)
- [ ] Write `src/ml/reorder/train_xgboost.py`
  - [ ] XGBoost binary classifier (`eval_metric: logloss`)
  - [ ] Log: F1, precision, recall, AUC
  - [ ] SHAP: top 10 features by importance
- [ ] Document baseline F1 in Results Log

#### 4.3 SageMaker Setup
- [ ] Write `infra/terraform/modules/sagemaker/` — Model Registry, Training Job IAM role
- [ ] Verify Training Job runs end-to-end in dev account

#### 4.4 LightGBM Primary (Phase 2)
- [ ] Write `src/ml/reorder/train_lightgbm.py`
  - [ ] `num_leaves=63`, `learning_rate=0.05`, `min_data_in_leaf=20`
  - [ ] Same features as XGBoost for fair comparison
- [ ] Write `src/ml/reorder/evaluate.py` — F1, PR curve, SHAP, confusion matrix

#### 4.5 Model Registry
- [ ] Register both models in SageMaker Model Registry
- [ ] Set LightGBM as champion if F1 > XGBoost
- [ ] Write `src/ml/reorder/hpo_config.py` — search space for Week 6

#### 4.6 A/B Comparison
- [ ] LightGBM vs XGBoost F1/AUC/training time
- [ ] Confirm multi-source features lift F1 vs Source 1 only

**Week 4 Exit Criteria**:
- XGBoost baseline F1 documented
- LightGBM F1 ≥ XGBoost on same test set
- Both models in SageMaker Model Registry
- Source 2 features demonstrably improve F1

---

## Week 5 — Task B Models + CD Pipeline

**Theme**: ALS · Content-Based Hybrid · Recommendation serving · CD prod deployment

### Tasks

#### 5.1 ALS Collaborative Filtering
- [ ] Write `src/ml/recommendation/train_als.py` (PySpark MLlib on EMR)
  - [ ] `rank=50`, `maxIter=20`, `regParam=0.1`, `alpha=40`
  - [ ] Top-20 recommendations per user → S3

#### 5.2 Content-Based Filtering
- [ ] Write `src/ml/recommendation/content_based.py` — cosine similarity on product vectors

#### 5.3 Hybrid Model
- [ ] Write `src/ml/recommendation/hybrid.py`
  - [ ] `score = α × ALS + (1-α) × content` (α=0.7); cold-start fallback if user < 5 orders

#### 5.4 Recommendation Serving API
- [ ] Write `src/serving/recommendation_handler.py` — Lambda `GET /recommend?user_id=&k=10`
- [ ] Write `infra/terraform/modules/api_gateway/` — recommendation API GW

#### 5.5 CD Pipeline
- [ ] Test full cycle: push to develop → deploy-dev auto-runs → dev environment updated
- [ ] Test prod gate: push to main → manual approval required → tf apply prod

#### 5.6 Step Functions Orchestration
- [ ] Write `infra/terraform/modules/step_functions/` — pipeline DAG (bronze → silver → gold → train)

**Week 5 Exit Criteria**:
- ALS Precision@10 measured
- `GET /recommend?user_id=1&k=10` returns results from staging
- CD deploys to dev automatically; prod gate blocks without approval

---

## Week 6 — HPO · Model Monitor · Evaluation · Documentation

**Theme**: SageMaker HPO · data drift monitoring · final metrics · report

### Tasks

#### 6.1 SageMaker HPO (Task A — LightGBM)
- [ ] `HyperparameterTuner`: `num_leaves` [31–127], `learning_rate` [0.01–0.1], `min_data_in_leaf` [10–50]
- [ ] Max 20 jobs, parallel 4; objective: maximise F1

#### 6.2 Model Monitor
- [ ] Write `src/monitoring/model_drift_monitor.py` — baseline stats + daily drift schedule
- [ ] CloudWatch alert → SNS → email if drift > threshold

#### 6.3 Final Evaluation
- [ ] Task A: XGBoost vs LightGBM vs LightGBM+HPO; Source 1 only vs 1+2 ablation
- [ ] Task B: ALS vs Content-Based vs Hybrid; Precision@10, Recall@10, NDCG@10

#### 6.4 End-to-End Validation
- [ ] Run full Step Functions pipeline from scratch
- [ ] Verify CI green + CD deploys cleanly to prod

#### 6.5 Documentation
- [ ] `README.md` — architecture diagram, how to run, results summary
- [ ] `docs/architecture.md` — detailed data flow diagram
- [ ] `notebooks/04_final_report.ipynb` — final evaluation report

**Week 6 Exit Criteria**:
- LightGBM post-HPO F1 ≥ 0.38
- Recommendation Precision@10 ≥ 0.30
- Multi-source lift ≥ +5% F1 documented
- Full pipeline end-to-end in prod

---

## Results Log

### Task A — Reorder Prediction

| Date | Model | Features | F1 | Precision | Recall | AUC | Notes |
|------|-------|----------|----|-----------|---------|----|-------|
| — | XGBoost (baseline) | Source 1 only | — | — | — | — | Phase 1 baseline |
| — | LightGBM | Source 1 only | — | — | — | — | A/B comparison |
| — | LightGBM | Source 1+2 | — | — | — | — | Primary model |
| — | LightGBM+HPO | Source 1+2 | — | — | — | — | After Week 6 tuning |

### Task B — Product Recommendation

| Date | Model | Precision@10 | Recall@10 | NDCG@10 | Notes |
|------|-------|-------------|----------|--------|-------|
| — | Frequency baseline | — | — | — | Most bought items globally |
| — | ALS only | — | — | — | PySpark MLlib |
| — | Content-Based only | — | — | — | Cosine similarity |
| — | Hybrid (ALS + CB) | — | — | — | α=0.7 default |

---

## Architecture Decisions Log

| Date | Decision | Alternatives Considered | Reason |
|------|---------|------------------------|--------|
| 2026-04-29 | Source 2 sits behind FastAPI (not direct DB access) | Direct RDS query | Enforces clean boundary; may move to real external API later |
| 2026-04-29 | Batch-first (no Kinesis for Source 1/2) | Full streaming | Two of three sources are batch; streaming adds complexity without value |
| 2026-04-29 | Terraform over AWS CDK | CDK, CloudFormation | Team more comfortable with HCL; mature ecosystem |
| 2026-04-29 | LightGBM as primary over XGBoost | XGBoost, CatBoost | Kaggle evidence; 3–5× faster training |
| 2026-04-29 | Implicit ALS over explicit | Explicit ALS, Neural CF | Purchase data is implicit feedback |
| 2026-04-29 | Source 3 (Kinesis) deferred | Implement now | Two core sources deliver the ML features; streaming adds risk |
| 2026-04-29 | FastAPI as Lambda+Mangum | ECS Fargate | Simpler infra, no ECS/ALB costs, adequate for batch API calls |
| 2026-04-29 | Glue JDBC for Source 1 bronze | Lambda with psycopg2 | Glue handles 32M+ rows; Lambda 15-min timeout risky |
| 2026-04-30 | Lambda layer uploaded to S3 (not direct) | Direct upload | Layer zip >50 MB exceeds Lambda direct-upload limit |
| 2026-04-30 | `spark.read.jdbc` with explicit bounds | Glue DynamicFrame hashfield | Glue hashpartitions crashes with `empty.reduceLeft` when using direct credentials |
| 2026-04-30 | Fetch Secrets Manager secret via boto3 in script | JDBC SECRET_ID property | `SECRET_ID` in connection_properties does NOT auto-inject credentials into JDBC URL |
| 2026-04-30 | Secrets Manager VPC interface endpoint | NAT Gateway | Interface endpoint is free for private-subnet access; avoids NAT cost |
| 2026-04-30 | RDS publicly_accessible=true in dev | Private subnet only | Allows direct data loading from local machine without bastion host |

---

## Blockers & Issues

| # | Blocker | Owner | Raised | Resolved | Notes |
|---|---------|-------|--------|----------|-------|
| — | — | — | — | — | — |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| EMR costs exceed budget in dev | Medium | Low | Auto-terminate; single-node `m5.xlarge`; run only for gold step |
| ALS cold-start degrades Precision@10 below threshold | Medium | High | Content-Based fallback in hybrid model |
| SageMaker Training Job takes > 1h on full dataset | Low | Medium | Subsample to 500K orders for dev; full data in final prod run |
| Gold join cardinality explosion (32M × products) | Medium | Medium | Broadcast join products table (small); partition by user_id |
