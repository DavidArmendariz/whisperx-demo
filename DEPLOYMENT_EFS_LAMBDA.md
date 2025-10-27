# EFS-Based Lambda Deployment Guide

This guide covers deploying the Dockerized Lambda function with faster-whisper model stored on EFS.

## Architecture Overview

- **Lambda Function**: `batch-worker-lambda-efs/` - Dockerized Python Lambda using AWS Lambda Runtime Interface Client
- **Base Image**: `python:3.12-slim`
- **Model Storage**: EFS (mounted at `/mnt/efs`)
- **VPC**: Lambda runs in private subnets with EFS mount targets
- **ECR Repository**: `<project>-lambda-worker`

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** installed and initialized
3. **Docker** installed (for building the Lambda image)
4. **EFS** deployed via Terraform with model pre-loaded

## Step-by-Step Deployment

### 1. Deploy Infrastructure with Terraform

```bash
cd terraform

# Initialize Terraform (first time only)
terraform init

# Review the plan
terraform plan

# Apply infrastructure changes
terraform apply

# Note the outputs - you'll need them
terraform output efs_file_system_id
terraform output lambda_worker_repository_url
```

### 2. Initialize Model on EFS

Before deploying the Lambda, you need to download the faster-whisper model to EFS. This is a **one-time setup**.

Run the initialization helper script to get detailed instructions:

```bash
./scripts/init_efs_model.sh
```

This script will display step-by-step instructions for mounting EFS and downloading the model.

#### Quick Setup (Copy-Paste to EC2 Instance)

```bash
# 1. Launch an EC2 instance in the private subnet (Amazon Linux 2023)
#    - Use the same VPC as Lambda
#    - Attach the EFS security group
#    - Use Systems Manager Session Manager to connect (no SSH needed)

# 2. Connect via Session Manager and mount EFS
EFS_ID=$(cd terraform && terraform output -raw efs_file_system_id)
EFS_DNS="${EFS_ID}.efs.${AWS_REGION}.amazonaws.com"

sudo mkdir -p /mnt/efs
sudo mount -t nfs4 -o nfsvers=4.1 ${EFS_DNS}:/ /mnt/efs

# 3. Install Python and faster-whisper
sudo dnf install python3.12 python3-pip -y
pip3.12 install --user faster-whisper

# 4. Download the model to EFS (this takes a few minutes)
python3.12 << 'EOF'
from faster_whisper import WhisperModel
import logging

logging.basicConfig(level=logging.INFO)
print("Downloading faster-whisper 'small' model to EFS...")

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
    download_root="/mnt/efs/models"
)

print("✓ Model downloaded successfully!")
print("Verifying...")
import os
for root, dirs, files in os.walk("/mnt/efs/models"):
    level = root.replace("/mnt/efs/models", "").count(os.sep)
    indent = " " * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
EOF

# 5. Verify the model exists
ls -lh /mnt/efs/models/
sudo du -sh /mnt/efs/models/*

# 6. Create cache directory with proper permissions
sudo mkdir -p /mnt/efs/cache
sudo chmod 777 /mnt/efs/cache

# 7. Terminate the EC2 instance (no longer needed)
```

#### Option B: Using ECS Task (Alternative)

Create a temporary ECS task that mounts EFS and downloads the model.

### 3. Update Requirements File

Ensure `batch-worker-lambda-efs/requirements.txt` includes all necessary dependencies:

```bash
cd batch-worker-lambda-efs
cat > requirements.txt << 'EOF'
boto3==1.40.59
faster-whisper==1.1.0
EOF
```

### 4. Build and Push Docker Image to ECR

```bash
cd batch-worker-lambda-efs

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
ECR_REPO_NAME="whisperx-demo-lambda-worker"  # Or get from terraform output
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build the Docker image for Lambda (must be linux/amd64)
docker build --platform linux/amd64 -t ${ECR_REPO_NAME}:latest .

# Tag the image
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest

# Push to ECR
docker push ${ECR_URI}:latest

echo "✓ Docker image pushed successfully to: ${ECR_URI}:latest"
```

### 5. Update Lambda Function

After pushing the image, update the Lambda function to use it:

```bash
# Trigger a Lambda function update to pull the new image
aws lambda update-function-code \
    --function-name whisperx-demo-whisper-transcription \
    --image-uri ${ECR_URI}:latest \
    --region ${AWS_REGION}

# Wait for the update to complete
aws lambda wait function-updated \
    --function-name whisperx-demo-whisper-transcription \
    --region ${AWS_REGION}

echo "✓ Lambda function updated successfully"
```

### 6. Test the Lambda Function

Create a test event and invoke the Lambda:

```bash
# Upload a test audio file to S3
aws s3 cp test-audio.mp3 s3://whisperx-demo-audio-files/input/test/sample.mp3

# Create test event
cat > /tmp/lambda-test-event.json << 'EOF'
{
  "s3_input_key": "input/test/sample.mp3",
  "s3_output_key": "output/test/transcription.json",
  "target_language": "es",
  "job_id": "test-job-001"
}
EOF

# Invoke Lambda function
aws lambda invoke \
    --function-name whisperx-demo-whisper-transcription \
    --payload file:///tmp/lambda-test-event.json \
    --region ${AWS_REGION} \
    /tmp/lambda-response.json

# Check response
cat /tmp/lambda-response.json

# Download the transcription result
aws s3 cp s3://whisperx-demo-audio-files/output/test/transcription.json /tmp/

# View the transcription
cat /tmp/transcription.json | jq '.'
```

### 7. Monitor Lambda Execution

```bash
# View CloudWatch Logs
aws logs tail /aws/lambda/whisperx-demo-whisper-transcription --follow

# Check Lambda metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=whisperx-demo-whisper-transcription \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average,Maximum \
    --region ${AWS_REGION}
```

## Quick Deployment Script

Create `deploy-lambda.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying Lambda with EFS..."

# Configuration
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME="whisperx-demo"
ECR_REPO_NAME="${PROJECT_NAME}-lambda-worker"
LAMBDA_FUNCTION_NAME="${PROJECT_NAME}-whisper-transcription"

cd batch-worker-lambda-efs

# Login to ECR
echo "📦 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build Docker image
echo "🏗️  Building Docker image..."
docker build --platform linux/amd64 -t ${ECR_REPO_NAME}:latest .

# Tag and push
echo "⬆️  Pushing to ECR..."
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest
docker push ${ECR_URI}:latest

# Update Lambda
echo "🔄 Updating Lambda function..."
aws lambda update-function-code \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --image-uri ${ECR_URI}:latest \
    --region ${AWS_REGION}

echo "⏳ Waiting for Lambda update to complete..."
aws lambda wait function-updated \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --region ${AWS_REGION}

echo "✅ Deployment complete!"
echo "📊 View logs: aws logs tail /aws/lambda/${LAMBDA_FUNCTION_NAME} --follow"
```

Make it executable:

```bash
chmod +x deploy-lambda.sh
```

## Dockerfile Details

The `batch-worker-lambda-efs/Dockerfile` uses:

- **Base Image**: `python:3.12-slim` (official Python image)
- **Lambda Runtime**: `awslambdaric` (AWS Lambda Runtime Interface Client for custom runtimes)
- **Entry Point**: `python -m awslambdaric` with handler `worker.handler`

Key differences from standard Lambda:

- Uses Python base image instead of AWS Lambda base
- Installs `awslambdaric` to provide Lambda runtime interface
- Code is copied to `/var/task/` (Lambda's working directory)
- Model is loaded from EFS at `/mnt/efs/models` (not included in image)

## Troubleshooting

### Lambda Timeout During Cold Start

If Lambda times out on first invocation:

- Check EFS mount is successful in CloudWatch Logs
- Verify model exists on EFS: `/mnt/efs/models/small/`
- Increase Lambda timeout (current: 900s / 15 minutes)

### EFS Mount Fails

```bash
# Check VPC configuration
aws lambda get-function-configuration \
    --function-name whisperx-demo-whisper-transcription \
    --query 'VpcConfig'

# Verify EFS mount targets
EFS_ID=$(cd terraform && terraform output -raw efs_file_system_id)
aws efs describe-mount-targets --file-system-id ${EFS_ID}

# Check security groups allow NFS (port 2049)
```

### Docker Build Issues

```bash
# Clean Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache --platform linux/amd64 -t lambda-worker:latest .

# Test locally with Lambda Runtime Interface Emulator
docker run --platform linux/amd64 -p 9000:8080 lambda-worker:latest
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'
```

### Permission Errors on EFS

```bash
# Connect to EC2 in same VPC and check permissions
ls -la /mnt/efs/
ls -la /mnt/efs/models/

# Fix permissions if needed
sudo chown -R 1000:1000 /mnt/efs/models/
sudo chmod -R 755 /mnt/efs/models/
sudo chmod -R 777 /mnt/efs/cache/
```

## Cost Optimization

1. **EFS Lifecycle Policy**: Automatically moves files to Infrequent Access after 30 days
2. **Lambda Memory**: Start with 10GB, reduce if not needed (check CloudWatch metrics)
3. **VPC Endpoints**: Use VPC endpoints for S3 to avoid NAT Gateway costs
4. **Reserved Concurrency**: Set if predictable workload to control costs

## Performance Tips

1. **Warm Starts**: Keep Lambda warm by invoking every 5-10 minutes
2. **Provisioned Concurrency**: Set to 1-2 if need instant response
3. **EFS Bursting**: Monitor burst credit balance in CloudWatch
4. **Model Size**: Start with 'small', upgrade to 'medium' if accuracy needs improve

## Next Steps

- Set up S3 event notifications to trigger Lambda automatically
- Add error handling and retry logic
- Implement DLQ (Dead Letter Queue) for failed invocations
- Add X-Ray tracing for debugging
- Create API Gateway endpoint for synchronous invocations
