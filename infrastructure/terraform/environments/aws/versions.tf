terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  # Recommended: S3 backend with state locking. Configure per team, e.g.:
  # backend "s3" {
  #   bucket         = "your-tf-state-bucket"
  #   key            = "conv-memory/aws.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "your-tf-locks"
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "terraform"
    }
  }
}
