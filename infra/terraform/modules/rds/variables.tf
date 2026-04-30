variable "project"           { type = string }
variable "environment"       { type = string }
variable "db_identifier"     { type = string }
variable "db_name"           { type = string }
variable "db_username"       { 
    type = string
    default = "nextcart_admin" 
    }
variable "subnet_ids"        { type = list(string) }
variable "sg_rds_id"         { type = string }
variable "instance_class"    { 
    type = string
    default = "db.t3.micro" 
    }
variable "allocated_storage" {
    type = number
    default = 20
    }
variable "publicly_accessible" {
  type    = bool
  default = false
}
