# Deployment Guide

This guide walks you through deploying the WhisperX Audio Transcription Service to AWS.

## Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured
- [ ] Terraform >= 1.13.4 installed
- [ ] Docker installed
- [ ] GitHub repository created
- [ ] Git installed

## Step-by-Step Deployment

### Step 1: Prepare AWS Account

1. **Create S3 bucket for Terraform state** (optional but recommended):

```bash
aws s3 mb s3://your-terraform-state-bucket --region us-east-1
aws s3api put-bucket-versioning \
  --bucket your-terraform-state-bucket \
  --versioning-configuration Status=Enabled
```

### Step 2: Configure Terraform

1. **Update backend configuration** in `terraform/main.tf`:

```hcl
backend "s3" {
  bucket = "your-terraform-state-bucket"
  key    = "whisperx-demo/terraform.tfstate"
  region = "us-east-1"
}
```

2. **Create `terraform.tfvars`** from the example:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

3. **Edit `terraform.tfvars`** with your values:

```hcl
github_org  = "your-github-username"
github_repo = "your-repo-name"
```

### Step 3: Deploy Infrastructure

```bash
cd terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply the configuration
terraform apply
```

**Important**: Save the outputs! You'll need them later.

```bash
# Save outputs to a file
terraform output > ../deployment-outputs.txt
```

### Step 4: Configure GitHub Actions

1. **Get the GitHub OIDC Role ARN**:

```bash
cd terraform
terraform output -raw github_oidc_role_arn
```

2. **Add GitHub Secret**:

   - Go to your GitHub repository
   - Navigate to: Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `AWS_ROLE_ARN`
   - Value: (paste the ARN from step 1)

## Post-Deployment Configuration

### Optional: Configure Custom Domain

1. **Create ACM certificate** for your domain in `us-east-1`
2. **Update Terraform** to add HTTPS listener:

Add to `terraform/ecs.tf`:

```hcl
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = "arn:aws:acm:region:account:certificate/xxxxx"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi.arn
  }
}
```

3. **Create Route53 record** pointing to ALB

### Optional: Enable Spot Instances for Batch

To reduce costs, modify `terraform/batch.tf`:

```hcl
compute_resources {
  type                = "SPOT"  # Change from "EC2"
  allocation_strategy = "SPOT_CAPACITY_OPTIMIZED"
  bid_percentage      = 50      # Bid at 50% of on-demand price
  # ... rest of configuration
}
```

## Monitoring Setup

### CloudWatch Dashboards

Create a dashboard to monitor your services:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name whisperx-demo \
  --dashboard-body file://cloudwatch-dashboard.json
```

### CloudWatch Alarms

Set up alarms for critical metrics:

```bash
# ECS Service CPU Alarm
aws cloudwatch put-metric-alarm \
  --alarm-name whisperx-ecs-high-cpu \
  --alarm-description "Alert when ECS CPU is high" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ServiceName,Value=whisperx-demo-fastapi-service Name=ClusterName,Value=whisperx-demo-cluster
```

## Troubleshooting Deployment

### Issue: ECS Tasks Not Starting

**Solution**:

```bash
# Check task definition
aws ecs describe-task-definition --task-definition whisperx-demo-fastapi

# Check service events
aws ecs describe-services \
  --cluster whisperx-demo-cluster \
  --services whisperx-demo-fastapi-service | jq '.services[0].events'
```

### Issue: Cannot Pull Images from ECR

**Solution**:

```bash
# Verify ECR repository exists
aws ecr describe-repositories --region us-east-1

# Check ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

### Issue: Batch Jobs Stuck in RUNNABLE

**Solution**:

```bash
# Check compute environment status
aws batch describe-compute-environments | grep -A 10 whisperx-demo

# Check job queue
aws batch describe-job-queues | grep -A 10 whisperx-demo
```

### Issue: GitHub Actions Failing

**Solution**:

1. Verify `AWS_ROLE_ARN` secret is set
2. Check IAM role trust relationship includes your repository
3. Ensure OIDC provider is configured correctly

## Updating the Deployment

### Update Infrastructure

```bash
cd terraform
terraform plan
terraform apply
```

### Update FastAPI Service

Push changes to the `fastapi-app/` directory:

```bash
git add fastapi-app/
git commit -m "Update FastAPI service"
git push origin main
```

GitHub Actions will automatically deploy.

### Update Batch Worker

Push changes to the `batch-worker/` directory:

```bash
git add batch-worker/
git commit -m "Update batch worker"
git push origin main
```

GitHub Actions will automatically deploy.

## Destroying the Infrastructure

**Warning**: This will delete all resources including data in S3!

```bash
# Optional: Backup S3 data first
S3_BUCKET=$(cd terraform && terraform output -raw s3_bucket_name)
aws s3 sync s3://$S3_BUCKET/ ./s3-backup/

# Empty S3 bucket (required before deletion)
aws s3 rm s3://$S3_BUCKET/ --recursive

# Destroy infrastructure
cd terraform
terraform destroy
```

## Next Steps

1. Set up CloudWatch dashboards for monitoring
2. Configure custom domain and HTTPS
3. Implement API authentication (API Gateway, Cognito)
4. Add CloudWatch alarms for critical metrics
5. Set up automated backups for important transcriptions
6. Consider implementing a frontend application
7. Add rate limiting to prevent abuse
8. Implement cost alerts

## Support

If you encounter issues:

1. Check CloudWatch Logs
2. Review AWS Batch job logs
3. Verify IAM permissions
4. Open an issue on GitHub

---

**Deployment Complete!** 🎉

Your WhisperX Audio Transcription Service is now running on AWS.
