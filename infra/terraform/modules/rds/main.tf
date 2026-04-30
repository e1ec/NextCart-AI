resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-${var.environment}-${var.db_identifier}"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${var.project}-${var.environment}-${var.db_identifier}-subnet-group" }
}

resource "random_password" "db" {
  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.project}/${var.environment}/${var.db_identifier}/password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = var.db_name
  })
}

resource "aws_db_instance" "main" {
  identifier        = "${var.project}-${var.environment}-${var.db_identifier}"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.sg_rds_id]
  publicly_accessible    = var.publicly_accessible
  skip_final_snapshot    = var.environment == "dev"
  deletion_protection    = var.environment == "prod"
  multi_az               = var.environment == "prod"

  backup_retention_period = var.environment == "prod" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  tags = { Name = "${var.project}-${var.environment}-${var.db_identifier}" }
}
