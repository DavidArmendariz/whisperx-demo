# CloudWatch Log Group for Batch Jobs
resource "aws_cloudwatch_log_group" "batch" {
  name              = "/aws/batch/${var.project_name}"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-batch-logs"
    Environment = var.environment
  }
}

# Launch Template for Batch Compute Environment
resource "aws_launch_template" "batch" {
  name_prefix = "${var.project_name}-batch-"

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "${var.project_name}-batch-instance"
      Environment = var.environment
    }
  }
}

# Batch Compute Environment
resource "aws_batch_compute_environment" "main" {
  type         = "MANAGED"
  service_role = aws_iam_role.batch_service.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"

    instance_role = aws_iam_instance_profile.ecs_instance.arn
    instance_type = [
      "c5.xlarge",
      "c5.2xlarge",
      "m5.xlarge",
      "m5.2xlarge"
    ]

    min_vcpus     = 0
    desired_vcpus = 0
    max_vcpus     = var.batch_max_vcpus

    subnets            = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.batch.id]

    launch_template {
      launch_template_id = aws_launch_template.batch.id
      version            = "$Latest"
    }

    tags = {
      Name        = "${var.project_name}-batch-compute"
      Environment = var.environment
    }
  }

  tags = {
    Name        = "${var.project_name}-compute-env"
    Environment = var.environment
  }

  depends_on = [aws_iam_role_policy_attachment.batch_service]
}

# Batch Job Queue
resource "aws_batch_job_queue" "main" {
  name     = "${var.project_name}-job-queue-${random_id.queue_suffix.hex}"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.main.arn
  }

  tags = {
    Name        = "${var.project_name}-job-queue"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
    replace_triggered_by = [
      aws_batch_compute_environment.main
    ]
  }
}

# Random ID for job queue name to avoid conflicts during recreation
resource "random_id" "queue_suffix" {
  byte_length = 4
  keepers = {
    compute_environment = aws_batch_compute_environment.main.arn
  }
}

# Batch Job Definition
resource "aws_batch_job_definition" "whisper_transcription" {
  name = "${var.project_name}-whisper-transcription"
  type = "container"

  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 3
    evaluate_on_exit {
      action           = "RETRY"
      on_status_reason = "Host EC2*"
    }
    evaluate_on_exit {
      action       = "EXIT"
      on_exit_code = "0"
    }
  }

  timeout {
    attempt_duration_seconds = 3600
  }

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch_worker.repository_url}:latest"

    jobRoleArn       = aws_iam_role.batch_job.arn
    executionRoleArn = aws_iam_role.batch_job_execution.arn

    resourceRequirements = [
      {
        type  = "VCPU"
        value = "4"
      },
      {
        type  = "MEMORY"
        value = "8192"
      }
    ]

    environment = [
      {
        name  = "AWS_DEFAULT_REGION"
        value = var.aws_region
      },
      {
        name  = "S3_BUCKET_NAME"
        value = aws_s3_bucket.audio_files.id
      },
      {
        name  = "TARGET_LANGUAGE"
        value = "es"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "batch"
      }
    }
  })

  tags = {
    Name        = "${var.project_name}-whisper-transcription"
    Environment = var.environment
  }
}
