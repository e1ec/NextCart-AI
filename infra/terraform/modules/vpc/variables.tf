variable "project"            { type = string }
variable "environment"        { type = string }
variable "region"             { type = string }
variable "cidr"               { 
    type = string
    default = "10.0.0.0/16" 
 }
variable "availability_zones" { type = list(string) }
