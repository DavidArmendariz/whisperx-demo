# Quick Reference Guide

## Common Commands

### Terraform

```bash
# Initialize
cd terraform && terraform init

# Plan changes
terraform plan -var-file=terraform.tfvars

# Apply changes
terraform apply -var-file=terraform.tfvars

# Destroy infrastructure
terraform destroy -var-file=terraform.tfvars

# View outputs
terraform output

# Get specific output
terraform output -raw alb_dns_name
```

### Docker

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# Build FastAPI
cd fastapi-app
docker build -t whisperx-fastapi .

# Build Batch Worker
cd batch-worker
docker build -t whisperx-worker .

# Push to ECR
docker tag whisperx-fastapi:latest <ecr-url>:latest
docker push <ecr-url>:latest
```

### AWS CLI

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster whisperx-demo-cluster \
  --services whisperx-demo-fastapi-service

# Force new deployment
aws ecs update-service \
  --cluster whisperx-demo-cluster \
  --service whisperx-demo-fastapi-service \
  --force-new-deployment

# List Batch jobs
aws batch list-jobs --job-queue whisperx-demo-job-queue

# Describe specific job
aws batch describe-jobs --jobs <job-id>

# View CloudWatch logs (FastAPI)
aws logs tail /ecs/whisperx-demo/fastapi --follow

# View CloudWatch logs (Batch)
aws logs tail /aws/batch/whisperx-demo --follow

# List S3 bucket contents
aws s3 ls s3://$(cd terraform && terraform output -raw s3_bucket_name)/

# Download transcription result
aws s3 cp s3://<bucket>/<output-key> result.json
```

### Testing

```bash
# Run test suite
python3 test_api.py --url http://<alb-dns> --audio sample.mp3

# Test health endpoint only
python3 test_api.py --url http://<alb-dns> --skip-transcription

# Using curl
curl http://<alb-dns>/health

# Upload audio
curl -X POST http://<alb-dns>/transcribe \
  -F "file=@audio.mp3" \
  -F "language=es"

# Check job status
curl http://<alb-dns>/job/<batch-job-id>
```

## Environment Variables

### FastAPI

- `AWS_DEFAULT_REGION` - AWS region
- `S3_BUCKET_NAME` - S3 bucket name
- `BATCH_JOB_QUEUE` - Batch job queue name
- `BATCH_JOB_DEFINITION` - Batch job definition name

### Batch Worker

- `AWS_DEFAULT_REGION` - AWS region
- `S3_BUCKET_NAME` - S3 bucket name
- `S3_INPUT_KEY` - Input audio S3 key
- `S3_OUTPUT_KEY` - Output transcription S3 key
- `TARGET_LANGUAGE` - Language code (es, en, etc.)
- `JOB_ID` - Unique job identifier

## API Endpoints

| Method | Endpoint              | Description                |
| ------ | --------------------- | -------------------------- |
| GET    | `/`                   | API information            |
| GET    | `/health`             | Health check               |
| POST   | `/transcribe`         | Upload audio and start job |
| GET    | `/job/{batch_job_id}` | Get job status             |

## Batch Job Statuses

- `SUBMITTED` - Job submitted to queue
- `PENDING` - Job waiting for resources
- `RUNNABLE` - Job ready to run
- `STARTING` - Job starting
- `RUNNING` - Job executing
- `SUCCEEDED` - Job completed successfully
- `FAILED` - Job failed

## Resource Names

All resources are prefixed with the project name (`whisperx-demo` by default):

- **VPC**: `whisperx-demo-vpc`
- **ECS Cluster**: `whisperx-demo-cluster`
- **ECS Service**: `whisperx-demo-fastapi-service`
- **ALB**: `whisperx-demo-alb`
- **S3 Bucket**: `whisperx-demo-audio-{env}-{account-id}`
- **ECR Repos**:
  - `whisperx-demo-fastapi`
  - `whisperx-demo-batch-worker`
- **Batch Queue**: `whisperx-demo-job-queue`
- **Batch Job Def**: `whisperx-demo-whisper-transcription`

## Supported Audio Formats

- MP3 (`.mp3`)
- WAV (`.wav`)
- M4A (`.m4a`)
- FLAC (`.flac`)
- OGG (`.ogg`)
- MP4 (`.mp4`)
- AVI (`.avi`)

## Language Codes

Common language codes for the `language` parameter:

- `es` - Spanish
- `en` - English
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `ru` - Russian
- `ja` - Japanese
- `ko` - Korean
- `zh` - Chinese

[Full list](https://github.com/openai/whisper#available-models-and-languages)

## Cost Estimates (us-east-1)

Approximate monthly costs for light usage:

- **ECS Fargate** (2 tasks): ~$30/month
- **NAT Gateway** (2 AZs): ~$65/month
- **ALB**: ~$23/month
- **S3**: ~$1-5/month (depends on storage)
- **CloudWatch Logs**: ~$1-5/month
- **Batch** (g4dn.xlarge): $0.526/hour when running
  - Example: 10 hours/month = ~$5.26/month

**Total baseline**: ~$125/month + compute usage

To reduce costs:

- Use 1 NAT Gateway instead of 2
- Reduce Fargate task count
- Use Spot instances for Batch
- Reduce log retention period

## Troubleshooting Quick Checks

```bash
# Check if ECS tasks are running
aws ecs list-tasks --cluster whisperx-demo-cluster

# Check task definition
aws ecs describe-task-definition --task-definition whisperx-demo-fastapi

# Check security groups
aws ec2 describe-security-groups --filters Name=group-name,Values=whisperx-demo-*

# Check Batch compute environment
aws batch describe-compute-environments | jq '.computeEnvironments[] | select(.computeEnvironmentName | contains("whisperx"))'

# View recent Batch jobs
aws batch list-jobs --job-queue whisperx-demo-job-queue --job-status FAILED

# Check ECR images
aws ecr describe-images --repository-name whisperx-demo-fastapi
aws ecr describe-images --repository-name whisperx-demo-batch-worker
```

## GitHub Actions Secrets

Required secret:

- `AWS_ROLE_ARN` - ARN of the GitHub OIDC IAM role

Get the value:

```bash
cd terraform
terraform output -raw github_oidc_role_arn
```

## Useful Links

- [WhisperX GitHub](https://github.com/m-bain/whisperX)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AWS Batch Documentation](https://docs.aws.amazon.com/batch/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [GitHub Actions AWS OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
