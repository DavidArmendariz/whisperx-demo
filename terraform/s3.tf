# S3 Bucket for Audio Files
resource "aws_s3_bucket" "audio_files" {
  bucket        = "${var.project_name}-audio-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name        = "${var.project_name}-audio-files"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "audio_files" {
  bucket = aws_s3_bucket.audio_files.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audio_files" {
  bucket = aws_s3_bucket.audio_files.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audio_files" {
  bucket = aws_s3_bucket.audio_files.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "audio_files" {
  bucket = aws_s3_bucket.audio_files.id

  rule {
    id     = "delete-old-files"
    status = "Enabled"

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
