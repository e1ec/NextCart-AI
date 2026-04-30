# NextCart — Deployment Operations Manual
**Covers: Week 1 + Week 2 (Source 1 + Source 2, excluding Source 3 Kinesis)**

---

## 在哪里运行 — 执行位置总览

| 阶段 | 在哪运行 | 谁实际执行 |
|------|---------|-----------|
| Phase 0 — Bootstrap | **本地终端** | 你手动运行，一次性 |
| Phase 1 — Python 环境 | **本地终端** | 你手动运行 |
| Phase 2 — Terraform | **本地终端** | 你发指令，AWS 创建资源 |
| Phase 3 — 加载 RDS | **本地终端**（需网络连通） | Python 脚本在本机跑，写入 AWS RDS |
| Phase 4 — Source 2 API | 本地用 **Docker**，云上已由 Terraform 部署 | 本地 Docker / AWS Lambda |
| Phase 5 — Bronze Pipeline | **本地终端**发指令 | AWS Glue / Lambda 在云上跑 |
| Phase 6 — Glue Crawlers | **本地终端**发指令 | AWS Glue 在云上跑 |
| Phase 7 — Silver Pipeline | **本地终端**发指令 | AWS Glue 在云上跑 |
| Phase 8 — 验证 | **本地终端** | 你手动运行 |
| Phase 9 — GitHub & CI/CD | **本地终端** + **GitHub** | 你初始化仓库，Actions 自动运行 |
| CI/CD（后续） | **自动触发**（push 代码） | GitHub Actions → AWS |

> **终端推荐**：Windows 用 **Git Bash** 或 **WSL2**（手册命令全是 bash 语法）。PowerShell 也可以但部分语法需要调整。

---

## 实际操作流程（第一次完整部署）

按以下顺序执行，每步完成后再进行下一步。

### 第一步 — 安装工具（本地，一次性）

1. 安装 [AWS CLI](https://aws.amazon.com/cli/) — 完成后 `aws --version` 有输出
2. 安装 [Terraform 1.7+](https://developer.hashicorp.com/terraform/install) — 完成后 `terraform --version` 有输出
3. 安装 [Python 3.11](https://python.org) — 完成后 `python --version` 显示 3.11.x
4. 安装 [Docker Desktop](https://docker.com) 并启动 — 完成后 `docker ps` 不报错

### 第二步 — 配置 AWS 凭证（本地终端）

```bash
# 用你的 IAM Access Key 配置 profile
aws configure --profile nextcart-dev
# AWS Access Key ID:     填入你的 Access Key ID
# AWS Secret Access Key: 填入你的 Secret Access Key
# Default region name:   ap-southeast-2
# Default output format: json

# 激活这个 profile（每次新开终端都需要执行）
export AWS_PROFILE=nextcart-dev

# 验证配置正确
aws sts get-caller-identity
# 预期输出：包含你的 Account ID 和 UserId 的 JSON
```

### 第三步 — Bootstrap（本地终端，只跑一次）

见下方 **Phase 0**，创建 Terraform 远程 state 所需的 S3 bucket 和 DynamoDB 表。

### 第四步 — 配置 Python 环境（本地终端）

见下方 **Phase 1**。

### 第五步 — Terraform 部署（本地终端，等待约 15 分钟）

见下方 **Phase 2**，执行 `terraform init` → `terraform plan` → `terraform apply`。
Terraform apply 会在 AWS 上创建：VPC、2 个 RDS 实例、S3 bucket、Lambda、Glue 等所有资源。

### 第六步 — 加载数据到 RDS（本地终端）

RDS 在 VPC 私有子网中，本机无法直接访问。**推荐方式：临时允许本机 IP 直连**（Dev 环境专用，加载完立即关闭）。

```bash
# 获取你的公网 IP
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "My IP: ${MY_IP}"

# 获取 RDS 安全组 ID（从 Terraform output 或 AWS 控制台）
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=nextcart-dev-sg-rds" \
  --query 'SecurityGroups[0].GroupId' --output text)

# 临时开放你的 IP → RDS 5432 端口
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_ID}" \
  --protocol tcp \
  --port 5432 \
  --cidr "${MY_IP}/32"

# 获取 RDS 端点（从 terraform output）
cd infra/terraform/environments/dev
ORDERS_HOST=$(terraform output -raw orders_db_endpoint 2>/dev/null || \
  aws rds describe-db-instances \
    --db-instance-identifier nextcart-dev-orders \
    --query 'DBInstances[0].Endpoint.Address' --output text)
cd -

echo "Orders DB host: ${ORDERS_HOST}"
```

然后执行 **Phase 3**（load-source1 和 load-source2）。

加载完成后，**立即关闭临时入站规则**：

```bash
aws ec2 revoke-security-group-ingress \
  --group-id "${SG_ID}" \
  --protocol tcp \
  --port 5432 \
  --cidr "${MY_IP}/32"

echo "Security group rule removed"
```

### 第七步 — 验证 Source 2 API（本地 Docker）

见 **Phase 4.1**，用 Docker Compose 在本地跑 FastAPI + PostgreSQL，验证 5 个端点正常。
AWS 上的 Lambda 版本已由 Terraform 部署，见 Phase 4.2 验证。

### 第八步 — 触发 Bronze Pipeline（本地终端发指令 → AWS 执行）

见 **Phase 5**，用 `aws glue start-job-run` 触发 Source 1 提取（实际在 AWS Glue 集群跑），
用 `aws lambda invoke` 触发 Source 2 提取（实际在 AWS Lambda 跑）。

### 第九步 — 运行 Crawler + Silver Pipeline（本地终端发指令 → AWS 执行）

见 **Phase 6 + Phase 7**，依次触发 Glue Crawler 和 Silver ETL Job。

### 第十步 — 验证（本地终端）

见 **Phase 8**，确认 S3 各层数据正常。

### 第十一步 — 推送到 GitHub（本地终端 + GitHub 网页）

见 **Phase 9**，创建远程仓库、初始化 git、配置 Actions Secrets、推送代码。首次 push 后 CI 自动运行。

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | ≥ 2.15 | https://aws.amazon.com/cli/ |
| Terraform | ~1.7 | https://developer.hashicorp.com/terraform/install |
| Python | 3.11 | https://python.org |
| Docker Desktop | latest | https://docker.com |
| psql (optional) | any | for manual DB verification |

Verify installs:
```bash
aws --version
terraform --version
python --version
docker --version
```

---

## Phase 0 — One-Time Bootstrap (Run Once Per AWS Account)

These resources must exist before Terraform can store state. Create them manually:

```bash
# Set your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-southeast-2"
STATE_BUCKET="nextcart-terraform-state-${ACCOUNT_ID}"

# 1. Create the S3 state bucket
aws s3api create-bucket \
  --bucket "${STATE_BUCKET}" \
  --region "${REGION}" \
  --create-bucket-configuration LocationConstraint="${REGION}"

# 2. Enable versioning on the state bucket
aws s3api put-bucket-versioning \
  --bucket "${STATE_BUCKET}" \
  --versioning-configuration Status=Enabled

# 3. Block public access on the state bucket
aws s3api put-public-access-block \
  --bucket "${STATE_BUCKET}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 4. Create the DynamoDB lock table
aws dynamodb create-table \
  --table-name "nextcart-terraform-locks" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}"

echo "Bootstrap complete. State bucket: ${STATE_BUCKET}"
```

---

## Phase 1 — Python Environment Setup

```bash
# From repo root
python -m venv .venv

# Activate
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows PowerShell

# Install all dependencies
pip install -r requirements-dev.txt

# Verify tests pass with placeholder
pytest tests/unit/ -v -m "not integration"
```

---

## Phase 2 — Terraform Init & Deploy (Dev)

### 2.1 Configure backend

Create a backend config file (NOT committed to git):

```bash
cat > infra/terraform/environments/dev/backend.tfvars << EOF
bucket         = "nextcart-terraform-state-${ACCOUNT_ID}"
region         = "ap-southeast-2"
dynamodb_table = "nextcart-terraform-locks"
encrypt        = true
EOF
```

### 2.2 Build Lambda dependency layer (required before apply)

The Lambda module expects a pre-built deps zip at `infra/terraform/modules/lambda/build/deps_layer.zip`.
**Must be built inside a Linux container** — native extensions (psycopg2, pyarrow) compiled on Windows will crash in Lambda.

```bash
mkdir -p infra/terraform/modules/lambda/build

# Build inside the Lambda runtime container (ensures Linux-compatible binaries)
docker run --rm \
  -v "$(pwd)/infra/terraform/modules/lambda/build:/out" \
  public.ecr.aws/lambda/python:3.11 \
  bash -c "
    pip install --quiet \
      fastapi mangum sqlalchemy psycopg2-binary \
      pyarrow boto3 requests \
      -t /tmp/python/lib/python3.11/site-packages && \
    cd /tmp && zip -r /out/deps_layer.zip python/ && \
    echo 'Done. Size:' && du -sh /out/deps_layer.zip
  "

ls -lh infra/terraform/modules/lambda/build/deps_layer.zip
# Expected: file exists, typically 60-120 MB
```

> **Note**: The zip is uploaded to S3 first (bypassing Lambda's 70 MB direct-upload limit), then referenced by the layer version. This is handled automatically by Terraform.

### 2.3 Terraform init

```bash
cd infra/terraform/environments/dev

terraform init -backend-config=backend.tfvars
# Expected: "Terraform has been successfully initialized"
```

### 2.4 Terraform plan

Review what will be created:
```bash
terraform plan
```

**Resources created (first apply, ~15 min to provision)**:
- 1 VPC + 4 subnets + IGW + route tables + 3 security groups + S3 VPC endpoint
- 2 RDS PostgreSQL instances (db.t3.micro) — one orders, one products
- 2 Secrets Manager secrets (auto-generated passwords)
- 1 S3 lake bucket (bronze/silver/gold/quarantine prefixes)
- 1 S3 Glue scripts bucket
- IAM roles (Lambda, Glue, EMR, SageMaker)
- Lambda functions (source2-api, source2-bronze-extractor) + API Gateway
- Glue connections, crawlers, ETL jobs

**Estimated monthly cost (dev)**:
- RDS db.t3.micro × 2: ~$28/month (free tier covers 1 instance)
- S3: ~$0.50/month (< 10GB initially)
- Lambda + API Gateway: within free tier
- Glue: $0.44/DPU-hour (only billed when jobs run)
- Total active: ~$15–30/month

### 2.5 Terraform apply

```bash
# Always run from the dev environment directory
cd infra/terraform/environments/dev

terraform apply
# Type 'yes' when prompted

# Save the outputs (note: path uses quotes because of space in "JR proj")
terraform output -json > "../../../../outputs_dev.json"
cat "../../../../outputs_dev.json"
```

Note these output values — you will need them in later steps:
```
source2_api_url        → https://xxxx.execute-api.ap-southeast-2.amazonaws.com/dev
lake_bucket            → nextcart-dev-lake
glue_scripts_bucket    → nextcart-dev-glue-scripts
orders_db_endpoint     → nextcart-dev-orders.xxxxx.ap-southeast-2.rds.amazonaws.com
products_db_endpoint   → nextcart-dev-products.xxxxx.ap-southeast-2.rds.amazonaws.com
orders_db_secret_arn   → arn:aws:secretsmanager:...
products_db_secret_arn → arn:aws:secretsmanager:...
```

> **`terraform output` must be run from `infra/terraform/environments/dev/`**, not from the project root.
> On Windows Git Bash, if the path contains spaces use quotes: `terraform -chdir="infra/terraform/environments/dev" output -raw lake_bucket`

### 2.6 已知 apply 错误及修复

首次 `terraform apply` 期间可能遇到以下错误，按顺序修复后重跑 `terraform apply`：

| 错误信息 | 原因 | 修复 |
|---------|------|------|
| `InvalidParameterValue: Character sets beyond ASCII are not supported` | Security Group description 含非 ASCII 字符（破折号 `—`） | 将 `vpc/main.tf` 中 `—` 改为普通连字符 `-` |
| `Cannot find version 15.4 for postgres` | RDS 15.4 已下线 | 将 `rds/main.tf` 中 `engine_version = "15.4"` 改为 `"15"` |
| `RequestEntityTooLargeException: Request must be smaller than 70167211 bytes` | Lambda layer 直传超过限制 | layer zip 先上传到 S3，再用 `s3_bucket`/`s3_key` 引用（代码已修复） |
| `Error: Output "orders_db_endpoint" not found` | 新 output 未 apply | 重跑 `terraform apply`，或先 `terraform refresh` |
| `InvalidPermission.Duplicate` (authorize-security-group-ingress) | 你的 IP 规则已存在（上次没有撤销） | 忽略该错误，规则有效，继续后续步骤 |

---

## Phase 3 — Load Data into RDS

> **运行位置**：本地终端。RDS 在私有子网里，需要先打通网络连接再运行 Python 脚本。

### 3.1 获取 DB 凭证（从 Secrets Manager）

```bash
# 确保还在 dev 目录下，或者先 cd 回项目根目录
cd "d:/study/JR proj/NextCart"   # Windows Git Bash 路径

# 从 Terraform outputs 读取 RDS 端点
cd infra/terraform/environments/dev

ORDERS_HOST=$(terraform output -raw orders_db_endpoint)
PRODUCTS_HOST=$(terraform output -raw products_db_endpoint 2>/dev/null || \
  aws rds describe-db-instances \
    --db-instance-identifier nextcart-dev-products \
    --query 'DBInstances[0].Endpoint.Address' --output text)

cd -   # 回到项目根目录

echo "Orders DB:   ${ORDERS_HOST}"
echo "Products DB: ${PRODUCTS_HOST}"

# 从 Secrets Manager 取密码
ORDERS_PASS=$(aws secretsmanager get-secret-value \
  --secret-id "nextcart/dev/orders/password" \
  --query SecretString --output text | python -c "import json,sys; print(json.load(sys.stdin)['password'])")

PRODUCTS_PASS=$(aws secretsmanager get-secret-value \
  --secret-id "nextcart/dev/products/password" \
  --query SecretString --output text | python -c "import json,sys; print(json.load(sys.stdin)['password'])")
```

### 3.2 打通本机 → RDS 网络（临时开放 IP，Dev 专用）

> Dev 环境的 RDS 设置了 `publicly_accessible = true` 并放在公有子网，这样本机才能通过公网 IP 直连。
> 但 Security Group 默认只允许 Lambda/Glue 访问，需要临时加入你的 IP。

```bash
# 获取你的公网 IP
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "Your IP: ${MY_IP}"

# 获取 RDS 安全组 ID（直接用 AWS CLI，不依赖 terraform output）
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=nextcart-dev-sg-rds" \
  --query 'SecurityGroups[0].GroupId' --output text)
echo "RDS Security Group: ${SG_ID}"

# 临时开放：你的 IP → RDS 端口 5432（如果已存在会报 Duplicate 错误，忽略即可）
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_ID}" \
  --protocol tcp \
  --port 5432 \
  --cidr "${MY_IP}/32" 2>/dev/null || echo "Rule already exists, continuing..."

echo "Ingress rule added. Remember to remove it after loading!"
```

> **连接超时排查**：如果连接仍然 timeout，检查：
> 1. RDS 实例的 `publicly_accessible` 是否为 `true`（`aws rds describe-db-instances --db-instance-identifier nextcart-dev-orders --query 'DBInstances[0].PubliclyAccessible'`）
> 2. 连接时使用的 host 是否是 orders RDS 的 endpoint（不是 products 的）
> 3. 安全组规则是否成功添加（`aws ec2 describe-security-groups --group-ids $SG_ID --query 'SecurityGroups[0].IpPermissions'`）

### 3.3 加载 Source 1 — Orders

> 运行位置：本地终端（项目根目录）

```bash
# 设置连接参数（指向 AWS RDS 公开端点，但受 SG 白名单保护）
export LOCAL_DB_HOST="${ORDERS_HOST}"
export LOCAL_DB_PORT=5432
export LOCAL_DB_PASSWORD="${ORDERS_PASS}"

# 先测试连接是否通
python -c "
import psycopg2, os
conn = psycopg2.connect(
    host=os.environ['LOCAL_DB_HOST'], port=int(os.environ['LOCAL_DB_PORT']),
    dbname='orders', user='nextcart_admin', password=os.environ['LOCAL_DB_PASSWORD'],
    sslmode='require'
)
print('Connection OK:', conn.server_version)
conn.close()
"

# 先跑 sample 验证流程通畅（1000 行，约 10 秒）
python src/ingestion/source1/load_orders_to_rds.py --env local --sample

# 验证 OK 后跑完整数据（3 张表共 ~36M 行，约 15-30 分钟）
python src/ingestion/source1/load_orders_to_rds.py --env local
```

**预期输出**：
```
Tables and indexes created
Loading orders.csv → orders
  orders: 50000 rows inserted
  orders: 100000 rows inserted
  ...
Finished orders: 3421083 total rows
Finished order_products_prior: 32434489 total rows
Finished order_products_train: 1384617 total rows
All tables loaded in 847.3s
```

### 3.4 加载 Source 2 — Products

```bash
export LOCAL_DB_HOST="${PRODUCTS_HOST}"
export LOCAL_DB_PORT=5432
export LOCAL_DB_PASSWORD="${PRODUCTS_PASS}"

python src/ingestion/source2/load_products_to_rds.py --env local
```

**Expected output**:
```
Loaded departments: 21 rows
Loaded aisles: 134 rows
Loaded products: 49688 rows
Products DB loaded in 4.2s
```

### 3.5 验证 RDS 数据

```bash
# 用 Python 验证（不依赖 psql 客户端）
python - << 'EOF'
import psycopg2, os

# Orders DB
conn = psycopg2.connect(
    host=os.environ['LOCAL_DB_HOST'], port=5432,
    dbname='orders', user='nextcart_admin',
    password=os.environ['LOCAL_DB_PASSWORD'], sslmode='require'
)
cur = conn.cursor()
cur.execute("SELECT eval_set, COUNT(*) FROM orders GROUP BY eval_set ORDER BY eval_set;")
print("=== Orders DB ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} rows")
conn.close()
EOF

# 预期输出：
#   prior: 3,214,874 rows
#   test:  75,000 rows
#   train: 131,209 rows
```

### 3.6 ⚠️ 加载完成后立即撤销临时访问权限

```bash
# 必须执行！关闭临时入站规则，恢复 RDS 私有状态
aws ec2 revoke-security-group-ingress \
  --group-id "${SG_ID}" \
  --protocol tcp \
  --port 5432 \
  --cidr "${MY_IP}/32"

# 验证规则已删除
aws ec2 describe-security-groups \
  --group-ids "${SG_ID}" \
  --query 'SecurityGroups[0].IpPermissions'
# 预期：空数组 []

echo "Security group restored. RDS is private again."
```

> **备选方案 — SSH Tunnel via Bastion**（更安全，适合长期使用）：
> 在 AWS 控制台的公有子网里启动一台 t3.nano EC2，拿到其公网 IP，然后：
> ```bash
> BASTION_IP="<bastion-public-ip>"
> ssh -N -L 5433:${ORDERS_HOST}:5432 ec2-user@${BASTION_IP} &    # orders
> ssh -N -L 5434:${PRODUCTS_HOST}:5432 ec2-user@${BASTION_IP} &  # products
> # 之后用 localhost:5433 / localhost:5434 连接，不需要改安全组
> ```

---

## Phase 4 — Source 2 API

> **运行位置**：本地用 Docker Compose 测试；AWS 上的 Lambda 版本已由 Terraform 自动部署。

### 4.1 本地测试（Docker Compose）

```bash
# 运行位置：项目根目录，需要 Docker Desktop 已启动

# 启动本地 FastAPI + PostgreSQL
docker-compose -f src/ingestion/source2/api/docker-compose.yml up -d

# 等待容器启动（约 5 秒）
sleep 5

# 加载产品数据到本地 DB（一次性）
export LOCAL_DB_HOST=localhost
export LOCAL_DB_PORT=5434
export LOCAL_DB_PASSWORD=localpassword
python src/ingestion/source2/load_products_to_rds.py --env local

# 测试所有 API 端点
curl http://localhost:8000/health
# 预期: {"status":"ok"}

curl http://localhost:8000/departments | python -m json.tool
# 预期: 21 个部门的 JSON 数组

curl "http://localhost:8000/products?page=1&page_size=5" | python -m json.tool
# 预期: {"total":49688,"page":1,"page_size":5,"items":[...]}

curl http://localhost:8000/products/196 | python -m json.tool
# 预期: 单个产品详情（含 aisle 和 department 字段）

# 停止本地服务
docker-compose -f src/ingestion/source2/api/docker-compose.yml down
```

**本地 Docker 常见问题：**

| 症状 | 原因 | 修复 |
|------|------|------|
| `entrypoint requires the handler name` | Dockerfile 基于 Lambda 镜像，其 ENTRYPOINT 不是 uvicorn | docker-compose.yml 中加 `entrypoint: python`，command 改为 `-m uvicorn main:app ...` |
| `ImportError: attempted relative import with no known parent package` | `main.py` 中使用了相对导入 `from .database import ...` | 改为绝对导入 `from database import ...`（api 目录下直接跑） |
| `curl: (52) Empty reply from server` | uvicorn 启动后子进程崩溃 | 查看容器日志：`docker-compose -f ... logs api` |

### 4.2 验证 AWS 上的 Lambda API（Terraform 已部署）

> 运行位置：本地终端

```bash
# 读取 API Gateway URL（路径含空格时需加引号）
SOURCE2_API_URL=$(terraform -chdir="infra/terraform/environments/dev" output -raw source2_api_url)
echo "Source 2 API: ${SOURCE2_API_URL}"

curl "${SOURCE2_API_URL}/health"
# 预期: {"status":"ok"}

curl "${SOURCE2_API_URL}/departments"
# 预期: 21 个部门的 JSON 数组（首次调用因 Lambda 冷启动可能慢 3-5 秒）

curl "${SOURCE2_API_URL}/products?page=1&page_size=3" | python -m json.tool
# 预期: {"total":49688,"page":1,"page_size":3,"items":[...]}
```

**AWS Lambda API 常见问题：**

| 症状 | 原因 | 修复 |
|------|------|------|
| `{"message":"Forbidden"}` | Lambda 函数不存在，或 API Gateway deployment 过期 | 检查函数是否存在：`aws lambda list-functions --query 'Functions[?contains(FunctionName,\`nextcart\`)].FunctionName'`；若不存在重跑 `terraform apply -target=module.lambda`；若存在则强制重新部署 API GW：`aws apigateway create-deployment --rest-api-id $API_ID --stage-name dev` |
| `/health` 正常，`/departments` timeout | Lambda 在私有子网，无法访问 Secrets Manager 公共端点 | 确认 VPC 中已有 Secrets Manager interface endpoint：`aws ec2 describe-vpc-endpoints --filters "Name=service-name,Values=com.amazonaws.ap-southeast-2.secretsmanager"`；endpoint 的 SG 必须同时包含 `sg-lambda` 和 `sg-glue` |
| Lambda 冷启动 timeout（第一次请求） | Lambda VPC 冷启动较慢 + Secrets Manager 调用 | 正常现象，热启动后正常；可通过预置并发（Provisioned Concurrency）消除，但 dev 无需配置 |
| `No module named 'pyarrow'` / `No module named 'psycopg2'` | Lambda 函数缺少 layer | 确认函数配置了 deps layer：`terraform apply -target=module.lambda -auto-approve` |

---

## Phase 5 — Bronze Pipeline

> **运行位置**：本地终端发 AWS CLI 指令，实际计算在 **AWS Glue / AWS Lambda** 上执行，不占用你本机资源。

### 5.1 Source 1 Bronze — Glue Job（RDS → S3）

Glue 脚本已由 Terraform 自动上传到 S3，凭证通过 `--orders_secret_arn` 传入（job 的 default_arguments 已设好，无需手动传）。

```bash
# 读取变量（路径含空格时加引号）
LAKE_BUCKET=$(terraform -chdir="infra/terraform/environments/dev" output -raw lake_bucket)

# 触发 Glue Job（命令在本地跑，Job 本身在 AWS Glue 跑）
JOB_RUN_ID=$(aws glue start-job-run \
  --job-name "nextcart-dev-source1-bronze" \
  --query JobRunId --output text)

echo "Glue Job started: ${JOB_RUN_ID}"
echo "Monitor: AWS Console → Glue → Jobs → nextcart-dev-source1-bronze → Run history"

# 用命令行轮询状态（每 30 秒检查一次）
while true; do
  STATE=$(aws glue get-job-run \
    --job-name nextcart-dev-source1-bronze \
    --run-id ${JOB_RUN_ID} \
    --query 'JobRun.JobRunState' --output text)
  echo "$(date '+%H:%M:%S') State: ${STATE}"
  [[ "${STATE}" == "SUCCEEDED" || "${STATE}" == "FAILED" || "${STATE}" == "STOPPED" ]] && break
  sleep 30
done
```

**状态变化**：STARTING → RUNNING → SUCCEEDED
**预计耗时**：10–20 分钟（3 张表，共 ~36M 行）

**Glue Job 失败排查：**

```bash
# 获取错误摘要
aws glue get-job-run \
  --job-name nextcart-dev-source1-bronze \
  --run-id ${JOB_RUN_ID} \
  --query 'JobRun.ErrorMessage' --output text

# 查看详细日志（Windows Git Bash 必须加 MSYS_NO_PATHCONV=1，否则路径被转换）
MSYS_NO_PATHCONV=1 aws logs tail \
  /aws-glue/jobs/error \
  --log-stream-name-prefix "${JOB_RUN_ID}" \
  --format short
```

| 错误信息 | 原因 | 修复 |
|---------|------|------|
| `EntityNotFoundException: Failed to start job run due to missing metadata` | Glue Job 不存在 | `terraform apply -target=module.glue -auto-approve` |
| `empty.reduceLeft` | Glue JDBC hash partitioning 不支持直接传 user/password | 脚本已改用 `spark.read.jdbc`（Spark 原生分区），不受此问题影响 |
| `ConnectTimeoutError: https://secretsmanager...amazonaws.com/` | Glue 在私有子网，Secrets Manager VPC endpoint 的 SG 没有包含 Glue SG | 确认 vpc endpoint 的 `security_group_ids` 包含 `sg-glue`；重跑 `terraform apply -target=module.vpc` |
| `Glue secret manager integration: secretId is not provided` | Glue connection 的 `SECRET_ID` 属性仅对部分连接类型生效，不适用于 JDBC | 脚本改为在代码中用 boto3 直接调 Secrets Manager（已修复） |
| RDS 表存在但行数为 0 | 数据没有真正加载成功 | 检查行数：见 Phase 3.5；重跑 Phase 3.3 |

### 5.2 Source 2 Bronze — Lambda 触发（API → S3）

> 这个 Lambda 调用 Source 2 API，把产品数据分页拉取并写入 S3 Bronze。

```bash
# 触发 Lambda（本地发命令，Lambda 在 AWS 运行）
aws lambda invoke \
  --function-name "nextcart-dev-source2-bronze" \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json

cat /tmp/response.json
# 预期: {"statusCode":200,"body":"{\"status\":\"ok\",\"run_date\":\"...\"}"}
```

### 5.3 验证 Bronze 数据已写入 S3

```bash
LAKE_BUCKET=$(terraform -chdir=infra/terraform/environments/dev output -raw lake_bucket)

echo "=== Source 1 Bronze ==="
aws s3 ls s3://${LAKE_BUCKET}/bronze/orders/ --recursive | head -20
# 预期: 看到 orders/ order_products_prior/ order_products_train/ 下有 .parquet 文件

echo "=== Source 2 Bronze ==="
aws s3 ls s3://${LAKE_BUCKET}/bronze/products/ --recursive
# 预期: 看到 products/ aisles/ departments/ 下各有 data.parquet
```

---

## Phase 6 — Glue Crawlers（注册 Bronze Schema 到 Data Catalog）

> **运行位置**：本地终端发指令，Crawler 在 **AWS Glue** 上运行。
> **前提**：Phase 5 的 Bronze Job 已 SUCCEEDED。

```bash
# 同时启动两个 Crawler
aws glue start-crawler --name "nextcart-dev-crawler-bronze-orders"
aws glue start-crawler --name "nextcart-dev-crawler-bronze-products"

echo "Crawlers started. Waiting for completion (2-5 min each)..."

# 等待所有 Crawler 完成
for CRAWLER in nextcart-dev-crawler-bronze-orders nextcart-dev-crawler-bronze-products; do
  while true; do
    STATE=$(aws glue get-crawler --name ${CRAWLER} \
      --query 'Crawler.State' --output text)
    echo "$(date '+%H:%M:%S') ${CRAWLER}: ${STATE}"
    [ "${STATE}" = "READY" ] && break
    sleep 15
  done
done

echo "All crawlers done."

# 验证表已注册到 Glue Catalog
aws glue get-tables \
  --database-name "nextcart_dev_bronze" \
  --query 'TableList[].Name'
# 预期: ["aisles","departments","order_products_prior","order_products_train","orders","products"]
```

---

## Phase 7 — Silver Pipeline（Glue ETL）

> **运行位置**：本地终端发指令，ETL 在 **AWS Glue** 上运行（PySpark 托管环境）。
> **前提**：Phase 6 的 Crawler 已 READY。

Run silver transform jobs after bronze crawlers complete:

```bash
# Orders silver transform
ORDERS_SILVER_RUN=$(aws glue start-job-run \
  --job-name "nextcart-dev-orders-silver" \
  --arguments "{\"--lake_bucket\":\"${LAKE_BUCKET}\"}" \
  --query JobRunId --output text)

echo "Orders silver job run: ${ORDERS_SILVER_RUN}"

# Products silver transform
PRODUCTS_SILVER_RUN=$(aws glue start-job-run \
  --job-name "nextcart-dev-products-silver" \
  --arguments "{\"--lake_bucket\":\"${LAKE_BUCKET}\"}" \
  --query JobRunId --output text)

echo "Products silver job run: ${PRODUCTS_SILVER_RUN}"

# Monitor
aws glue get-job-run --job-name nextcart-dev-orders-silver \
  --run-id ${ORDERS_SILVER_RUN} --query 'JobRun.{State:JobRunState,Err:ErrorMessage}'
```

### 7.1 Run Silver Crawler

```bash
aws glue start-crawler --name "nextcart-dev-crawler-silver"

# Wait
while [ "$(aws glue get-crawler --name nextcart-dev-crawler-silver --query 'Crawler.State' --output text)" != "READY" ]; do
  sleep 15; echo "waiting..."
done

# Verify silver tables
aws glue get-tables \
  --database-name "nextcart_dev_silver" \
  --query 'TableList[].Name'
```

### 7.2 验证 Silver 数据

```bash
# 检查 Silver 层输出（本地终端）
echo "=== Silver S3 contents ==="
aws s3 ls s3://${LAKE_BUCKET}/silver/ --recursive | head -30

# 检查隔离区（应为空或极少量）
echo "=== Quarantine (should be empty) ==="
aws s3 ls s3://${LAKE_BUCKET}/quarantine/ --recursive

# 运行 Silver Crawler，注册 schema 到 Catalog
aws glue start-crawler --name "nextcart-dev-crawler-silver"
while true; do
  STATE=$(aws glue get-crawler --name nextcart-dev-crawler-silver \
    --query 'Crawler.State' --output text)
  echo "$(date '+%H:%M:%S') Silver crawler: ${STATE}"
  [ "${STATE}" = "READY" ] && break
  sleep 15
done

aws glue get-tables \
  --database-name "nextcart_dev_silver" \
  --query 'TableList[].Name'
# 预期: ["orders","order_products_prior","order_products_train","products"]
```

---

## Phase 8 — 端到端验证

> **运行位置**：本地终端。安装 `s3fs` 后用 Python 直接读取 S3 Parquet 验证行数。

```bash
# 安装 s3fs（如果还没有）
pip install s3fs pyarrow

# 读取 LAKE_BUCKET 变量
LAKE_BUCKET=$(terraform -chdir=infra/terraform/environments/dev output -raw lake_bucket)

# 运行验证脚本
python - << EOF
import pyarrow.parquet as pq
import s3fs

LAKE_BUCKET = "${LAKE_BUCKET}"
fs = s3fs.S3FileSystem()

checks = [
    ("Bronze orders",          f"{LAKE_BUCKET}/bronze/orders/orders/"),
    ("Bronze order_products",  f"{LAKE_BUCKET}/bronze/orders/order_products_prior/"),
    ("Bronze products",        f"{LAKE_BUCKET}/bronze/products/products/"),
    ("Silver orders",          f"{LAKE_BUCKET}/silver/orders/orders/"),
    ("Silver products",        f"{LAKE_BUCKET}/silver/products/"),
]

print(f"{'Layer':<25} {'Path':<55} {'Rows':>12}")
print("-" * 95)
for label, path in checks:
    try:
        ds = pq.ParquetDataset(path, filesystem=fs)
        total = sum(f.metadata.num_rows for f in ds.fragments)
        status = "OK " if total > 0 else "EMPTY"
        print(f"{status} {label:<22} s3://{path:<52} {total:>12,}")
    except Exception as e:
        print(f"ERR {label:<22} s3://{path:<52} {str(e)[:30]}")
EOF
```

**预期输出**（行数参考）：
```
Layer                     Path                                                       Rows
-----------------------------------------------------------------------------------------------
OK  Bronze orders         s3://nextcart-dev-lake/bronze/orders/orders/         3,421,083
OK  Bronze order_products s3://nextcart-dev-lake/bronze/orders/order_produ... 32,434,489
OK  Bronze products       s3://nextcart-dev-lake/bronze/products/products/         49,688
OK  Silver orders         s3://nextcart-dev-lake/silver/orders/orders/         3,420,900
OK  Silver products       s3://nextcart-dev-lake/silver/products/                 49,688
```

---

## Phase 9 — 推送到 GitHub & 激活 CI/CD

> **运行位置**：本地终端 + GitHub 网页。
> **前提**：Phase 0–8 全部完成，本地代码状态良好。

### 9.1 更新 .gitignore（确保不提交大文件和敏感信息）

Lambda layer 构建产物（deps_layer.zip）体积可达 100+ MB，必须排除在 git 之外。
Terraform backend 配置含账号信息，也不应提交。

```bash
# 在项目根目录执行
cat >> .gitignore << 'EOF'

# Lambda build artifacts — binary, large, platform-specific
infra/terraform/modules/lambda/build/

# Terraform backend config — contains account-specific bucket names
backend.tfvars
infra/terraform/environments/*/backend.tfvars

# Local outputs file
outputs_dev.json
infra/terraform/outputs_dev.json
EOF
```

验证 .gitignore 生效：
```bash
git check-ignore -v infra/terraform/modules/lambda/build/deps_layer.zip
# 预期输出: .gitignore:xx:infra/terraform/modules/lambda/build/  ...deps_layer.zip
```

### 9.2 在 GitHub 创建远程仓库

1. 打开 [github.com](https://github.com) → **New repository**
2. Repository name: `NextCart`（或 `nextcart`）
3. Visibility: **Private**（项目含 AWS 账号相关配置）
4. **不要**勾选 "Add a README"、".gitignore"、"license"（本地已有）
5. 点击 **Create repository**，记录仓库 URL，例如：`https://github.com/your-username/NextCart.git`

### 9.3 初始化本地 git 仓库并完成首次提交

```bash
# 在项目根目录执行
cd "d:/study/JR proj/NextCart"

# 初始化 git
git init
git branch -M main

# 添加远程仓库（替换为你的实际 URL）
git remote add origin https://github.com/your-username/NextCart.git

# 检查哪些文件会被提交（确认没有大文件和敏感信息）
git status
git ls-files --others --exclude-standard | head -30   # 未追踪文件预览

# 暂存所有文件
git add .

# 再次确认 staged 文件，重点检查没有 .env、*.tfstate、deps_layer.zip
git status
# 如果看到不该提交的文件，用 git rm --cached <file> 撤销

# 首次提交
git commit -m "feat: initial NextCart project scaffold

- Medallion architecture pipeline (Bronze/Silver/Gold)
- Terraform modules: VPC, RDS, S3, Lambda, Glue, IAM
- Source 1 orders loader + Source 2 products API
- Glue ETL jobs for bronze and silver layers
- GitHub Actions CI workflow"
```

### 9.4 配置 GitHub Actions Secrets

CI/CD workflows 需要 AWS 凭证和配置信息。在 GitHub 仓库页面配置：

**路径**：仓库页 → Settings → Secrets and variables → Actions → **New repository secret**

需要添加的 Secrets：

| Secret 名称 | 值来源 | 说明 |
|-------------|--------|------|
| `AWS_ACCESS_KEY_ID` | IAM 用户凭证 | CI 用的 IAM Access Key |
| `AWS_SECRET_ACCESS_KEY` | IAM 用户凭证 | 对应的 Secret Key |
| `AWS_REGION` | `ap-southeast-2` | 固定值 |
| `TF_STATE_BUCKET` | Phase 0 创建的 bucket 名 | `nextcart-terraform-state-<account_id>` |
| `DB_PASSWORD_SECRET_ARN` | `orders_db_secret_arn` terraform output | 用于集成测试（可选） |

```bash
# 快速获取需要填入的值
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "TF_STATE_BUCKET: nextcart-terraform-state-${ACCOUNT_ID}"

cd infra/terraform/environments/dev
echo "DB_PASSWORD_SECRET_ARN: $(terraform output -raw orders_db_secret_arn)"
```

> **最佳实践**：建议为 GitHub Actions 单独创建一个权限受限的 IAM 用户（只有 CI 需要的权限），不要使用个人开发账号的 Access Key。

### 9.5 创建 develop 分支并推送

根据项目分支模型，`develop` 是日常开发的集成分支，`main` 只接受 PR：

```bash
# 推送 main 分支
git push -u origin main

# 创建并推送 develop 分支
git checkout -b develop
git push -u origin develop

# 切回 develop 作为日常工作分支
# （后续 feature 从 develop 分出，合回 develop）
```

### 9.6 验证 CI 自动触发

```bash
# 模拟一次 PR 流程，验证 CI 工作
git checkout -b test/verify-ci
echo "# CI test" >> README_CI_TEST.md
git add README_CI_TEST.md
git commit -m "test(ci): verify GitHub Actions pipeline"
git push -u origin test/verify-ci
```

然后在 GitHub 网页：
1. 打开仓库 → **Pull requests** → **New pull request**
2. base: `develop` ← compare: `test/verify-ci`
3. 创建 PR

**预期**：Actions 自动运行三个 job：

| Job | 内容 | 预期结果 |
|-----|------|---------|
| `lint` | flake8 + black --check | ✅ Pass |
| `unit-tests` | pytest tests/unit/ + coverage ≥ 80% | ✅ Pass（PySpark 相关 test 跳过） |
| `tf-validate` | terraform validate（dev 模块） | ✅ Pass |

查看 CI 状态：仓库页 → **Actions** tab

```bash
# 也可以用 gh CLI 查看（需先安装 GitHub CLI）
gh run list --limit 5
gh run view <run-id>
```

CI 通过后，合并 PR，然后清理测试分支：

```bash
git checkout develop
git pull origin develop
git branch -d test/verify-ci
git push origin --delete test/verify-ci
```

### 9.7 后续日常开发工作流

```bash
# 新功能开发标准流程
git checkout develop
git pull origin develop

git checkout -b feat/silver-great-expectations   # 从 develop 新建 feature 分支

# ... 编写代码 ...

git add .
git commit -m "feat(silver): add Great Expectations data quality checks"
git push -u origin feat/silver-great-expectations

# GitHub 上创建 PR: feat/... → develop
# CI 自动运行，通过后合并

# 合并到 main 触发 prod 部署（需人工审批）
# main 受保护，只能通过 PR 合并
```

---

## 暂停与销毁（控制 Dev 成本）

### 暂停 RDS（保留数据，停止计费，最多 7 天）

在 AWS 控制台：RDS → 选择实例 → Actions → Stop temporarily
或用 CLI：

```bash
aws rds stop-db-instance --db-instance-identifier nextcart-dev-orders
aws rds stop-db-instance --db-instance-identifier nextcart-dev-products
# 停止后不再按小时计费，但存储费用仍计
```

### 完全销毁所有资源（不可逆）

```bash
cd infra/terraform/environments/dev
terraform destroy
# 输入 'yes' 确认 — 这会删除所有 RDS 数据、S3 数据、Lambda 等
```

> **注意**：`terraform destroy` 会删除 S3 lake bucket 里的所有数据（Bronze/Silver/Gold）。如果需要保留数据，先手动备份或取消 `lifecycle { prevent_destroy = true }` 保护。

---

## Troubleshooting

### 综合问题速查表

| 症状 | 原因 | 修复 |
|------|------|------|
| `terraform init` 失败: "No such bucket" | State bucket 未创建 | 执行 Phase 0 bootstrap |
| `InvalidParameterValue: Character sets beyond ASCII` | SG description 含非 ASCII 字符（如 `—`） | 改为普通连字符 `-` |
| `Cannot find version 15.x for postgres` | 指定的 RDS 小版本已下线 | 改为大版本号如 `"15"`，AWS 自动选最新可用版本 |
| `RequestEntityTooLargeException` (Lambda layer) | layer zip > 70 MB 直传限制 | 先上传到 S3，用 `s3_bucket`/`s3_key` 引用（已在代码中修复） |
| `ModifyDBSubnetGroup: Some subnets currently in use` | 试图从 subnet group 移除已被实例占用的子网 | 先用 `concat(private, public)` 保留原子网再 apply；若需彻底换子网需 destroy + recreate |
| `Output "xxx" not found` | output 在最近一次 apply 后才加入配置 | 重跑 `terraform apply`，或改用 `aws` CLI 直接查询 |
| RDS 连接 timeout（本机直连） | RDS 在私有子网或公网 IP 未加入 SG | 确认 `publicly_accessible=true`（dev 专用）且已执行 Phase 3.2 的 SG 白名单 |
| `database "xxx" does not exist` | 连接的 host 是另一个 RDS 实例 | Orders 和 Products 是两个独立 RDS，端点不同，连接时确认使用正确的 `ORDERS_HOST` / `PRODUCTS_HOST` |
| `{"message":"Forbidden"}` from API GW | Lambda 函数不存在或 deployment 过期 | 检查 Lambda 是否创建；强制重部署：`aws apigateway create-deployment --rest-api-id $API_ID --stage-name dev` |
| `Endpoint request timed out` (API GW) | Lambda 无法访问 Secrets Manager（私有子网无 NAT） | 确认 Secrets Manager VPC interface endpoint 存在且 SG 包含 lambda SG（有 HTTPS self ingress）；重跑 `terraform apply -target=module.vpc` |
| `No module named 'pyarrow'` / `'psycopg2'` | Lambda 函数未绑定 deps layer | `terraform apply -target=module.lambda -auto-approve` |
| `ImportError: attempted relative import` | FastAPI 代码用了相对导入（`.database`） | 改为绝对导入（`database`），已在代码中修复 |
| Glue `empty.reduceLeft` | Glue 内部 hash partition 查 MIN/MAX 失败（表空或直接传凭证时的已知 bug） | 1) 确认表有数据；2) 改用 `spark.read.jdbc` 替代 Glue DynamicFrame（已修复） |
| Glue `ConnectTimeoutError: secretsmanager` | Glue SG 不在 Secrets Manager VPC endpoint 的允许列表 | endpoint 的 `security_group_ids` 加入 `sg_glue_id`；重跑 `terraform apply -target=module.vpc` |
| Glue job `EntityNotFoundException` | Glue job 未被创建 | `terraform apply -target=module.glue -auto-approve` |

---

### Windows Git Bash 特别注意事项

```bash
# 1. 路径含空格时，-chdir 参数需加引号
terraform -chdir="infra/terraform/environments/dev" output -raw lake_bucket
# ❌ 错误: terraform -chdir=infra/terraform/environments/dev output ...

# 2. aws logs tail 的 log group 路径以 / 开头，Git Bash 会把它当 Windows 路径展开
#    解决方法：加 MSYS_NO_PATHCONV=1 前缀
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/nextcart-dev-source2-api --follow --format short
MSYS_NO_PATHCONV=1 aws logs tail /aws-glue/jobs/error --log-stream-name-prefix "${JOB_RUN_ID}" --format short

# 3. terraform output 必须在 environments/dev 目录下运行
cd infra/terraform/environments/dev
terraform output -raw lake_bucket
# 不要在项目根目录下跑，会提示 "No outputs found"
```

---

### 常用诊断命令

```bash
# ── Lambda ──────────────────────────────────────────────────────────────────
# 查看所有 nextcart Lambda 函数
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName,`nextcart`)].FunctionName'

# 直接调用 source2-api 测试（不经过 API Gateway）
aws lambda invoke \
  --function-name nextcart-dev-source2-api \
  --cli-binary-format raw-in-base64-out \
  --payload '{"httpMethod":"GET","path":"/health","headers":{},"queryStringParameters":null,"body":null,"isBase64Encoded":false,"requestContext":{"resourcePath":"/{proxy+}","stage":"dev"}}' \
  /tmp/response.json && cat /tmp/response.json

# 查看 Lambda 日志（Windows 需加 MSYS_NO_PATHCONV=1）
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/nextcart-dev-source2-api --follow --format short
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/nextcart-dev-source2-bronze --follow --format short

# ── Glue ────────────────────────────────────────────────────────────────────
# 列出所有 Glue Job
aws glue list-jobs --query 'JobNames'

# 查看最近一次 run 状态
aws glue get-job-run \
  --job-name nextcart-dev-source1-bronze \
  --run-id ${JOB_RUN_ID} \
  --query 'JobRun.{State:JobRunState,Error:ErrorMessage}'

# Glue 错误日志
MSYS_NO_PATHCONV=1 aws logs tail /aws-glue/jobs/error \
  --log-stream-name-prefix "${JOB_RUN_ID}" --format short

# Glue 输出日志（print 语句）
MSYS_NO_PATHCONV=1 aws logs tail /aws-glue/jobs/output \
  --log-stream-name-prefix "${JOB_RUN_ID}" --format short

# ── RDS ─────────────────────────────────────────────────────────────────────
# 查看 RDS 实例状态
aws rds describe-db-instances \
  --query 'DBInstances[?contains(DBInstanceIdentifier,`nextcart`)].{ID:DBInstanceIdentifier,Status:DBInstanceStatus,Public:PubliclyAccessible}'

# 验证行数（需先配置好 LOCAL_DB_HOST / ORDERS_HOST 等环境变量）
python -c "
import psycopg2, os
conn = psycopg2.connect(host=os.environ['ORDERS_HOST'], port=5432,
    dbname='orders', user='nextcart_admin',
    password=os.environ['ORDERS_PASS'], sslmode='require')
cur = conn.cursor()
for t in ['orders','order_products_prior','order_products_train']:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'{t}: {cur.fetchone()[0]:,}')
conn.close()
"

# ── VPC Endpoints ────────────────────────────────────────────────────────────
# 检查 Secrets Manager endpoint 是否存在且状态正常
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.ap-southeast-2.secretsmanager" \
  --query "VpcEndpoints[*].{State:State,Id:VpcEndpointId,SGs:Groups[*].GroupId}"

# ── 成本检查 ─────────────────────────────────────────────────────────────────
aws rds describe-db-instances \
  --query 'DBInstances[?contains(DBInstanceIdentifier,`nextcart`)].{ID:DBInstanceIdentifier,Status:DBInstanceStatus,Class:DBInstanceClass}'
```
