# WhisperX Audio Transcription Service

A production-ready audio transcription service using WhisperX, deployed on AWS with FastAPI and AWS Batch. This solution provides automatic speech recognition (ASR) with speaker diarization for Spanish audio files, running on GPU-enabled instances.

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Internet   │────▶│     ALB      │────▶│   FastAPI    │────▶│   S3 Bucket  │
│              │     │              │     │  (ECS/Fargate)│     │ (Audio Files)│
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │  AWS Batch   │
                                           │   (Submit)   │
                                           └──────────────┘
                                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │  Batch Job   │
                                           │ (g4dn.xlarge)│
                                           │  + WhisperX  │
                                           └──────────────┘
                                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │   S3 Bucket  │
                                           │(Transcripts) │
                                           └──────────────┘
```

### Key Components:

- **VPC**: Multi-AZ setup with public and private subnets
- **Application Load Balancer (ALB)**: Routes traffic to FastAPI service
- **ECS Fargate**: Hosts the FastAPI application in private subnets
- **S3**: Stores input audio files and output transcriptions
- **AWS Batch**: Manages GPU compute resources (g4dn.xlarge instances)
- **ECR**: Container registry for Docker images
- **IAM**: OIDC-based authentication for GitHub Actions

## 📋 Prerequisites

- AWS Account with appropriate permissions
- GitHub repository
- Terraform >= 1.6.0
- Docker
- AWS CLI
- Git

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/whisperx-demo.git
cd whisperx-demo
```

### 2. Configure Terraform Backend

Edit `terraform/main.tf` to configure your S3 backend:

```hcl
backend "s3" {
  bucket = "your-terraform-state-bucket"
  key    = "whisperx-demo/terraform.tfstate"
  region = "us-east-1"
}
```

### 3. Create Terraform Variables File

Create `terraform/terraform.tfvars`:

```hcl
aws_region     = "us-east-1"
project_name   = "whisperx-demo"
environment    = "prod"
github_org     = "your-github-username"
github_repo    = "whisperx-demo"

# Optional customizations
vpc_cidr              = "10.0.0.0/16"
availability_zones    = ["us-east-1a", "us-east-1b"]
fastapi_cpu          = 512
fastapi_memory       = 1024
fastapi_desired_count = 2
batch_max_vcpus      = 16
```

### 4. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

**Note**: Save the outputs after applying, especially:

- `alb_dns_name`
- `github_oidc_role_arn`
- `ecr_fastapi_repository_url`
- `ecr_batch_worker_repository_url`

### 5. Configure GitHub Secrets

Add the following secrets to your GitHub repository:

- `AWS_ROLE_ARN`: The IAM role ARN from Terraform output (`github_oidc_role_arn`)

**How to add secrets:**

1. Go to your repository on GitHub
2. Navigate to Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Add the `AWS_ROLE_ARN` secret

### 6. Initial Docker Image Push

For the first deployment, manually build and push the Docker images:

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push FastAPI image
cd fastapi-app
docker build -t <ecr-fastapi-url>:latest .
docker push <ecr-fastapi-url>:latest

# Build and push Batch Worker image
cd ../batch-worker
docker build -t <ecr-batch-worker-url>:latest .
docker push <ecr-batch-worker-url>:latest
```

After initial push, GitHub Actions will handle subsequent deployments.

## 📡 API Usage

### Upload Audio for Transcription

```bash
curl -X POST http://<alb-dns-name>/transcribe \
  -F "file=@audio.mp3" \
  -F "language=es"
```

**Response:**

```json
{
  "message": "Transcription job submitted successfully",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "batch_job_id": "abc123-def456",
  "s3_input_key": "input/20231024-120000-550e8400/audio.mp3",
  "s3_output_key": "output/20231024-120000-550e8400/transcription.json",
  "language": "es",
  "status": "SUBMITTED"
}
```

### Check Job Status

```bash
curl http://<alb-dns-name>/job/<batch-job-id>
```

**Response:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "batch_job_id": "abc123-def456",
  "status": "SUCCEEDED",
  "created_at": 1698163200,
  "started_at": 1698163230,
  "stopped_at": 1698163500,
  "status_reason": null
}
```

### Health Check

```bash
curl http://<alb-dns-name>/health
```

## 🔄 CI/CD Pipeline

The project includes three GitHub Actions workflows:

### 1. Deploy Terraform Infrastructure

- **Trigger**: Push to `main` or PR affecting `terraform/**`
- **Actions**: Plan and apply Terraform changes
- **File**: `.github/workflows/deploy-terraform.yml`

### 2. Deploy FastAPI Service

- **Trigger**: Push to `main` affecting `fastapi-app/**`
- **Actions**: Build Docker image, push to ECR, update ECS service
- **File**: `.github/workflows/deploy-fastapi.yml`

### 3. Deploy Batch Worker

- **Trigger**: Push to `main` affecting `batch-worker/**`
- **Actions**: Build Docker image, push to ECR, register new job definition
- **File**: `.github/workflows/deploy-batch-worker.yml`

All workflows use OIDC for secure, keyless authentication with AWS.

## 📊 Output Format

Transcription results are saved to S3 in JSON format:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "es",
  "device_used": "cuda",
  "full_text": "Hola, esto es una transcripción de prueba.",
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Hola, esto es una transcripción de prueba.",
      "speaker": "SPEAKER_00",
      "words": [
        {
          "word": "Hola",
          "start": 0.0,
          "end": 0.5,
          "score": 0.95
        }
      ]
    }
  ],
  "metadata": {
    "total_segments": 1,
    "s3_input_key": "input/20231024-120000-550e8400/audio.mp3",
    "s3_output_key": "output/20231024-120000-550e8400/transcription.json"
  }
}
```

## 🔧 Configuration

### Environment Variables

#### FastAPI Service

- `AWS_DEFAULT_REGION`: AWS region (default: us-east-1)
- `S3_BUCKET_NAME`: S3 bucket for audio files
- `BATCH_JOB_QUEUE`: AWS Batch job queue name
- `BATCH_JOB_DEFINITION`: AWS Batch job definition name

#### Batch Worker

- `AWS_DEFAULT_REGION`: AWS region
- `S3_BUCKET_NAME`: S3 bucket name
- `S3_INPUT_KEY`: S3 key for input audio file
- `S3_OUTPUT_KEY`: S3 key for output transcription
- `TARGET_LANGUAGE`: Language code (default: es)
- `JOB_ID`: Unique job identifier

### Supported Audio Formats

- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- FLAC (.flac)
- OGG (.ogg)
- MP4 (.mp4)
- AVI (.avi)

### Supported Languages

WhisperX supports 99 languages. Common codes:

- `es` - Spanish
- `en` - English
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese

[Full language list](https://github.com/openai/whisper#available-models-and-languages)

## 💰 Cost Optimization

- **Auto-scaling**: Batch compute environment scales to zero when idle
- **VPC Endpoints**: S3 VPC endpoint reduces data transfer costs
- **Spot Instances**: Consider using spot instances for Batch (modify Terraform)
- **S3 Lifecycle**: Automatic deletion of files after 30 days
- **Right-sizing**: Adjust Fargate CPU/memory based on actual usage

## 🔒 Security

- Private subnets for compute resources
- Security groups with minimal required access
- S3 bucket encryption at rest
- IAM roles with least privilege
- OIDC-based GitHub authentication (no long-lived credentials)
- Versioning enabled on S3 bucket
- Public access blocked on S3 bucket

## 📈 Monitoring

CloudWatch Logs are configured for:

- FastAPI application: `/ecs/whisperx-demo/fastapi`
- Batch jobs: `/aws/batch/whisperx-demo`

Container Insights is enabled on the ECS cluster.

## 🐛 Troubleshooting

### Batch Job Fails Immediately

- Check CloudWatch Logs: `/aws/batch/whisperx-demo`
- Verify S3 permissions on the Batch job role
- Ensure Docker image has GPU drivers (nvidia-smi should work)

### FastAPI Returns 500 Error

- Check CloudWatch Logs: `/ecs/whisperx-demo/fastapi`
- Verify environment variables are set correctly
- Ensure IAM role has permissions to submit Batch jobs

### GPU Not Available in Batch

- Verify g4dn.xlarge instances are available in your region/AZ
- Check Batch compute environment status
- Ensure launch template has correct AMI (ECS GPU-optimized)

### GitHub Actions Failing

- Verify `AWS_ROLE_ARN` secret is set correctly
- Check trust relationship on the IAM role
- Ensure OIDC provider thumbprints are current

## 🧪 Local Development

### Run FastAPI Locally

```bash
cd fastapi-app
pip install -r requirements.txt
export AWS_DEFAULT_REGION=us-east-1
export S3_BUCKET_NAME=your-bucket
export BATCH_JOB_QUEUE=your-queue
export BATCH_JOB_DEFINITION=your-job-def
uvicorn main:app --reload
```

### Test Batch Worker Locally (Requires GPU)

```bash
cd batch-worker
pip install -r requirements.txt
export S3_BUCKET_NAME=your-bucket
export S3_INPUT_KEY=input/test/audio.mp3
export S3_OUTPUT_KEY=output/test/result.json
export TARGET_LANGUAGE=es
python worker.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- [WhisperX](https://github.com/m-bain/whisperX) - Fast automatic speech recognition
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Terraform](https://www.terraform.io/) - Infrastructure as Code

## 📞 Support

For issues and questions:

- Open an issue on GitHub
- Check CloudWatch Logs for detailed error messages
- Review AWS Batch job logs for transcription failures

---

**Built with ❤️ using AWS, Terraform, and open-source tools**

---

# WhisperX Audio Transcription Service - lamda

---

# in batch-worker

````
```bash
docker build -t whisperx-batch-worker .
docker images whisperx-batch-worker
````

# Create lambda from terminal

```bash
aws ecr create-repository \
  --repository-name whisperx-batch-worker \
  --region us-east-1

# Login de Docker en ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 761018890099.dkr.ecr.us-east-1.amazonaws.com

#Tag and Push the Docker image
docker tag whisperx-batch-worker:latest 761018890099.dkr.ecr.us-east-1.amazonaws.com/whisperx-batch-worker:latest
docker push 761018890099.dkr.ecr.us-east-1.amazonaws.com/whisperx-batch-worker:latest

```

# Crear archivo de política de confianza

```bash
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Crear el rol
aws iam create-role \
  --role-name lambda-whisperx-role \
  --assume-role-policy-document file://trust-policy.json

# Adjuntar política básica de ejecución
aws iam attach-role-policy \
  --role-name lambda-whisperx-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Adjuntar acceso a S3 (si lo necesitas)
aws iam attach-role-policy \
  --role-name lambda-whisperx-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

# verificar el estado

```bash
aws lambda get-function --function-name whisperx-batch-worker --query 'Configuration.State'

# Ver toda la configuración
aws lambda get-function --function-name whisperx-batch-worker
```
