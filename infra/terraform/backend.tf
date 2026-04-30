# Remote state — S3 bucket and DynamoDB lock table must be created manually
# before running terraform init for the first time.
#
# Bootstrap commands (run once):
#   aws s3api create-bucket --bucket nextcart-terraform-state-{ACCOUNT_ID} --region ap-southeast-2 \
#       --create-bucket-configuration LocationConstraint=ap-southeast-2
#   aws s3api put-bucket-versioning --bucket nextcart-terraform-state-{ACCOUNT_ID} \
#       --versioning-configuration Status=Enabled
#   aws dynamodb create-table --table-name nextcart-terraform-locks \
#       --attribute-definitions AttributeName=LockID,AttributeType=S \
#       --key-schema AttributeName=LockID,KeyType=HASH \
#       --billing-mode PAY_PER_REQUEST --region ap-southeast-2

terraform {
  backend "s3" {
    # Fill in actual values in environments/dev/backend.tfvars and environments/prod/backend.tfvars
    # Run: terraform init -backend-config=backend.tfvars
    bucket         = "nextcart-terraform-state"   # override per environment
    key            = "nextcart/terraform.tfstate"  # override per environment
    region         = "ap-southeast-2"
    dynamodb_table = "nextcart-terraform-locks"
    encrypt        = true
  }
}
