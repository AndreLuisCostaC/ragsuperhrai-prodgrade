variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be one of: dev, test, prod."
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "bedrock_aws_region" {
  description = "Bedrock AWS region"
  type        = string
  default     = "us-east-1"
}

variable "chroma_api_key" {
  description = "Chroma API KEY"
  type        = string
  default     = "ck-9mkd6VBfUd3GeXLeE7sN5urxLzYACxZkDYsLHAogTbmQ"
}

variable "chroma_collection_name" {
  description = "Chroma Collection Name"
  type        = string
  default     = "collection_bedrock"
}

variable "chroma_database" {
  description = "Chroma Database"
  type        = string
  default     = "vecdb_bedrock"
}

variable "chroma_tenant" {
  description = "Chroma Tenant"
  type        = string
  default     = "3f7e1866-298f-46b6-b369-b82e89c628c7"
}

variable "default_aws_region" {
  description = "Default AWS Region"
  type        = string
  default     = "ca-central-1"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
}

variable "api_throttle_burst_limit" {
  description = "API Gateway throttle burst limit"
  type        = number
  default     = 10
}

variable "api_throttle_rate_limit" {
  description = "API Gateway throttle rate limit"
  type        = number
  default     = 5
}

variable "use_custom_domain" {
  description = "Attach a custom domain to CloudFront"
  type        = bool
  default     = false
}

variable "root_domain" {
  description = "Apex domain name, e.g. mydomain.com"
  type        = string
  default     = ""
}