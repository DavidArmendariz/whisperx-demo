output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for audio files"
  value       = aws_s3_bucket.audio_files.id
}

output "ecr_fastapi_repository_url" {
  description = "URL of the FastAPI ECR repository"
  value       = aws_ecr_repository.fastapi.repository_url
}

output "ecr_batch_worker_repository_url" {
  description = "URL of the Batch worker ECR repository"
  value       = aws_ecr_repository.batch_worker.repository_url
}

output "batch_job_queue_arn" {
  description = "ARN of the Batch job queue"
  value       = aws_batch_job_queue.main.arn
}

output "batch_job_definition_arn" {
  description = "ARN of the Batch job definition"
  value       = aws_batch_job_definition.whisper_transcription.arn
}

# Lambda outputs
output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.whisper_transcription.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.whisper_transcription.arn
}

output "lambda_ecr_repository_url" {
  description = "URL of the ECR repository for Lambda worker"
  value       = aws_ecr_repository.lambda_worker.repository_url
}
