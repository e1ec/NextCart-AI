output "source2_api_url"           { value = aws_api_gateway_stage.main.invoke_url }
output "source2_api_function_name" { value = aws_lambda_function.source2_api.function_name }
output "source2_bronze_function"   { value = aws_lambda_function.source2_bronze.function_name }
