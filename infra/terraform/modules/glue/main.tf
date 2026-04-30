# ── Glue Scripts Bucket ──────────────────────────────────────
resource "aws_s3_bucket" "glue_scripts" {
  bucket = "${var.project}-${var.environment}-glue-scripts"
}

resource "aws_s3_bucket_public_access_block" "glue_scripts" {
  bucket                  = aws_s3_bucket.glue_scripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload Glue PySpark scripts to S3
resource "aws_s3_object" "glue_source1_bronze" {
  bucket = aws_s3_bucket.glue_scripts.bucket
  key    = "bronze/glue_source1_bronze.py"
  source = "${var.scripts_path}/pipeline/bronze/glue_source1_bronze.py"
  etag   = filemd5("${var.scripts_path}/pipeline/bronze/glue_source1_bronze.py")
}

resource "aws_s3_object" "glue_orders_silver" {
  bucket = aws_s3_bucket.glue_scripts.bucket
  key    = "silver/glue_orders_silver.py"
  source = "${var.scripts_path}/pipeline/silver/glue_orders_silver.py"
  etag   = filemd5("${var.scripts_path}/pipeline/silver/glue_orders_silver.py")
}

resource "aws_s3_object" "glue_products_silver" {
  bucket = aws_s3_bucket.glue_scripts.bucket
  key    = "silver/glue_products_silver.py"
  source = "${var.scripts_path}/pipeline/silver/glue_products_silver.py"
  etag   = filemd5("${var.scripts_path}/pipeline/silver/glue_products_silver.py")
}

# ── Glue Data Catalog ────────────────────────────────────────
resource "aws_glue_catalog_database" "bronze" {
  name = "${var.project}_${var.environment}_bronze"
}

resource "aws_glue_catalog_database" "silver" {
  name = "${var.project}_${var.environment}_silver"
}

# ── JDBC Connection to RDS Orders ────────────────────────────
resource "aws_glue_connection" "rds_orders" {
  name = "${var.project}-${var.environment}-rds-orders"

  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:postgresql://${var.orders_db_endpoint}:5432/${var.orders_db_name}"
    SECRET_ID           = var.orders_db_secret_arn
  }

  physical_connection_requirements {
    availability_zone      = var.availability_zones[0]
    security_group_id_list = [var.sg_glue_id]
    subnet_id              = var.private_subnet_ids[0]
  }
}

# ── Crawlers ─────────────────────────────────────────────────
resource "aws_glue_crawler" "bronze_orders" {
  database_name = aws_glue_catalog_database.bronze.name
  name          = "${var.project}-${var.environment}-crawler-bronze-orders"
  role          = var.glue_role_arn
  schedule      = "cron(0 2 * * ? *)"

  s3_target {
    path = "s3://${var.lake_bucket}/bronze/orders/"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })
}

resource "aws_glue_crawler" "bronze_products" {
  database_name = aws_glue_catalog_database.bronze.name
  name          = "${var.project}-${var.environment}-crawler-bronze-products"
  role          = var.glue_role_arn

  s3_target {
    path = "s3://${var.lake_bucket}/bronze/products/"
  }
}

resource "aws_glue_crawler" "silver" {
  database_name = aws_glue_catalog_database.silver.name
  name          = "${var.project}-${var.environment}-crawler-silver"
  role          = var.glue_role_arn

  s3_target {
    path = "s3://${var.lake_bucket}/silver/"
  }
}

# ── ETL Jobs ─────────────────────────────────────────────────
resource "aws_glue_job" "source1_bronze" {
  name              = "${var.project}-${var.environment}-source1-bronze"
  role_arn          = var.glue_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 60

  command {
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/bronze/glue_source1_bronze.py"
    python_version  = "3"
  }

  connections = [aws_glue_connection.rds_orders.name]

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--lake_bucket"                      = var.lake_bucket
    "--orders_secret_arn"                = var.orders_db_secret_arn
    "--TempDir"                          = "s3://${aws_s3_bucket.glue_scripts.bucket}/tmp/"
  }
}

resource "aws_glue_job" "orders_silver" {
  name              = "${var.project}-${var.environment}-orders-silver"
  role_arn          = var.glue_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 60

  command {
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/silver/glue_orders_silver.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--lake_bucket"                      = var.lake_bucket
    "--TempDir"                          = "s3://${aws_s3_bucket.glue_scripts.bucket}/tmp/"
  }
}

resource "aws_glue_job" "products_silver" {
  name              = "${var.project}-${var.environment}-products-silver"
  role_arn          = var.glue_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30

  command {
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/silver/glue_products_silver.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--lake_bucket"                      = var.lake_bucket
    "--TempDir"                          = "s3://${aws_s3_bucket.glue_scripts.bucket}/tmp/"
  }
}
