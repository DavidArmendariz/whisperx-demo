variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "whisperx-demo"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "fastapi_cpu" {
  description = "CPU units for FastAPI task"
  type        = number
  default     = 512
}

variable "fastapi_memory" {
  description = "Memory for FastAPI task"
  type        = number
  default     = 1024
}

variable "fastapi_desired_count" {
  description = "Desired count of FastAPI tasks"
  type        = number
  default     = 1
}

variable "batch_max_vcpus" {
  description = "Maximum vCPUs for Batch compute environment"
  type        = number
  default     = 16
}

variable "batch_gpu_max_vcpus" {
  description = "Maximum vCPUs for GPU Batch compute environment"
  type        = number
  default     = 8
}

variable "efs_performance_mode" {
  description = "EFS performance mode"
  type        = string
  default     = "generalPurpose"
}

variable "efs_throughput_mode" {
  description = "EFS throughput mode"
  type        = string
  default     = "bursting"
}
