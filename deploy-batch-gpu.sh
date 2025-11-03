#!/bin/bash
set -e

AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="761018890099"
ECR_REPO="whisperx-demo-batch-gpu"
IMAGE_TAG="gpu-latest"
AWS_PROFILE="DavidArmendarizDW"

echo "Building GPU batch image..."
cd batch-worker-gpu
docker build -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG .

echo "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "Pushing image..."
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

echo "Done. Create/Update Batch job definition to reference the new image URL in Terraform or AWS Console."
