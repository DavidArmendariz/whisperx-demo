// GPU Batch Compute Environment and Job Definition
resource "aws_batch_compute_environment" "gpu" {
  type         = "MANAGED"
  service_role = aws_iam_role.batch_service.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"

    instance_role = aws_iam_instance_profile.ecs_instance.arn
    instance_type = [
      "g4dn.xlarge", # T4 GPU
      "g5.xlarge"    # A10G (if available)
    ]

  min_vcpus     = 0
  # Set desired_vcpus to 1 so Batch will attempt to launch at least one GPU instance
  # and move RUNNABLE jobs to STARTING. This helps when the compute environment
  # is idle and we want to trigger scale-up immediately.
  desired_vcpus = 1
  max_vcpus     = var.batch_gpu_max_vcpus

    subnets            = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.batch.id]

    launch_template {
      launch_template_id = aws_launch_template.batch.id
      version            = "$Latest"
    }

    tags = {
      Name        = "${var.project_name}-batch-gpu-compute"
      Environment = var.environment
    }
  }

  tags = {
    Name        = "${var.project_name}-compute-env-gpu"
    Environment = var.environment
  }

  depends_on = [aws_iam_role_policy_attachment.batch_service]
}

// Job Queue for GPU compute environment
resource "aws_batch_job_queue" "gpu" {
  name     = "${var.project_name}-job-queue-gpu-${random_id.queue_suffix.hex}"
  state    = "ENABLED"
  priority = 10

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.gpu.arn
  }

  tags = {
    Name        = "${var.project_name}-job-queue-gpu"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

// GPU Job Definition
resource "aws_batch_job_definition" "whisper_transcription_gpu" {
  name = "${var.project_name}-whisper-transcription-gpu"
  type = "container"

  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 3
  }

  timeout {
    attempt_duration_seconds = 7200 // 2 hours
  }

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch_worker.repository_url}:latest"

    jobRoleArn       = aws_iam_role.batch_job.arn
    executionRoleArn = aws_iam_role.batch_job_execution.arn

    resourceRequirements = [
      { type = "VCPU" , value = "8" },
      { type = "MEMORY", value = "32768" },
      { type = "GPU", value = "1" }
    ]

    environment = [
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
      { name = "S3_BUCKET_NAME", value = aws_s3_bucket.audio_files.id },
      { name = "TARGET_LANGUAGE", value = "es" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "batch-gpu"
      }
    }
  })

  tags = {
    Name        = "${var.project_name}-whisper-transcription-gpu"
    Environment = var.environment
  }
}
