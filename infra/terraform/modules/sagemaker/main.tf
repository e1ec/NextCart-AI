# ── SageMaker IAM execution role ────────────────────────────────────────────

resource "aws_iam_role" "sagemaker" {
  name = "${var.project}-${var.environment}-sagemaker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
    }]
  })

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "data-eng-team"
  }
}

resource "aws_iam_role_policy_attachment" "sagemaker_execution" {
  role       = aws_iam_role.sagemaker.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# Explicit S3 access for the lake and scripts buckets
resource "aws_iam_role_policy" "sagemaker_s3" {
  name = "${var.project}-${var.environment}-sagemaker-s3"
  role = aws_iam_role.sagemaker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LakeBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject",
          "s3:ListBucket", "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.lake_bucket}",
          "arn:aws:s3:::${var.lake_bucket}/*",
        ]
      },
      {
        Sid    = "ScriptsBucketAccess"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.scripts_bucket}",
          "arn:aws:s3:::${var.scripts_bucket}/*",
        ]
      }
    ]
  })
}

# ── Model Registry — Task A (Reorder Prediction) ─────────────────────────────

resource "aws_sagemaker_model_package_group" "reorder" {
  model_package_group_name        = "${var.project}-${var.environment}-reorder"
  model_package_group_description = "Task A Reorder Prediction — XGBoost baseline and LightGBM primary"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "data-eng-team"
  }
}

# ── Model Registry — Task B (Product Recommendation) ─────────────────────────

resource "aws_sagemaker_model_package_group" "recommendation" {
  model_package_group_name        = "${var.project}-${var.environment}-recommendation"
  model_package_group_description = "Task B Product Recommendation — ALS and hybrid models"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "data-eng-team"
  }
}
