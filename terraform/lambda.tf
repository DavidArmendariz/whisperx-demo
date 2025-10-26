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

# Lambda Function
resource "aws_lambda_function" "whisper_transcription" {
  function_name = "${var.project_name}-whisper-transcription"
  role          = aws_iam_role.lambda_execution.arn

  package_type = "Image"
  image_uri    = "${aws_ecr_repository.lambda_worker.repository_url}:latest"

  timeout     = 900   # 15 minutes (max for Lambda)
  memory_size = 10240 # Maximum memory for maximum CPU allocation

  environment {
    variables = {
      S3_BUCKET_NAME     = aws_s3_bucket.audio_files.id
      TARGET_LANGUAGE    = "es"
      HF_HOME            = "/tmp/huggingface"
      TRANSFORMERS_CACHE = "/tmp/huggingface"
      XDG_CACHE_HOME     = "/tmp"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_worker,
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
