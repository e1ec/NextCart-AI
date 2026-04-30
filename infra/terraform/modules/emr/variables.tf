variable "project"     { type = string }
variable "environment" { type = string }
variable "region"      { type = string }

variable "emr_service_role_arn" { type = string }
variable "emr_ec2_profile_arn"  { type = string }

variable "vpc_id"    { type = string }
variable "subnet_id" { type = string }

variable "lake_bucket"    { type = string }
variable "scripts_bucket" { type = string }

variable "master_instance_type"  {
  type    = string
  default = "m5.xlarge"
}

variable "idle_timeout_seconds" {
  type    = number
  default = 3600
}
