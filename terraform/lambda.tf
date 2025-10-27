# ECR Repository for Lambda Worker
resource "aws_ecr_repository" "lambda_worker" {
  name                 = "${var.project_name}-lambda-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "${var.project_name}-lambda-worker"
    Environment = var.environment
  }
}

# ECR Lifecycle Policy for Lambda Worker
resource "aws_ecr_lifecycle_policy" "lambda_worker" {
  repository = aws_ecr_repository.lambda_worker.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_worker" {
  name              = "/aws/lambda/${var.project_name}-whisper-transcription"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-lambda-logs"
    Environment = var.environment
  }
}

# Security Group for Lambda
resource "aws_security_group" "lambda_transcription" {
  name_prefix = "${var.project_name}-lambda-transcription-"
  description = "Security group for Lambda transcription function"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-lambda-transcription-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Lambda Function (updated)
resource "aws_lambda_function" "whisper_transcription" {
  function_name = "${var.project_name}-whisper-transcription"
  role          = aws_iam_role.lambda_execution.arn

  package_type = "Image"
  image_uri    = "${aws_ecr_repository.lambda_worker.repository_url}:latest"

  timeout     = 900   # 15 minutes
  memory_size = 10240 # Maximum memory

  # VPC Configuration for EFS access
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda_transcription.id]
  }

  # EFS Mount Configuration
  file_system_config {
    arn              = aws_efs_access_point.lambda_model_access.arn
    local_mount_path = "/mnt/efs"
  }

  environment {
    variables = {
      S3_BUCKET_NAME     = aws_s3_bucket.audio_files.id
      TARGET_LANGUAGE    = "es"
      MODEL_PATH         = "/mnt/efs/models" # Model location from EFS
      HF_HOME            = "/mnt/efs/cache"  # Hugging Face cache
      TRANSFORMERS_CACHE = "/mnt/efs/cache"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_worker,
    aws_efs_mount_target.model_storage
  ]

  tags = {
    Name        = "${var.project_name}-whisper-transcription"
    Environment = var.environment
  }
}

# Lambda permission - restrict invocation to only ECS task role
resource "aws_lambda_permission" "ecs_invoke" {
  statement_id  = "AllowExecutionFromECSTask"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.whisper_transcription.function_name
  principal     = aws_iam_role.ecs_task.arn
}
