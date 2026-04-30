provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "nextcart"
      Environment = "prod"
      ManagedBy   = "terraform"
      Owner       = "data-eng-team"
    }
  }
}

# Prod environment — mirrors dev with production-grade sizing.
# Only populated after dev is stable (Week 5+).
