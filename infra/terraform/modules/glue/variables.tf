variable "project"              { type = string }
variable "environment"          { type = string }
variable "glue_role_arn"        { type = string }
variable "lake_bucket"          { type = string }
variable "scripts_path"         { type = string }
variable "orders_db_endpoint"   { type = string }
variable "orders_db_name"       { type = string }
variable "orders_db_secret_arn" {
  type = string
}
variable "private_subnet_ids"   { type = list(string) }
variable "availability_zones"   { type = list(string) }
variable "sg_glue_id"           { type = string }
