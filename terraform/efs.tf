# EFS File System for Model Storage
resource "aws_efs_file_system" "model_storage" {
  creation_token   = "${var.project_name}-whisper-model"
  performance_mode = var.efs_performance_mode
  throughput_mode  = var.efs_throughput_mode
  encrypted        = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = {
    Name        = "${var.project_name}-whisper-model-efs"
    Environment = var.environment
  }
}

# EFS Mount Targets (one per availability zone in private subnets)
resource "aws_efs_mount_target" "model_storage" {
  count = length(var.availability_zones)

  file_system_id  = aws_efs_file_system.model_storage.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# Security Group for EFS
resource "aws_security_group" "efs" {
  name_prefix = "${var.project_name}-efs-"
  description = "Security group for EFS mount targets"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "NFS from Lambda"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda_transcription.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-efs-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# EFS Access Point for Lambda
resource "aws_efs_access_point" "lambda_model_access" {
  file_system_id = aws_efs_file_system.model_storage.id

  root_directory {
    path = "/models"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  posix_user {
    gid = 1000
    uid = 1000
  }

  tags = {
    Name        = "${var.project_name}-lambda-model-access"
    Environment = var.environment
  }
}