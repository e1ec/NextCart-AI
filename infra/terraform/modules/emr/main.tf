# ── Security groups (cross-reference via separate rules to avoid cycle) ───────
resource "aws_security_group" "emr_master" {
  name        = "${var.project}-${var.environment}-sg-emr-master"
  description = "EMR master node"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.environment}-sg-emr-master" }
}

resource "aws_security_group" "emr_slave" {
  name        = "${var.project}-${var.environment}-sg-emr-slave"
  description = "EMR core/task nodes (required even for single-node cluster)"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.environment}-sg-emr-slave" }
}

# Allow EMR internal communication between master and slave nodes
resource "aws_security_group_rule" "master_from_slave" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "tcp"
  security_group_id        = aws_security_group.emr_master.id
  source_security_group_id = aws_security_group.emr_slave.id
}

resource "aws_security_group_rule" "slave_from_master" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "tcp"
  security_group_id        = aws_security_group.emr_slave.id
  source_security_group_id = aws_security_group.emr_master.id
}

# ── EMR Cluster (single-node, auto-terminate after idle) ──────────────────────
resource "aws_emr_cluster" "nextcart" {
  name          = "${var.project}-${var.environment}-emr"
  release_label = "emr-6.15.0"
  applications  = ["Spark"]

  service_role = var.emr_service_role_arn
  log_uri      = "s3://${var.scripts_bucket}/emr-logs/"

  # Cluster stays alive waiting for steps; auto_termination_policy handles shutdown
  keep_job_flow_alive_when_no_steps = true

  auto_termination_policy {
    idle_timeout = var.idle_timeout_seconds
  }

  ec2_attributes {
    instance_profile                  = var.emr_ec2_profile_arn
    subnet_id                         = var.subnet_id
    emr_managed_master_security_group = aws_security_group.emr_master.id
    emr_managed_slave_security_group  = aws_security_group.emr_slave.id
  }

  # Single-node: master only, no core_instance_group
  master_instance_group {
    instance_type = var.master_instance_type
  }

  configurations_json = jsonencode([
    {
      Classification = "spark"
      Properties     = { "maximizeResourceAllocation" = "true" }
    },
    {
      Classification = "spark-defaults"
      Properties = {
        "spark.sql.adaptive.enabled"                    = "true"
        "spark.sql.adaptive.coalescePartitions.enabled" = "true"
      }
    }
  ])

  tags = { Name = "${var.project}-${var.environment}-emr" }
}
