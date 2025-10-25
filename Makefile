.PHONY: help init plan apply destroy deploy-fastapi deploy-worker test clean

# Variables
TERRAFORM_DIR = terraform
AWS_REGION ?= us-east-1
AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --query Account --output text)

# Colors for output
BLUE = \033[0;34m
GREEN = \033[0;32m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)WhisperX Demo - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# Terraform commands
init: ## Initialize Terraform
	@echo "$(BLUE)Initializing Terraform...$(NC)"
	cd $(TERRAFORM_DIR) && terraform init

plan: ## Run Terraform plan
	@echo "$(BLUE)Running Terraform plan...$(NC)"
	cd $(TERRAFORM_DIR) && terraform plan -var-file=terraform.tfvars

apply: ## Apply Terraform changes
	@echo "$(BLUE)Applying Terraform changes...$(NC)"
	cd $(TERRAFORM_DIR) && terraform apply -var-file=terraform.tfvars

destroy: ## Destroy all infrastructure
	@echo "$(RED)WARNING: This will destroy all infrastructure!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cd $(TERRAFORM_DIR) && terraform destroy -var-file=terraform.tfvars; \
	fi

outputs: ## Show Terraform outputs
	@cd $(TERRAFORM_DIR) && terraform output

# Docker commands
ecr-login: ## Login to ECR
	@echo "$(BLUE)Logging in to ECR...$(NC)"
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

build-fastapi: ## Build FastAPI Docker image
	@echo "$(BLUE)Building FastAPI image...$(NC)"
	cd fastapi-app && docker build -t whisperx-fastapi:latest .

build-worker: ## Build Batch Worker Docker image
	@echo "$(BLUE)Building Batch Worker image...$(NC)"
	cd batch-worker && docker build -t whisperx-worker:latest .

build-all: build-fastapi build-worker ## Build all Docker images

push-fastapi: ecr-login build-fastapi ## Build and push FastAPI image to ECR
	@echo "$(BLUE)Pushing FastAPI image to ECR...$(NC)"
	$(eval FASTAPI_ECR := $(shell cd $(TERRAFORM_DIR) && terraform output -raw ecr_fastapi_repository_url))
	docker tag whisperx-fastapi:latest $(FASTAPI_ECR):latest
	docker push $(FASTAPI_ECR):latest

push-worker: ecr-login build-worker ## Build and push Batch Worker image to ECR
	@echo "$(BLUE)Pushing Batch Worker image to ECR...$(NC)"
	$(eval WORKER_ECR := $(shell cd $(TERRAFORM_DIR) && terraform output -raw ecr_batch_worker_repository_url))
	docker tag whisperx-worker:latest $(WORKER_ECR):latest
	docker push $(WORKER_ECR):latest

push-all: push-fastapi push-worker ## Build and push all images to ECR

# Deployment commands
deploy-fastapi: push-fastapi ## Deploy FastAPI service
	@echo "$(BLUE)Deploying FastAPI service...$(NC)"
	aws ecs update-service \
		--cluster whisperx-demo-cluster \
		--service whisperx-demo-fastapi-service \
		--force-new-deployment \
		--region $(AWS_REGION)

deploy-worker: push-worker ## Deploy Batch Worker
	@echo "$(GREEN)Batch Worker image pushed. New jobs will use the updated image.$(NC)"

deploy-all: deploy-fastapi deploy-worker ## Deploy all services

# Testing commands
test-health: ## Test health endpoint
	$(eval ALB_DNS := $(shell cd $(TERRAFORM_DIR) && terraform output -raw alb_dns_name))
	@echo "$(BLUE)Testing health endpoint...$(NC)"
	curl -s http://$(ALB_DNS)/health | jq .

test-api: ## Run full API test suite (requires test audio file)
	$(eval ALB_DNS := $(shell cd $(TERRAFORM_DIR) && terraform output -raw alb_dns_name))
	@echo "$(BLUE)Running API test suite...$(NC)"
	@if [ -z "$(AUDIO_FILE)" ]; then \
		echo "$(RED)Error: AUDIO_FILE not specified$(NC)"; \
		echo "Usage: make test-api AUDIO_FILE=path/to/audio.mp3"; \
		exit 1; \
	fi
	./test_api.py --url http://$(ALB_DNS) --audio $(AUDIO_FILE)

# AWS commands
logs-fastapi: ## Tail FastAPI logs
	@echo "$(BLUE)Tailing FastAPI logs...$(NC)"
	aws logs tail /ecs/whisperx-demo/fastapi --follow --region $(AWS_REGION)

logs-batch: ## Tail Batch job logs
	@echo "$(BLUE)Tailing Batch logs...$(NC)"
	aws logs tail /aws/batch/whisperx-demo --follow --region $(AWS_REGION)

list-jobs: ## List recent Batch jobs
	@echo "$(BLUE)Listing Batch jobs...$(NC)"
	aws batch list-jobs --job-queue whisperx-demo-job-queue --region $(AWS_REGION) | jq '.jobSummaryList[] | {jobId, jobName, status}'

ecs-status: ## Show ECS service status
	@echo "$(BLUE)ECS Service Status:$(NC)"
	aws ecs describe-services \
		--cluster whisperx-demo-cluster \
		--services whisperx-demo-fastapi-service \
		--region $(AWS_REGION) | jq '.services[] | {serviceName, status, runningCount, desiredCount}'

s3-list: ## List S3 bucket contents
	$(eval BUCKET := $(shell cd $(TERRAFORM_DIR) && terraform output -raw s3_bucket_name))
	@echo "$(BLUE)S3 Bucket Contents:$(NC)"
	aws s3 ls s3://$(BUCKET)/ --recursive --human-readable

# Cleanup commands
clean: ## Clean local Docker images
	@echo "$(BLUE)Cleaning local Docker images...$(NC)"
	-docker rmi whisperx-fastapi:latest
	-docker rmi whisperx-worker:latest

clean-s3: ## Empty S3 bucket (required before destroy)
	$(eval BUCKET := $(shell cd $(TERRAFORM_DIR) && terraform output -raw s3_bucket_name))
	@echo "$(RED)WARNING: This will delete all files in S3!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		aws s3 rm s3://$(BUCKET)/ --recursive; \
	fi

# Development commands
fmt: ## Format Terraform code
	@echo "$(BLUE)Formatting Terraform code...$(NC)"
	cd $(TERRAFORM_DIR) && terraform fmt -recursive

validate: ## Validate Terraform configuration
	@echo "$(BLUE)Validating Terraform configuration...$(NC)"
	cd $(TERRAFORM_DIR) && terraform validate

# Information commands
info: ## Show deployment information
	@echo "$(BLUE)Deployment Information:$(NC)"
	@echo ""
	$(eval ALB_DNS := $(shell cd $(TERRAFORM_DIR) && terraform output -raw alb_dns_name 2>/dev/null || echo "Not deployed"))
	$(eval BUCKET := $(shell cd $(TERRAFORM_DIR) && terraform output -raw s3_bucket_name 2>/dev/null || echo "Not deployed"))
	@echo "  API URL:     http://$(ALB_DNS)"
	@echo "  S3 Bucket:   $(BUCKET)"
	@echo "  AWS Region:  $(AWS_REGION)"
	@echo ""

check-prereqs: ## Check prerequisites
	@echo "$(BLUE)Checking prerequisites...$(NC)"
	@command -v terraform >/dev/null 2>&1 || { echo "$(RED)terraform is not installed$(NC)"; exit 1; }
	@command -v aws >/dev/null 2>&1 || { echo "$(RED)aws CLI is not installed$(NC)"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)docker is not installed$(NC)"; exit 1; }
	@command -v jq >/dev/null 2>&1 || { echo "$(RED)jq is not installed$(NC)"; exit 1; }
	@echo "$(GREEN)All prerequisites satisfied!$(NC)"
