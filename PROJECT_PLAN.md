# NextCart — Project Plan

**Status**: 🔵 In Progress — Week 1 + Week 2 code complete, pending deployment
**Last Updated**: 2026-04-29
**Team Size**: 3
**Duration**: 6 Weeks (Week 1 starts on project kick-off date)

---

## Quick Status Dashboard

| Area | Status | Owner | Notes |
|------|--------|-------|-------|
| AWS Environment | 🔵 In Progress | — | Terraform modules written; pending `terraform apply` |
| CI/CD Scaffold | ✅ Done | — | 3 GitHub Actions workflows written |
| Source 1 — RDS Orders | 🔵 In Progress | — | Loader script done; pending RDS deployment |
| Source 2 — Product API | 🔵 In Progress | — | FastAPI + Lambda + API GW written; pending deploy |
| Source 3 — Kinesis Simulator | ⏸ Paused | — | Deferred — not in current scope |
| Bronze Pipeline | 🔵 In Progress | — | Glue script (S1) + Lambda handler (S2) written |
| Silver Pipeline | 🔵 In Progress | — | Glue ETL scripts for orders + products written |
| Gold / Feature Engineering | ⬜ Not Started | — | EMR PySpark cross-source join |
| Task A — XGBoost Baseline | ⬜ Not Started | — | F1 baseline |
| Task A — LightGBM | ⬜ Not Started | — | F1 ≥ 0.38 |
| Task B — ALS | ⬜ Not Started | — | Precision@10 |
| Task B — Hybrid | ⬜ Not Started | — | ALS + Content-Based |
| CD Pipeline (Prod Deploy) | ⬜ Not Started | — | Manual approval gate |
| HPO + Model Monitor | ⬜ Not Started | — | SageMaker Tuning Job |
| Final Report | ⬜ Not Started | — | — |

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
| CI test coverage (src/pipeline + src/ml) | ≥ 80% | — |

### Task B — Product Recommendation
> Platform misses upsell opportunities mid-session due to no recommendation mechanism.

| Metric | Minimum | Target |
|--------|---------|--------|
| Precision@10 | ≥ 0.30 | — |
| Recall@10 | Measured | — |
| Cold-start coverage (Content-Based fallback) | Measured | — |

### Engineering
- All 3 data sources flowing into S3 Medallion lake
- Full IaC via Terraform (dev + prod environments)
- CI runs on every PR; CD deploys to dev automatically
- Prod deploy requires manual approval gate

---

## Week 1 — Foundation

**Theme**: EDA · AWS environment · Terraform base · CI scaffold
**Goal**: Team can push code, CI runs, dev AWS account has basic infra.

### Tasks

#### 1.1 EDA & Data Understanding
- [ ] Load all 6 CSVs locally, run shape/dtypes/null analysis
- [ ] Document key statistics: order count, reorder rate, product long-tail distribution
- [ ] Identify join keys across the 6 files (product_id, order_id, user_id)
- [ ] Create `data/samples/` — 1,000-row subsets of orders + products for CI use
- [ ] Commit EDA findings to `notebooks/01_eda.ipynb`

#### 1.2 AWS Environment
- [x] Configure GitHub Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- [ ] Create Terraform state S3 bucket + DynamoDB lock table → see `docs/deployment_guide.md` Phase 0
- [ ] Verify AWS CLI access: `aws sts get-caller-identity`
- [ ] Run `terraform init -backend-config=backend.tfvars` and confirm no errors

#### 1.3 Terraform Base ✅ Code Written
- [x] `infra/terraform/backend.tf` — S3 state + DynamoDB lock config
- [x] `infra/terraform/versions.tf` — AWS provider ~5.0, Terraform ~1.7
- [x] `infra/terraform/modules/vpc/` — VPC, subnets, security groups, S3 VPC endpoint
- [x] `infra/terraform/modules/s3/` — lake bucket with bronze/silver/gold/quarantine zones
- [x] `infra/terraform/modules/iam/` — Lambda, Glue, EMR roles and policies
- [x] `infra/terraform/modules/rds/` — parameterised RDS module (used for orders + products)
- [x] `infra/terraform/modules/lambda/` — Source2 API + Bronze extractor + API Gateway
- [x] `infra/terraform/modules/glue/` — JDBC connection, crawlers, ETL jobs
- [x] `infra/terraform/environments/dev/main.tf` — wires all modules
- [ ] `terraform apply` succeeds end-to-end in dev account

#### 1.4 GitHub Actions — CI Scaffold ✅ Done
- [x] `.github/workflows/ci.yml` — lint + unit tests + tf validate
- [x] `.github/workflows/deploy-dev.yml` — auto-deploy on push to develop
- [x] `.github/workflows/deploy-prod.yml` — gated prod deploy
- [x] `pyproject.toml` — black/flake8/pytest/mypy config
- [x] `requirements-dev.txt` — full dev dependencies
- [x] `Makefile` — all common commands
- [ ] Confirm CI workflow green on a test PR (needs GitHub repo setup)

#### 1.5 Repository Setup ✅ Done
- [x] `.gitignore` — data/raw/, .terraform/, *.tfstate, .env
- [x] Full directory skeleton with `__init__.py` files
- [ ] Push to GitHub and confirm team members can clone + `make install` + `make test`

**Week 1 Exit Criteria**:
- `terraform plan` on dev environment succeeds
- CI pipeline goes green on a dummy PR
- All team members have working local environment
- EDA notebook committed with key findings documented

---

## Week 2 — Data Ingestion (All 3 Sources → Bronze)

**Theme**: RDS loaders · Product API · Kinesis simulator · Bronze pipeline
**Goal**: All 3 sources are flowing raw data into S3 bronze zone.

### Tasks

#### 2.1 Source 1 — Orders RDS ✅ Code Written
- [x] `infra/terraform/modules/rds/` — parameterised PostgreSQL RDS module
- [x] `nextcart-dev-rds-orders` wired in `environments/dev/main.tf`
- [x] `src/ingestion/source1/load_orders_to_rds.py`
  - [x] Loads orders → order_products_prior → order_products_train
  - [x] `--env local/dev` flag + `--sample` flag for 1000-row test load
  - [x] Chunked insert (50K rows/batch) with ON CONFLICT DO NOTHING
- [ ] Run `make load-source1` against dev RDS (see deployment_guide.md Phase 3)

#### 2.2 Source 2 — Products RDS + FastAPI ✅ Code Written
- [x] `nextcart-dev-rds-products` RDS wired in Terraform
- [x] `src/ingestion/source2/load_products_to_rds.py` — loads departments → aisles → products
- [x] `src/ingestion/source2/api/database.py` — SQLAlchemy + Secrets Manager
- [x] `src/ingestion/source2/api/models.py` — ORM models (Product, Aisle, Department)
- [x] `src/ingestion/source2/api/schemas.py` — Pydantic response schemas
- [x] `src/ingestion/source2/api/main.py` — FastAPI + Mangum Lambda adapter
- [x] `src/ingestion/source2/api/Dockerfile` + `docker-compose.yml`
- [x] `tests/unit/test_api_models.py` — 6 unit tests, no DB required
- [x] Lambda + API Gateway deployed via Terraform modules
- [ ] `make api-up` local test → verify all 5 endpoints respond
- [ ] Invoke Lambda in AWS: `curl ${SOURCE2_API_URL}/health`

#### 2.3 Source 3 — Kinesis Simulator ⏸ Paused
- Deferred per scope decision. Will revisit in Week 5 if time permits.

#### 2.4 Bronze Pipeline ✅ Code Written
- [x] `src/pipeline/bronze/glue_source1_bronze.py` — Glue JDBC job, reads 3 RDS tables → S3 bronze
- [x] `src/pipeline/bronze/lambda_source2_bronze.py` — Lambda, paginates Product API → S3 bronze
- [x] Glue job + Lambda wired in Terraform (`modules/glue/` + `modules/lambda/`)
- [ ] Run Source 1 bronze Glue job (see deployment_guide.md Phase 5.1)
- [ ] Invoke Source 2 bronze Lambda (see deployment_guide.md Phase 5.2)
- [ ] Verify S3 bronze zone has Parquet files from both sources

**Week 2 Exit Criteria**:
- `make load-source1` and `make load-source2` work end-to-end
- `make api-up` starts FastAPI locally; `GET /products` returns data
- `make simulate-stream --duration 30` writes events (locally or to Kinesis)
- S3 bronze zone contains all 3 data sources in raw form

---

## Week 3 — Silver + Gold (EMR PySpark Feature Engineering)

**Theme**: Data quality · Silver transforms · EMR cross-source joins · Feature Store
**Goal**: Validated Parquet in silver; ML-ready feature tables in gold.

### Tasks

#### 3.1 Silver — Orders (Source 1) ✅ Code Written
- [x] `src/pipeline/silver/glue_orders_silver.py` — Glue ETL job
  - [x] Type casting for all columns
  - [x] Deduplication on `order_id`
  - [x] Null filter + quarantine write for bad rows
  - [x] Domain validation: `order_dow` 0-6, `reordered` ∈ {0,1}
  - [x] Output: `s3://…/silver/orders/` Parquet, partitioned by `eval_set`
- [x] `tests/unit/test_silver_transforms.py` — 5 PySpark unit tests
- [ ] Run `nextcart-dev-orders-silver` Glue job (see deployment_guide.md Phase 7)

#### 3.2 Silver — Products (Source 2) ✅ Code Written
- [x] `src/pipeline/silver/glue_products_silver.py` — Glue ETL job
  - [x] Join products + aisles + departments into denormalised table
  - [x] Product name normalisation (lowercase, strip whitespace)
  - [x] Null join coverage warning
  - [x] Output: `s3://…/silver/products/` Parquet, partitioned by `department_id`
- [ ] Run `nextcart-dev-products-silver` Glue job (see deployment_guide.md Phase 7)

#### 3.3 Silver — Clickstream (Source 3)
- [ ] Write `src/pipeline/silver/clickstream_silver.py`
  - [ ] Parse JSON events, validate schema (event_type enum check)
  - [ ] Sessionise: group by `user_id + session_id`, compute session duration
  - [ ] Output: `s3://…/silver/clickstream/` Parquet, partitioned by `year/month/day`

#### 3.4 EMR Cluster
- [ ] Write `infra/terraform/modules/emr/` — single-node `m5.xlarge` dev cluster, auto-terminate
- [ ] Configure PySpark job submission via Step Functions
- [ ] Test: submit a simple word-count PySpark job to verify EMR connectivity

#### 3.5 Gold — Task A Features (Reorder Prediction)
- [ ] Write `src/pipeline/gold/reorder_features.py` (PySpark on EMR)
  - [ ] Join: orders + order_products_prior + products (cross-source join)
  - [ ] Compute features:
    - `user_product_reorder_rate`: # times user bought product / # times user ordered
    - `days_since_last_purchase`: latest `days_since_prior_order` for user-product pair
    - `user_avg_order_size`: mean items per order per user
    - `product_global_reorder_rate`: global reorder rate for each product
    - `add_to_cart_order_mean`: average cart position for product (proxy for habit)
    - `order_dow`, `order_hour_of_day`: time-based features
    - `is_organic`, `department_encoded`, `aisle_encoded`: from Source 2 join
    - `session_view_count`, `view_to_purchase_ratio`: from Source 3 clickstream join
  - [ ] Label: `reordered` from `order_products_train` (test set for model eval)
  - [ ] Output: `s3://…/gold/reorder_features/` Parquet

#### 3.6 Gold — Task B Features (Recommendation)
- [ ] Write `src/pipeline/gold/recommendation_features.py` (PySpark on EMR)
  - [ ] Build `user_id × product_id` interaction matrix (implicit purchase count)
  - [ ] Compute product content vectors: TF-IDF on product name + department + aisle
  - [ ] Output: `s3://…/gold/interaction_matrix/` + `s3://…/gold/product_vectors/`

#### 3.7 Data Quality Gate
- [ ] Write `src/monitoring/data_quality_checks.py`
  - [ ] Bronze → Silver: null rate threshold, schema conformance
  - [ ] Silver → Gold: join cardinality check (no unexpected row explosion)
  - [ ] Failed records written to `s3://…/quarantine/` with rejection reason tag
- [ ] Wire Great Expectations into `tests/data_quality/`

**Week 3 Exit Criteria**:
- Silver Parquet for all 3 sources passes Great Expectations suites
- Gold feature table for Task A has all 12 features populated
- Gold interaction matrix for Task B is non-empty
- EMR job submits and completes without error

---

## Week 4 — Task A Models (XGBoost Baseline → LightGBM)

**Theme**: Train-test split · XGBoost baseline · LightGBM primary · Model Registry
**Goal**: LightGBM model with F1 ≥ 0.38 registered in SageMaker Model Registry.

### Tasks

#### 4.1 Train/Test Split Strategy
- [ ] Define split: use `eval_set = 'train'` orders as test labels; prior orders as training data
- [ ] Write `src/ml/reorder/prepare_dataset.py`
  - [ ] Load gold features from S3
  - [ ] Split: 80% train / 20% validation (stratified by user)
  - [ ] Save train/val/test splits to `s3://…/gold/ml_splits/`

#### 4.2 XGBoost Baseline (Phase 1)
- [ ] Write `src/ml/reorder/train_xgboost.py`
  - [ ] Load features from S3 (or local sample with `--env local`)
  - [ ] Train XGBoost binary classifier (`eval_metric: logloss`)
  - [ ] Log: F1, precision, recall, AUC to SageMaker Experiments (or MLflow locally)
  - [ ] Save model artifact to S3
- [ ] Run SHAP analysis: top 10 features by importance
- [ ] Document baseline F1 in this file (section: Results Log)

#### 4.3 SageMaker Setup
- [ ] Write `infra/terraform/modules/sagemaker/` — Model Registry, Training Job IAM role
- [ ] Write SageMaker Training Job config for XGBoost (built-in container)
- [ ] Verify Training Job runs end-to-end in dev account

#### 4.4 LightGBM Primary (Phase 2)
- [ ] Write `src/ml/reorder/train_lightgbm.py`
  - [ ] LightGBM binary classifier, `metric: binary_logloss`
  - [ ] Hyperparameters (initial): `num_leaves=63`, `learning_rate=0.05`, `min_data_in_leaf=20`
  - [ ] Same feature set as XGBoost for fair comparison
  - [ ] Log metrics to SageMaker Experiments
- [ ] Write `src/ml/reorder/evaluate.py`
  - [ ] F1 at threshold 0.5
  - [ ] Precision-recall curve (find optimal threshold)
  - [ ] SHAP summary plot saved to S3
  - [ ] Confusion matrix

#### 4.5 Model Registry
- [ ] Register XGBoost and LightGBM models in SageMaker Model Registry
- [ ] Set LightGBM as champion if F1 > XGBoost F1
- [ ] Write `src/ml/reorder/hpo_config.py` — search space for Week 6 HPO:
  - `num_leaves`: [31, 127], `learning_rate`: [0.01, 0.1], `min_data_in_leaf`: [10, 50]

#### 4.6 A/B Comparison
- [ ] Write comparison report: LightGBM vs XGBoost F1/AUC/training time
- [ ] Confirm multi-source features (Source 2 + 3) lift F1 vs Source 1 only

**Week 4 Exit Criteria**:
- XGBoost baseline F1 documented (expected ~0.38–0.40)
- LightGBM F1 ≥ XGBoost F1 on same test set
- Both models registered in SageMaker Model Registry
- Source 2 + 3 features demonstrably improve F1 over Source 1 only

---

## Week 5 — Task B Models + CD Pipeline

**Theme**: ALS · Content-Based Hybrid · Recommendation serving · CD prod deployment
**Goal**: Recommendation API live in staging; CD pipeline deploys to prod with approval gate.

### Tasks

#### 5.1 ALS Collaborative Filtering (Phase 2)
- [ ] Write `src/ml/recommendation/train_als.py` (PySpark MLlib on EMR)
  - [ ] Load interaction matrix from `s3://…/gold/interaction_matrix/`
  - [ ] Train implicit ALS: `rank=50`, `maxIter=20`, `regParam=0.1`, `alpha=40`
  - [ ] Generate Top-20 recommendations per user
  - [ ] Save: user factors, item factors, Top-K table to S3
- [ ] Write `src/ml/recommendation/evaluate.py`
  - [ ] Precision@10, Recall@10, NDCG@10
  - [ ] Use held-out last order per user as ground truth

#### 5.2 Content-Based Filtering
- [ ] Write `src/ml/recommendation/content_based.py`
  - [ ] Load product vectors from `s3://…/gold/product_vectors/`
  - [ ] Compute cosine similarity matrix (top-50 similar items per product)
  - [ ] Serve: given a product, return N most similar products
  - [ ] Cache similarity matrix in S3

#### 5.3 Hybrid Model
- [ ] Write `src/ml/recommendation/hybrid.py`
  - [ ] Weighted merge: `score = α × ALS_score + (1-α) × content_score` (α = 0.7 default)
  - [ ] Cold-start fallback: if user has < 5 orders → use content-based only
  - [ ] Output: unified Top-K list per user

#### 5.4 Recommendation Serving API
- [ ] Write `src/serving/recommendation_handler.py` (AWS Lambda)
  - [ ] `GET /recommend?user_id={id}&k=10`
  - [ ] Loads pre-computed Top-K from S3/DynamoDB cache
  - [ ] Response: `{ user_id, recommendations: [{product_id, score, source}] }`
- [ ] Write `infra/terraform/modules/api_gateway/` — API Gateway → Lambda
- [ ] Deploy to staging endpoint; run smoke test

#### 5.5 CD Pipeline (GitHub Actions)
- [ ] Write `.github/workflows/deploy-dev.yml`
  - [ ] Trigger: push to `develop`
  - [ ] Steps: tf apply dev → glue/lambda sync → smoke test
- [ ] Write `.github/workflows/deploy-prod.yml`
  - [ ] Trigger: push to `main`
  - [ ] Steps: tf plan → **manual approval gate** (GitHub Environment "production") → tf apply
  - [ ] Model promotion gate: new model must beat registry champion
- [ ] Test the full CD cycle: push dummy change to develop → verify auto-deploy succeeds

#### 5.6 Step Functions Orchestration
- [ ] Write `infra/terraform/modules/step_functions/` — full pipeline DAG
  - [ ] Bronze ingestion (parallel: source1, source2, source3)
  - [ ] Silver transforms (parallel after bronze)
  - [ ] Gold feature engineering (after silver)
  - [ ] ML Training Jobs (after gold)
- [ ] Trigger Step Functions execution manually; confirm all states succeed

**Week 5 Exit Criteria**:
- ALS model produces Top-10 recommendations with Precision@10 measured
- Hybrid model improves on cold-start coverage vs ALS alone
- `GET /recommend?user_id=1&k=10` returns results from staging API
- CD pipeline deploys to dev automatically on push; prod gate blocks without approval

---

## Week 6 — HPO · Model Monitor · Evaluation · Documentation

**Theme**: SageMaker HPO · data drift monitoring · final metrics · report
**Goal**: Deliver polished, production-grade system with documented results.

### Tasks

#### 6.1 SageMaker HPO (Task A — LightGBM)
- [ ] Submit `HyperparameterTuner` job using config from `src/ml/reorder/hpo_config.py`
  - [ ] Search space: `num_leaves` [31–127], `learning_rate` [0.01–0.1], `min_data_in_leaf` [10–50]
  - [ ] Max jobs: 20, parallel: 4
  - [ ] Objective: maximise F1 on validation set
- [ ] Register winning HPO model as new champion if F1 improves
- [ ] Document final F1 with optimal hyperparameters

#### 6.2 Model Monitor
- [ ] Write `src/monitoring/model_drift_monitor.py`
  - [ ] Baseline statistics from training data (feature distributions)
  - [ ] SageMaker Model Monitor schedule: daily drift check
  - [ ] CloudWatch alert if feature drift > threshold
- [ ] Wire alert to SNS topic → email notification

#### 6.3 Final Evaluation
- [ ] Task A: Final F1, precision, recall on held-out test set
  - [ ] Compare: XGBoost baseline vs LightGBM vs LightGBM+HPO
  - [ ] Compare: Source 1 only vs Source 1+2 vs Source 1+2+3 (feature ablation)
- [ ] Task B: Final Precision@10, Recall@10, NDCG@10
  - [ ] Compare: ALS only vs Content-Based only vs Hybrid
- [ ] Produce final comparison tables for report

#### 6.4 End-to-End Validation
- [ ] Run full Step Functions pipeline from scratch (bronze → silver → gold → training)
- [ ] Verify CI is green (all unit tests pass, coverage ≥ 80%)
- [ ] Verify CD deploys cleanly to prod (with manual approval)
- [ ] Verify rollback path: redeploy previous Model Registry version

#### 6.5 Documentation
- [ ] Update `README.md` (architecture diagram, how to run, results summary)
- [ ] Write `docs/architecture.md` (detailed data flow diagram)
- [ ] Write final evaluation report (can be a notebook `notebooks/04_final_report.ipynb`)
- [ ] Record demo: pipeline run + recommendation API call

**Week 6 Exit Criteria**:
- LightGBM post-HPO F1 ≥ 0.38 (target ~0.40+)
- Recommendation Precision@10 ≥ 0.30
- Multi-source feature lift ≥ +5% F1 vs single-source documented
- Full pipeline runs end-to-end in prod without manual intervention
- All documentation complete

---

## Results Log

> Update this section as models are trained. Record the exact run date, config, and metrics.

### Task A — Reorder Prediction

| Date | Model | Features | F1 | Precision | Recall | AUC | Notes |
|------|-------|----------|----|-----------|---------|----|-------|
| — | XGBoost (baseline) | Source 1 only | — | — | — | — | Phase 1 baseline |
| — | LightGBM | Source 1 only | — | — | — | — | A/B comparison |
| — | LightGBM | Source 1+2+3 | — | — | — | — | Primary model |
| — | LightGBM+HPO | Source 1+2+3 | — | — | — | — | After Week 6 tuning |

### Task B — Product Recommendation

| Date | Model | Precision@10 | Recall@10 | NDCG@10 | Notes |
|------|-------|-------------|----------|--------|-------|
| — | Frequency baseline | — | — | — | Most bought items globally |
| — | ALS only | — | — | — | PySpark MLlib |
| — | Content-Based only | — | — | — | Cosine similarity |
| — | Hybrid (ALS + CB) | — | — | — | α=0.7 default |

---

## Architecture Decisions Log

> Record non-obvious decisions so future team members understand why.

| Date | Decision | Alternatives Considered | Reason |
|------|---------|------------------------|--------|
| 2026-04-29 | Source 2 sits behind FastAPI (not direct DB access from ML) | Direct RDS query | Enforces clean boundary; Source 2 may later move to real external API |
| 2026-04-29 | Batch-first (no Kinesis for Source 1/2) | Full streaming with Kinesis | Two of three sources are batch; forcing stream adds complexity without value |
| 2026-04-29 | Terraform over AWS CDK | CDK (TypeScript), CloudFormation | Team more comfortable with HCL; Terraform ecosystem mature for multi-cloud |
| 2026-04-29 | LightGBM as primary over XGBoost | XGBoost, CatBoost, Neural net | Kaggle leaderboard evidence; 3–5× faster training; SageMaker container available |
| 2026-04-29 | Implicit ALS over explicit | Explicit ALS, Neural CF | Purchase data is implicit feedback (no explicit ratings); standard choice |
| 2026-04-29 | Source 3 (Kinesis) deferred | Implement now | Two core sources (RDS + API) deliver the ML features; streaming adds risk without near-term payoff |
| 2026-04-29 | FastAPI deployed as Lambda+Mangum | ECS Fargate | Simpler infra, no ECS/ALB costs, adequate for batch API calls; no persistent endpoint needed |
| 2026-04-29 | Glue JDBC for Source 1 bronze (not Lambda) | Lambda with psycopg2 | Glue handles 32M+ rows efficiently; Lambda 15-min timeout would be risky for order_products_prior |

---

## Blockers & Issues

> Add blockers here as they arise. Remove when resolved.

| # | Blocker | Owner | Raised | Resolved | Notes |
|---|---------|-------|--------|----------|-------|
| — | — | — | — | — | — |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Source 2 API data quality poor (missing prices, categories) | Medium | Medium | Use simulated/enriched data from CSV; note gap in report |
| EMR costs exceed budget in dev | Medium | Low | Auto-terminate cluster; use `m5.xlarge` single-node; run only for gold step |
| ALS cold-start degrades Precision@10 below threshold | Medium | High | Content-Based fallback already planned in hybrid model |
| SageMaker Training Job takes > 1h on full dataset | Low | Medium | Subsample to 500K orders for dev runs; use full data only in final prod run |
| CI coverage drops below 80% | Low | Low | Track coverage per PR; flag regressions in GitHub Actions output |

---

## Team Assignments (Template)

> Fill in actual names when assigned.

| Module | Primary | Reviewer |
|--------|---------|---------|
| Terraform infra (RDS, S3, Kinesis) | TBD | TBD |
| Source 1 + 2 RDS loaders | TBD | TBD |
| Source 2 FastAPI | TBD | TBD |
| Source 3 Kinesis simulator | TBD | TBD |
| Bronze pipeline (all 3 sources) | TBD | TBD |
| Silver transforms + Great Expectations | TBD | TBD |
| Gold feature engineering (EMR) | TBD | TBD |
| Task A — XGBoost + LightGBM | TBD | TBD |
| Task B — ALS + Hybrid | TBD | TBD |
| Recommendation serving API | TBD | TBD |
| CI/CD GitHub Actions | TBD | TBD |
| Model Monitor + CloudWatch | TBD | TBD |
| Final report + documentation | TBD | TBD |
