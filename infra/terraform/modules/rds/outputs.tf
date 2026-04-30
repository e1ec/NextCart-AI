output "endpoint"           { value = aws_db_instance.main.address }
output "port"               { value = aws_db_instance.main.port }
output "db_name"            { value = aws_db_instance.main.db_name }
output "secret_arn"         { value = aws_secretsmanager_secret.db_password.arn }
