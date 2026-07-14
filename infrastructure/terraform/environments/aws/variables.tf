variable "name" {
  description = "Name prefix for every resource"
  type        = string
  default     = "conv-memory"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.40.0.0/16"
}

variable "eks_version" {
  description = "EKS Kubernetes version"
  type        = string
  default     = "1.29"
}

variable "eks_instance_types" {
  description = "Node group instance types"
  type        = list(string)
  default     = ["m5.large"]
}

variable "eks_desired_nodes" {
  type    = number
  default = 3
}

variable "eks_min_nodes" {
  type    = number
  default = 2
}

variable "eks_max_nodes" {
  type    = number
  default = 10
}

variable "db_instance_class" {
  description = "RDS instance class (Postgres 16 supports pgvector via CREATE EXTENSION)"
  type        = string
  default     = "db.r6g.large"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 100
}

variable "db_password" {
  description = "Master password for RDS Postgres (feed via TF_VAR_db_password, never tfvars in git)"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "eks_endpoint_public_access" {
  description = "Expose the EKS control-plane endpoint publicly (private-only by default; use a bastion/VPN, or enable and restrict the CIDRs)"
  type        = bool
  default     = false
}

variable "eks_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach a public EKS endpoint (never leave 0.0.0.0/0 in production)"
  type        = list(string)
  default     = []
}

variable "redis_auth_token" {
  description = "ElastiCache AUTH token (feed via TF_VAR_redis_auth_token; required with in-transit encryption)"
  type        = string
  sensitive   = true
}
