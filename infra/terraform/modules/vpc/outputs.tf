output "vpc_id"              { value = aws_vpc.main.id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "public_subnet_ids"  { value = aws_subnet.public[*].id }
output "sg_rds_id"          { value = aws_security_group.rds.id }
output "sg_lambda_vpc_id"   { value = aws_security_group.lambda_vpc.id }
output "sg_glue_id"         { value = aws_security_group.glue.id }
