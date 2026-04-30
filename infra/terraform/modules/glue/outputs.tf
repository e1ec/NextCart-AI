output "bronze_database_name"   { value = aws_glue_catalog_database.bronze.name }
output "silver_database_name"   { value = aws_glue_catalog_database.silver.name }
output "source1_bronze_job"     { value = aws_glue_job.source1_bronze.name }
output "orders_silver_job"      { value = aws_glue_job.orders_silver.name }
output "products_silver_job"    { value = aws_glue_job.products_silver.name }
output "glue_scripts_bucket"    { value = aws_s3_bucket.glue_scripts.bucket }
