data "archive_file" "source2_api" {
  type        = "zip"
  source_dir  = "${var.src_path}/ingestion/source2/api"
  output_path = "${path.module}/build/source2_api.zip"
}

data "archive_file" "source2_bronze" {
  type = "zip"
  source {
    content  = file("${var.src_path}/pipeline/bronze/lambda_source2_bronze.py")
    filename = "handler.py"
  }
  output_path = "${path.module}/build/source2_bronze.zip"
}

# ── Upload deps layer zip to S3 (bypasses 50MB direct-upload limit) ──────
resource "aws_s3_object" "deps_layer" {
  bucket = var.glue_scripts_bucket
  key    = "lambda-layers/python-deps.zip"
  source = "${path.module}/build/deps_layer.zip"
  etag   = filemd5("${path.module}/build/deps_layer.zip")
}

# ── Python deps layer — referenced from S3, not direct upload ────────────
resource "aws_lambda_layer_version" "deps" {
  layer_name               = "${var.project}-${var.environment}-python-deps"
  s3_bucket                = aws_s3_object.deps_layer.bucket
  s3_key                   = aws_s3_object.deps_layer.key
  s3_object_version        = aws_s3_object.deps_layer.version_id
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["x86_64"]
}

# ── Source 2 API Lambda (FastAPI + Mangum, in VPC -> reads RDS products) ─
resource "aws_lambda_function" "source2_api" {
  function_name    = "${var.project}-${var.environment}-source2-api"
  filename         = data.archive_file.source2_api.output_path
  source_code_hash = data.archive_file.source2_api.output_base64sha256
  handler          = "main.handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256
  role             = var.lambda_role_arn

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.sg_lambda_vpc_id]
  }

  environment {
    variables = {
      APP_ENV         = var.environment
      DB_SECRET_ARN   = var.products_db_secret_arn
      AWS_REGION_NAME = var.region
    }
  }

  layers = [aws_lambda_layer_version.deps.arn]

  tags = { Name = "${var.project}-${var.environment}-source2-api" }
}

# ── Source 2 Bronze Extractor Lambda (calls API GW -> writes to S3) ──────
resource "aws_lambda_function" "source2_bronze" {
  function_name    = "${var.project}-${var.environment}-source2-bronze"
  filename         = data.archive_file.source2_bronze.output_path
  source_code_hash = data.archive_file.source2_bronze.output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 512
  role             = var.lambda_role_arn

  environment {
    variables = {
      LAKE_BUCKET  = var.lake_bucket
      API_BASE_URL = "https://${aws_api_gateway_rest_api.source2.id}.execute-api.${var.region}.amazonaws.com/${var.environment}"
    }
  }

  layers = [aws_lambda_layer_version.deps.arn]

  tags = { Name = "${var.project}-${var.environment}-source2-bronze" }
}

# ── API Gateway for Source 2 API ─────────────────────────────────────────
resource "aws_api_gateway_rest_api" "source2" {
  name = "${var.project}-${var.environment}-source2-api"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.source2.id
  parent_id   = aws_api_gateway_rest_api.source2.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.source2.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.source2.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.source2_api.invoke_arn
}

# Use aws_api_gateway_stage instead of deprecated stage_name on deployment
resource "aws_api_gateway_deployment" "main" {
  depends_on  = [aws_api_gateway_integration.lambda]
  rest_api_id = aws_api_gateway_rest_api.source2.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_integration.lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.source2.id
  stage_name    = var.environment
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.source2_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.source2.execution_arn}/*/*"
}
