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
    type                = "SPOT"
    allocation_strategy = "SPOT_CAPACITY_OPTIMIZED"
    bid_percentage      = 50

    instance_role = aws_iam_instance_profile.ecs_instance.arn
    instance_type = [var.batch_instance_type]

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
  name     = "${var.project_name}-job-queue"
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
    create_before_destroy = false
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
      },
      {
        type  = "GPU"
        value = "1"
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

    linuxParameters = {
      devices = [
        {
          hostPath      = "/dev/nvidia0"
          containerPath = "/dev/nvidia0"
          permissions   = ["READ", "WRITE", "MKNOD"]
        },
        {
          hostPath      = "/dev/nvidiactl"
          containerPath = "/dev/nvidiactl"
          permissions   = ["READ", "WRITE", "MKNOD"]
        },
        {
          hostPath      = "/dev/nvidia-uvm"
          containerPath = "/dev/nvidia-uvm"
          permissions   = ["READ", "WRITE", "MKNOD"]
        }
      ]
    }
  })

  tags = {
    Name        = "${var.project_name}-whisper-transcription"
    Environment = var.environment
  }
}
