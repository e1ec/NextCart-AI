output "lambda_role_arn"          { value = aws_iam_role.lambda.arn }
output "glue_role_arn"            { value = aws_iam_role.glue.arn }
output "emr_service_role_arn"     { value = aws_iam_role.emr_service.arn }
output "emr_ec2_profile_arn"      { value = aws_iam_instance_profile.emr_ec2.arn }
