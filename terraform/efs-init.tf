# Temporary EC2 instance to initialize EFS with Whisper model
# This is a one-time operation - destroy this resource after model is downloaded

# IAM Role for EC2 instance
resource "aws_iam_role" "efs_init" {
  name = "${var.project_name}-efs-init-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-efs-init-role"
    Environment = var.environment
  }
}

# Attach SSM policy for Session Manager access
resource "aws_iam_role_policy_attachment" "efs_init_ssm" {
  role       = aws_iam_role.efs_init.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Instance profile
resource "aws_iam_instance_profile" "efs_init" {
  name = "${var.project_name}-efs-init-profile"
  role = aws_iam_role.efs_init.name
}

# Security group for the init instance
resource "aws_security_group" "efs_init" {
  name_prefix = "${var.project_name}-efs-init-"
  description = "Security group for EFS initialization instance"
  vpc_id      = aws_vpc.main.id

  # Allow NFS to EFS
  egress {
    description     = "NFS to EFS"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.efs.id]
  }

  # Allow HTTPS for package downloads
  egress {
    description = "HTTPS for downloads"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow HTTP for package downloads
  egress {
    description = "HTTP for downloads"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-efs-init-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Update EFS security group to allow access from init instance
resource "aws_security_group_rule" "efs_from_init" {
  type                     = "ingress"
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  security_group_id        = aws_security_group.efs.id
  source_security_group_id = aws_security_group.efs_init.id
  description              = "NFS from EFS init instance"
}

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# User data script to download model
locals {
  efs_init_user_data = <<-EOF
    #!/bin/bash
    set -e
    
    # Log file
    LOG_FILE="/var/log/efs-init.log"
    exec > >(tee -a $LOG_FILE) 2>&1
    
    echo "=========================================="
    echo "Starting EFS Model Initialization"
    echo "Time: $(date)"
    echo "=========================================="
    
    # Wait for EFS mount targets to be available
    echo "Waiting for EFS to be ready..."
    sleep 30
    
    # Install required packages
    echo "Installing Python 3.12 and dependencies..."
    dnf install -y python3.12 python3-pip nfs-utils
    
    # Install faster-whisper for ec2-user
    echo "Installing faster-whisper..."
    sudo -u ec2-user pip3.12 install --user faster-whisper
    
    # Mount EFS
    echo "Mounting EFS: ${aws_efs_file_system.model_storage.dns_name}"
    mkdir -p /mnt/efs
    mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2 \
      ${aws_efs_file_system.model_storage.dns_name}:/ /mnt/efs
    
    # Verify mount
    df -h | grep efs
    echo "EFS mounted successfully"
    
    # Create directories
    mkdir -p /mnt/efs/models
    mkdir -p /mnt/efs/cache
    
    # Download model as ec2-user
    echo "Downloading faster-whisper model to EFS..."
    echo "This will take 5-10 minutes depending on connection speed..."
    
    sudo -u ec2-user python3.12 << 'PYTHON_EOF'
import sys
import logging
from faster_whisper import WhisperModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("Downloading faster-whisper 'small' model...")
print("=" * 60)

try:
    model = WhisperModel(
        'small',
        device='cpu',
        compute_type='int8',
        download_root='/mnt/efs/models'
    )
    print("\n" + "=" * 60)
    print("✅ Model downloaded successfully!")
    print("=" * 60)
    sys.exit(0)
except Exception as e:
    print(f"\n❌ Error downloading model: {e}")
    sys.exit(1)
PYTHON_EOF
    
    # Set proper permissions
    echo "Setting permissions..."
    chown -R 1000:1000 /mnt/efs/models
    chown -R 1000:1000 /mnt/efs/cache
    chmod -R 755 /mnt/efs/models
    chmod -R 777 /mnt/efs/cache
    
    # Verify model exists
    echo ""
    echo "=========================================="
    echo "Model files on EFS:"
    ls -lh /mnt/efs/models/
    echo ""
    echo "Disk usage:"
    du -sh /mnt/efs/models/*
    echo "=========================================="
    
    # Create completion marker
    echo "Model initialization completed at $(date)" > /mnt/efs/.model-initialized
    
    echo ""
    echo "=========================================="
    echo "✅ EFS Model Initialization Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Verify model exists: ls -lh /mnt/efs/models/"
    echo "2. Destroy this EC2 instance: terraform destroy -target=aws_instance.efs_init"
    echo ""
  EOF
}

# EC2 instance for EFS initialization
resource "aws_instance" "efs_init" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.medium"

  subnet_id                   = aws_subnet.private[0].id
  vpc_security_group_ids      = [aws_security_group.efs_init.id]
  iam_instance_profile        = aws_iam_instance_profile.efs_init.name
  associate_public_ip_address = false

  user_data = local.efs_init_user_data

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name        = "${var.project_name}-efs-init"
    Environment = var.environment
    Purpose     = "Temporary - EFS model initialization"
  }

  # Ensure EFS is ready before creating instance
  depends_on = [
    aws_efs_mount_target.model_storage,
    aws_security_group_rule.efs_from_init
  ]

  lifecycle {
    ignore_changes = [
      user_data,
      ami
    ]
  }
}

# Output for monitoring
output "efs_init_instance_id" {
  description = "ID of the EFS initialization instance"
  value       = aws_instance.efs_init.id
}

output "efs_init_status_command" {
  description = "Command to check initialization status"
  value       = "aws ssm start-session --target ${aws_instance.efs_init.id} && tail -f /var/log/efs-init.log"
}

output "efs_init_destroy_command" {
  description = "Command to destroy the init instance after completion"
  value       = "terraform destroy -target=aws_instance.efs_init -target=aws_iam_role.efs_init -target=aws_iam_instance_profile.efs_init -target=aws_security_group.efs_init"
}
