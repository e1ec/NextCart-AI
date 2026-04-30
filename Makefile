.PHONY: install lint format test test-all generate-samples \
        tf-init-dev tf-plan-dev tf-apply-dev \
        load-source1 load-source2 api-up simulate-stream \
        run-bronze run-silver run-gold \
        train-xgboost train-lightgbm train-als

# ── Environment ──────────────────────────────────────────────
install:
	pip install -r requirements-dev.txt
	pre-commit install

# ── Code Quality ─────────────────────────────────────────────
lint:
	flake8 src/ tests/
	black --check src/ tests/

format:
	black src/ tests/

# ── Tests ────────────────────────────────────────────────────
test:
	pytest tests/unit/ tests/data_quality/ -v -m "not integration"

test-all:
	pytest tests/ -v

# ── Sample Data ──────────────────────────────────────────────
generate-samples:
	python scripts/generate_samples.py

# ── Terraform (Dev) ──────────────────────────────────────────
tf-init-dev:
	terraform -chdir=infra/terraform/environments/dev init

tf-plan-dev:
	terraform -chdir=infra/terraform/environments/dev plan

tf-apply-dev:
	terraform -chdir=infra/terraform/environments/dev apply -auto-approve

# ── Data Ingestion ───────────────────────────────────────────
load-source1:
	python src/ingestion/source1/load_orders_to_rds.py --env local --sample

load-source2:
	python src/ingestion/source2/load_products_to_rds.py --env local --sample

api-up:
	docker-compose -f src/ingestion/source2/api/docker-compose.yml up

simulate-stream:
	python src/ingestion/source3/clickstream_simulator.py --duration 60 --rate 5 --env local

# ── Pipeline ─────────────────────────────────────────────────
run-bronze:
	python src/pipeline/bronze/rds_source1_to_s3.py --env local
	python src/pipeline/bronze/api_source2_to_s3.py --env local
	python src/pipeline/bronze/kinesis_to_s3.py --env local

run-silver:
	python src/pipeline/silver/orders_silver.py --env local
	python src/pipeline/silver/products_silver.py --env local
	python src/pipeline/silver/clickstream_silver.py --env local

run-gold:
	python src/pipeline/gold/reorder_features.py --env local
	python src/pipeline/gold/recommendation_features.py --env local

# ── ML Training ──────────────────────────────────────────────
train-xgboost:
	python src/ml/reorder/train_xgboost.py --env local

train-lightgbm:
	python src/ml/reorder/train_lightgbm.py --env local

train-als:
	python src/ml/recommendation/train_als.py --env local
