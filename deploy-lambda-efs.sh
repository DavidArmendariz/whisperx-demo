#!/bin/bash
set -e

echo "🚀 Deploying Lambda with EFS..."

# Configuration
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME="whisperx-demo"
ECR_REPO_NAME="${PROJECT_NAME}-lambda-worker"
LAMBDA_FUNCTION_NAME="${PROJECT_NAME}-whisper-transcription"

cd "$(dirname "$0")/batch-worker-lambda-efs"

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

echo ""
echo "✅ Deployment complete!"
echo "📊 View logs: aws logs tail /aws/lambda/${LAMBDA_FUNCTION_NAME} --follow"
echo "🔗 ECR Image: ${ECR_URI}:latest"
