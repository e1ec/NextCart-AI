output "role_arn" {
  value       = aws_iam_role.sagemaker.arn
  description = "IAM role ARN to pass to SageMaker Training Jobs and Model Registry"
}

output "reorder_model_package_group" {
  value       = aws_sagemaker_model_package_group.reorder.model_package_group_name
}

output "recommendation_model_package_group" {
  value       = aws_sagemaker_model_package_group.recommendation.model_package_group_name
}
