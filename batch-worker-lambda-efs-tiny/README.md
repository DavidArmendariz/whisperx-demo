# Batch Worker Lambda with EFS - Tiny Model (Fast Variant)

AWS Lambda function for **fast** audio transcription using faster-whisper's **tiny model** with EFS-mounted storage. This variant trades some accuracy for **5-7x faster processing** compared to the small model.

## Architecture

- **Runtime**: Python 3.12 (custom container)
- **Model Storage**: AWS EFS (mounted at `/mnt/efs/models`)
- **Model**: faster-whisper "tiny" (~75 MB) - **Multilingual**
- **Memory**: 10240 MB (10 GB)
- **Timeout**: 900 seconds (15 minutes)
- **VPC**: Required for EFS access
- **Speed**: 5-7x faster than "small" model
- **Languages**: Spanish and 90+ other languages

## Performance

| Metric           | Tiny Model                    | Small Model (standard)    |
| ---------------- | ----------------------------- | ------------------------- |
| Processing Speed | **~1-2 min** for 25-min audio | ~7-8 min for 25-min audio |
| Model Size       | 75 MB                         | 466 MB                    |
| Memory Usage     | ~1-2 GB                       | ~3 GB                     |
| Accuracy         | Good                          | Better                    |
| Languages        | 90+ (multilingual)            | 90+ (multilingual)        |

## Prerequisites

1. **EFS File System** with model downloaded
2. **VPC Configuration** with private subnets
3. **Security Groups** configured for Lambda-to-EFS communication
4. **ECR Repository** for Docker image
5. **IAM Role** with EFS, S3, and CloudWatch permissions

## Local Development

### Build Docker Image

```bash
cd batch-worker-lambda-efs

# Build for Lambda (linux/amd64 platform)
docker build --platform linux/amd64 -t whisperx-lambda-efs:latest .
```

### Test Locally (Optional)

```bash
# Run container locally
docker run --platform linux/amd64 -p 9000:8080 whisperx-lambda-efs:latest

# In another terminal, invoke the function
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{
    "s3_bucket": "your-bucket",
    "s3_input_key": "input/audio.mp3",
    "s3_output_key": "output/transcription.json"
  }'
```

## Deployment

### Option 1: Automated Script

```bash
# From project root
./deploy-lambda-efs.sh
```

This script:

- Authenticates with ECR
- Builds the Docker image
- Pushes to ECR
- Updates Lambda function

### Option 2: Manual Deployment

```bash
# 1. Set variables
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="761018890099"
ECR_REPO="whisperx-demo-lambda-worker"
LAMBDA_FUNCTION="whisperx-demo-whisper-transcription"

# 2. Login to ECR
aws ecr get-login-password --region $AWS_REGION --profile DavidArmendarizDW | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 3. Build image
cd batch-worker-lambda-efs
docker build --platform linux/amd64 \
  -t $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest .

# 4. Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# 5. Update Lambda
aws lambda update-function-code \
  --function-name $LAMBDA_FUNCTION \
  --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest \
  --region $AWS_REGION \
  --profile DavidArmendarizDW

# 6. Wait for update to complete
aws lambda wait function-updated \
  --function-name $LAMBDA_FUNCTION \
  --region $AWS_REGION \
  --profile DavidArmendarizDW
```

### Option 3: GitHub Actions

Push to `main` or `feature/efs` branch with changes in `batch-worker-lambda-efs/` directory.

## Lambda Configuration

### Environment Variables

Set in `terraform/lambda.tf`:

```hcl
environment {
  variables = {
    MODEL_PATH         = "/mnt/efs/models"
    MODEL_SIZE         = "small"
    DEVICE             = "cpu"
    COMPUTE_TYPE       = "int8"
    AWS_DEFAULT_REGION = "us-east-1"
  }
}
```

### VPC Configuration

Lambda must be in VPC to access EFS:

```hcl
vpc_config {
  subnet_ids         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids = [aws_security_group.lambda.id]
}
```

### EFS Mount

```hcl
file_system_config {
  arn              = aws_efs_access_point.model_access_point.arn
  local_mount_path = "/mnt/efs"
}
```

## Testing the Lambda

### Create Test Event

```bash
# Create test payload
cat > /tmp/lambda-test.json << 'EOF'
{
  "s3_bucket": "whisperx-demo-audio-prod-761018890099",
  "s3_input_key": "input/20251026-214438-34150cb6-0fc7-4356-9c53-054dbf94447d/audio.mp3",
  "s3_output_key": "output/20251026-214438-34150cb6-0fc7-4356-9c53-054dbf94447d/efstranscription.json"
}
EOF
```

### Invoke Lambda (Asynchronous)

```bash
# Invoke without waiting (recommended for long-running jobs)
aws lambda invoke \
  --function-name whisperx-demo-whisper-transcription \
  --invocation-type Event \
  --payload file:///tmp/lambda-test.json \
  --cli-binary-format raw-in-base64-out \
  --profile DavidArmendarizDW \
  /tmp/lambda-response.json

echo "Lambda invoked! Check CloudWatch Logs for progress."
```

### Invoke Lambda (Synchronous - for testing only)

```bash
# Wait for response (may timeout after 10 seconds in CLI)
aws lambda invoke \
  --function-name whisperx-demo-whisper-transcription \
  --invocation-type RequestResponse \
  --payload file:///tmp/lambda-test.json \
  --cli-binary-format raw-in-base64-out \
  --profile DavidArmendarizDW \
  /tmp/lambda-response.json

# View response
cat /tmp/lambda-response.json | jq .
```

## Monitoring

### View CloudWatch Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/whisperx-demo-whisper-transcription \
  --profile DavidArmendarizDW \
  --region us-east-1 \
  --follow

# View recent logs
aws logs tail /aws/lambda/whisperx-demo-whisper-transcription \
  --profile DavidArmendarizDW \
  --region us-east-1 \
  --since 10m
```

### Check Execution Time

```bash
# Get execution metrics
aws logs tail /aws/lambda/whisperx-demo-whisper-transcription \
  --profile DavidArmendarizDW \
  --region us-east-1 \
  --since 30m \
  --format short | grep "REPORT"
```

Example output:

```
REPORT RequestId: abc123...
  Duration: 477945.87 ms
  Billed Duration: 477946 ms
  Memory Size: 10240 MB
  Max Memory Used: 2985 MB
  Init Duration: 2053.67 ms
```

### Verify Output in S3

```bash
# List output files
aws s3 ls s3://whisperx-demo-audio-prod-761018890099/output/YOUR-SESSION-ID/ \
  --profile DavidArmendarizDW

# Download transcription
aws s3 cp s3://whisperx-demo-audio-prod-761018890099/output/YOUR-SESSION-ID/efstranscription.json \
  /tmp/transcription.json \
  --profile DavidArmendarizDW

# Preview transcription
cat /tmp/transcription.json | jq '.full_text' -r | head -20
```

## Performance Benchmarks

### Cold Start (First Execution)

- Model download from EFS: ~30-60 seconds
- Model loading into memory: ~20-30 seconds
- **Total overhead**: ~50-90 seconds

### Warm Start (Subsequent Executions)

- Model already in memory
- **No additional overhead**

### Transcription Speed

- **25-minute audio**: ~7-8 minutes (477 seconds measured)
- **Approximate ratio**: 1 minute of audio = ~19 seconds processing
- **Maximum supported**: ~15 minutes of transcription time = ~47 minutes of audio

### Memory Usage

- **Model in memory**: ~2-3 GB
- **Peak usage**: ~3-8 GB depending on audio length
- **Configured**: 10 GB (10240 MB)

## Limitations

### Lambda Timeout

- **Maximum**: 900 seconds (15 minutes)
- **Suitable for audio**: Up to ~45-50 minutes
- **For longer audio**: Use AWS Batch instead

### Audio Length Guidelines

| Audio Duration | Lambda Status | Recommendation               |
| -------------- | ------------- | ---------------------------- |
| < 10 minutes   | ✅ Optimal    | Lambda EFS                   |
| 10-30 minutes  | ✅ Good       | Lambda EFS                   |
| 30-45 minutes  | ⚠️ Works      | Lambda EFS (monitor closely) |
| > 45 minutes   | ❌ Timeout    | Use AWS Batch                |

## Troubleshooting

### Lambda Times Out

**Symptom**: Function times out after 900 seconds

**Solutions**:

1. Check audio length (must be < 45 minutes for Lambda)
2. Use AWS Batch for longer files
3. Split audio into chunks

### Model Not Found on EFS

**Symptom**: "Model not found at /mnt/efs/models"

**Solutions**:

```bash
# 1. Verify EFS mount
aws lambda get-function --function-name whisperx-demo-whisper-transcription \
  --profile DavidArmendarizDW \
  --query 'Configuration.FileSystemConfigs'

# 2. Check EFS contents via EC2
# See scripts/init_efs_model.sh for mounting instructions

# 3. Re-download model
# Run terraform/efs-init.tf to recreate init instance
```

### High Memory Usage

**Symptom**: "Memory limit exceeded" or near 10 GB usage

**Solutions**:

1. Use smaller model ("tiny" or "base" instead of "small")
2. Reduce audio chunk size
3. Increase Lambda memory (max 10 GB)

### VPC Timeout Issues

**Symptom**: Lambda cannot reach EFS or S3

**Solutions**:

```bash
# Verify security groups
aws ec2 describe-security-groups \
  --group-ids sg-0fc467f2e013f6eea \
  --profile DavidArmendarizDW

# Check EFS mount targets
aws efs describe-mount-targets \
  --file-system-id fs-02bce47280a1b0104 \
  --profile DavidArmendarizDW

# Verify VPC endpoints for S3 (if using private subnets)
aws ec2 describe-vpc-endpoints \
  --profile DavidArmendarizDW \
  --filters "Name=vpc-id,Values=vpc-02ebe1c834de831c3"
```

## Cost Optimization

### Lambda Pricing

- **Compute**: $0.0000166667 per GB-second
- **Requests**: $0.20 per 1M requests
- **Example (25-min audio)**: ~$0.13 per transcription

### EFS Pricing

- **Storage**: $0.30 per GB-month (Standard)
- **Model (~1 GB)**: ~$0.30/month
- **Data transfer**: Free within same AZ

### Tips

1. Use EFS lifecycle policies (move to IA after 30 days)
2. Keep Lambda warm for batch processing
3. Use asynchronous invocation to avoid API Gateway costs

## Development

### Update Dependencies

```bash
# Edit requirements.txt
vim requirements.txt

# Rebuild and deploy
./deploy-lambda-efs.sh
```

### Modify Worker Code

```bash
# Edit worker.py
vim worker.py

# Test changes
docker build --platform linux/amd64 -t whisperx-lambda-efs:latest .

# Deploy
./deploy-lambda-efs.sh
```

## Related Documentation

- [Architecture Overview](../ARCHITECTURE.md)
- [Deployment Guide](../DEPLOYMENT_EFS_LAMBDA.md)
- [EFS Initialization](../scripts/init_efs_model.sh)
- [Terraform Configuration](../terraform/)
- [GitHub Actions Workflow](../.github/workflows/deploy-batch-worker-lambda-efs.yml)

## Support

For issues or questions:

1. Check CloudWatch Logs for error details
2. Review Terraform state: `terraform show`
3. Verify EFS mount: `aws efs describe-file-systems`
4. Test with shorter audio files first
