#!/bin/bash
set -e

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="761018890099"
ECR_REPO="whisperx-demo-lambda-worker"
LAMBDA_FUNCTION="whisperx-demo-whisper-transcription"
AWS_PROFILE="DavidArmendarizDW"
IMAGE_TAG="tiny"

echo "🚀 Deploying Lambda with Tiny Model (Fast & Multilingual)..."
echo ""

# Login to ECR
echo "📝 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Docker image
echo ""
echo "🔨 Building Docker image (tiny model variant for Spanish)..."
cd batch-worker-lambda-efs-tiny
docker build --platform linux/amd64 \
  -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG .

# Tag as latest too
docker tag $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Push to ECR
echo ""
echo "📤 Pushing to ECR..."
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Update Lambda function
echo ""
echo "🔄 Updating Lambda function..."
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION \
  --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG \
  --region $AWS_REGION \
  --profile $AWS_PROFILE

# Wait for update to complete
echo ""
echo "⏳ Waiting for Lambda to update..."
aws lambda wait function-updated \
  --function-name $LAMBDA_FUNCTION \
  --region $AWS_REGION \
  --profile $AWS_PROFILE

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Lambda Configuration:"
aws lambda get-function-configuration \
  --function-name $LAMBDA_FUNCTION \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query '{FunctionName:FunctionName,Memory:MemorySize,Timeout:Timeout,LastModified:LastModified}' \
  --output table

echo ""
echo "🎯 Model: tiny (Multilingual - supports Spanish)"
echo "⚡ Expected speed: 5-7x faster than 'small' model"
echo "📝 Expected time for 25-min audio: ~1-2 minutes"
echo "🌍 Language support: Spanish and 90+ other languages"
echo ""
echo "🧪 Test with:"
echo "  aws lambda invoke --function-name $LAMBDA_FUNCTION \\"
echo "    --invocation-type Event \\"
echo "    --payload file:///tmp/lambda-test.json \\"
echo "    --profile $AWS_PROFILE \\"
echo "    /tmp/response.json"
