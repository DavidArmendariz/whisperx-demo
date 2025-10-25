# Getting Started Checklist

Use this checklist to ensure a smooth deployment of the WhisperX Audio Transcription Service.

## Pre-Deployment Checklist

### AWS Account Setup

- [ ] AWS account with admin access
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured (`aws configure`)
- [ ] Verified AWS credentials work (`aws sts get-caller-identity`)

### Development Tools

- [ ] Terraform >= 1.6.0 installed (`terraform --version`)
- [ ] Docker installed (`docker --version`)
- [ ] Git installed (`git --version`)
- [ ] jq installed for JSON parsing (`jq --version`)
- [ ] Python 3.11+ installed (for testing)

### GitHub Repository

- [ ] GitHub repository created
- [ ] Repository cloned locally
- [ ] You have admin access to repository settings

### AWS Service Limits

- [ ] VPC limit allows new VPC
- [ ] ECS service limit allows new cluster
- [ ] ECR repository limit allows 2 new repos
- [ ] g4dn.xlarge instances available in target region
- [ ] Batch service limit allows compute environment

## Deployment Checklist

### 1. Terraform Backend (Optional but Recommended)

- [ ] Created S3 bucket for Terraform state
- [ ] Enabled versioning on state bucket
- [ ] Updated `terraform/main.tf` with backend config
- [ ] Bucket name is globally unique

### 2. Terraform Configuration

- [ ] Copied `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`
- [ ] Updated `github_org` in terraform.tfvars
- [ ] Updated `github_repo` in terraform.tfvars
- [ ] Reviewed and adjusted other variables (region, instance types, etc.)
- [ ] Saved terraform.tfvars

### 3. Initial Infrastructure Deployment

- [ ] Ran `cd terraform && terraform init`
- [ ] Ran `terraform plan` and reviewed changes
- [ ] Ran `terraform apply` successfully
- [ ] Saved outputs to a file (`terraform output > ../outputs.txt`)
- [ ] Noted the following outputs:
  - [ ] alb_dns_name: ********\_\_\_********
  - [ ] s3_bucket_name: ********\_\_\_********
  - [ ] github_oidc_role_arn: ********\_\_\_********
  - [ ] ecr_fastapi_repository_url: ********\_\_\_********
  - [ ] ecr_batch_worker_repository_url: ********\_\_\_********

### 4. Docker Images - Initial Push

- [ ] Logged into ECR (`make ecr-login` or manual login)
- [ ] Built FastAPI image (`make build-fastapi`)
- [ ] Pushed FastAPI image to ECR (`make push-fastapi`)
- [ ] Built Batch Worker image (`make build-worker`)
- [ ] Pushed Batch Worker image to ECR (`make push-worker`)
- [ ] Verified images in ECR console

### 5. ECS Service Deployment

- [ ] Forced new ECS deployment (`make deploy-fastapi`)
- [ ] Waited for ECS service to stabilize (2-5 minutes)
- [ ] Verified tasks are running in ECS console
- [ ] Checked task is in RUNNING state

### 6. GitHub Actions Setup

- [ ] Copied GitHub OIDC role ARN from Terraform outputs
- [ ] Added `AWS_ROLE_ARN` secret to GitHub repository:
  - Settings → Secrets and variables → Actions → New repository secret
- [ ] Verified secret is saved

### 7. Initial Testing

- [ ] Tested health endpoint: `make test-health`
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] ALB DNS resolves correctly
- [ ] No 5xx errors from ALB

### 8. Full Functionality Test

- [ ] Prepared a test audio file (MP3, WAV, etc.)
- [ ] Ran full test: `make test-api AUDIO_FILE=test.mp3`
- [ ] OR used curl to upload audio
- [ ] Received job ID and batch job ID
- [ ] Job status checked successfully
- [ ] Monitored job in AWS Batch console
- [ ] Job completed successfully
- [ ] Downloaded transcription from S3
- [ ] Verified transcription JSON format

## Post-Deployment Checklist

### Monitoring Setup

- [ ] Checked CloudWatch Logs for FastAPI (`make logs-fastapi`)
- [ ] Checked CloudWatch Logs for Batch (`make logs-batch`)
- [ ] Verified logs are being written
- [ ] Set up CloudWatch alarms (optional)

### Security Review

- [ ] Verified ECS tasks are in private subnets
- [ ] Confirmed S3 bucket has public access blocked
- [ ] Checked security group rules are minimal
- [ ] Reviewed IAM role permissions

### Cost Optimization

- [ ] Reviewed estimated monthly costs
- [ ] Considered reducing to 1 NAT Gateway
- [ ] Considered Spot instances for Batch
- [ ] Set up AWS Cost Alerts

### Documentation

- [ ] Documented ALB DNS name for team
- [ ] Documented S3 bucket name
- [ ] Created runbook for common operations
- [ ] Shared access instructions with team

### GitHub Actions

- [ ] Pushed a test change to `fastapi-app/`
- [ ] Verified GitHub Action ran successfully
- [ ] Checked ECS service was updated
- [ ] Pushed a test change to `batch-worker/`
- [ ] Verified new job definition was registered

## Ongoing Maintenance Checklist

### Weekly

- [ ] Check CloudWatch Logs for errors
- [ ] Review Batch job failure rate
- [ ] Monitor S3 storage usage
- [ ] Check AWS costs

### Monthly

- [ ] Review and update Python dependencies
- [ ] Check for Terraform provider updates
- [ ] Review security group rules
- [ ] Update WhisperX model if needed
- [ ] Review CloudWatch Logs retention

### Quarterly

- [ ] Test disaster recovery procedures
- [ ] Review and optimize costs
- [ ] Update documentation
- [ ] Security audit of IAM roles

## Troubleshooting Checklist

### API Not Responding

- [ ] Check ALB health checks are passing
- [ ] Verify ECS tasks are running
- [ ] Check security group allows traffic
- [ ] Review CloudWatch Logs for errors
- [ ] Verify NAT Gateway is working

### Batch Jobs Not Starting

- [ ] Check compute environment status
- [ ] Verify job queue is enabled
- [ ] Check instance limits in region
- [ ] Review job definition configuration
- [ ] Check IAM role permissions

### GitHub Actions Failing

- [ ] Verify AWS_ROLE_ARN secret is set
- [ ] Check IAM role trust relationship
- [ ] Verify OIDC provider is configured
- [ ] Check ECR repository exists
- [ ] Review GitHub Action logs

### High Costs

- [ ] Check for orphaned instances
- [ ] Verify Batch scales down to zero
- [ ] Review NAT Gateway usage
- [ ] Check S3 storage size
- [ ] Review CloudWatch Logs retention

## Rollback Checklist

### If Deployment Fails

- [ ] Check Terraform state is consistent
- [ ] Review error messages in detail
- [ ] Check AWS service quotas
- [ ] Verify AWS credentials are valid
- [ ] Consider destroying and redeploying

### To Roll Back Changes

- [ ] Revert Git commits
- [ ] Run `terraform plan` to preview
- [ ] Run `terraform apply` to revert
- [ ] Or use `make deploy-fastapi`/`make deploy-worker`

## Cleanup Checklist (Before Destroy)

### Data Backup

- [ ] Download important transcriptions from S3
- [ ] Export CloudWatch Logs if needed
- [ ] Save Terraform state file
- [ ] Document any custom configurations

### Resource Cleanup

- [ ] Empty S3 bucket (`make clean-s3`)
- [ ] Stop all running Batch jobs
- [ ] Terminate any manual EC2 instances
- [ ] Remove custom CloudWatch alarms

### Terraform Destroy

- [ ] Run `terraform destroy`
- [ ] Confirm all resources deleted
- [ ] Check AWS console for orphaned resources
- [ ] Delete Terraform state bucket if needed

---

## Quick Commands Reference

```bash
# Check prerequisites
make check-prereqs

# Deploy infrastructure
make init plan apply

# Build and push images
make push-all

# Deploy services
make deploy-all

# Test deployment
make test-health
make test-api AUDIO_FILE=test.mp3

# Monitor
make logs-fastapi
make logs-batch
make list-jobs

# Get info
make info
make outputs
```

## Support Resources

- **Documentation**: README.md, DEPLOYMENT.md, QUICK_REFERENCE.md
- **Commands**: Run `make help` for all available commands
- **AWS Console**: Check ECS, Batch, CloudWatch Logs
- **GitHub**: Review Actions tab for CI/CD status

---

✅ **Checklist Complete!** You're ready to deploy and operate your WhisperX Audio Transcription Service.
