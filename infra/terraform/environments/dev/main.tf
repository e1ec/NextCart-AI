provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "nextcart"
      Environment = "dev"
      ManagedBy   = "terraform"
      Owner       = "data-eng-team"
    }
  }
}

terraform {
  required_providers {
    aws    = { 
      source = "hashicorp/aws"
       version = "~> 5.0" }
    random = { 
      source = "hashicorp/random"
       version = "~> 3.0" }
    archive = { 
      source = "hashicorp/archive"
       version = "~> 2.0" }
  }
  backend "s3" {
    key = "nextcart/dev/terraform.tfstate"
  }
}

locals {
  project     = var.project
  environment = var.environment
  region      = var.aws_region
  azs         = ["${var.aws_region}a", "${var.aws_region}b"]
  src_path    = "${path.root}/../../../../src"
}

# ── VPC ──────────────────────────────────────────────────────
module "vpc" {
  source             = "../../modules/vpc"
  project            = local.project
  environment        = local.environment
  region             = local.region
  availability_zones = local.azs
}

# ── S3 Data Lake ─────────────────────────────────────────────
module "s3" {
  source      = "../../modules/s3"
  project     = local.project
  environment = local.environment
}

# ── IAM Roles ────────────────────────────────────────────────
module "iam" {
  source      = "../../modules/iam"
  project     = local.project
  environment = local.environment
}

# ── RDS — Source 1: Orders ───────────────────────────────────
module "rds_orders" {
  source               = "../../modules/rds"
  project              = local.project
  environment          = local.environment
  db_identifier        = "orders"
  db_name              = "orders"
  subnet_ids           = module.vpc.public_subnet_ids
  sg_rds_id            = module.vpc.sg_rds_id
  instance_class       = "db.t3.micro"
  publicly_accessible  = true
}

# ── RDS — Source 2: Products ─────────────────────────────────
module "rds_products" {
  source               = "../../modules/rds"
  project              = local.project
  environment          = local.environment
  db_identifier        = "products"
  db_name              = "products"
  subnet_ids           = module.vpc.public_subnet_ids
  sg_rds_id            = module.vpc.sg_rds_id
  instance_class       = "db.t3.micro"
  publicly_accessible  = true
}

# ── Lambda (Source 2 API + Bronze Extractor) ─────────────────
module "lambda" {
  source                = "../../modules/lambda"
  project               = local.project
  environment           = local.environment
  region                = local.region
  lambda_role_arn       = module.iam.lambda_role_arn
  lake_bucket           = module.s3.bucket_name
  src_path              = local.src_path
  private_subnet_ids    = module.vpc.private_subnet_ids
  sg_lambda_vpc_id      = module.vpc.sg_lambda_vpc_id
  products_db_secret_arn = module.rds_products.secret_arn
  glue_scripts_bucket    = module.glue.glue_scripts_bucket
}

# ── Glue (Bronze extraction + Silver ETL) ────────────────────
module "glue" {
  source              = "../../modules/glue"
  project             = local.project
  environment         = local.environment
  glue_role_arn       = module.iam.glue_role_arn
  lake_bucket         = module.s3.bucket_name
  scripts_path        = local.src_path
  orders_db_endpoint      = module.rds_orders.endpoint
  orders_db_name          = module.rds_orders.db_name
  orders_db_secret_arn    = module.rds_orders.secret_arn
  private_subnet_ids  = module.vpc.private_subnet_ids
  availability_zones  = local.azs
  sg_glue_id          = module.vpc.sg_glue_id
}

# ── Outputs ──────────────────────────────────────────────────
output "source2_api_url"        { value = module.lambda.source2_api_url }
output "sg_rds_id"              { value = module.vpc.sg_rds_id }
output "lake_bucket"            { value = module.s3.bucket_name }
output "glue_scripts_bucket"    { value = module.glue.glue_scripts_bucket }
output "orders_db_endpoint"     { value = module.rds_orders.endpoint }
output "orders_db_secret_arn"   { value = module.rds_orders.secret_arn }
output "products_db_endpoint"   { value = module.rds_products.endpoint }
output "products_db_secret_arn" { value = module.rds_products.secret_arn }
