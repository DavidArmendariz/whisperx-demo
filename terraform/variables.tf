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
  default     = 2
}

variable "batch_instance_type" {
  description = "Instance type for Batch jobs"
  type        = string
  default     = "g4dn.xlarge"
}

variable "batch_max_vcpus" {
  description = "Maximum vCPUs for Batch compute environment"
  type        = number
  default     = 16
}
