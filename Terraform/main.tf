terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Use S3 backend for state management (recommended for team)
  # Uncomment when ready:
  # backend "s3" {
  #   bucket         = "my-terraform-state"
  #   key            = "esg/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "email-security-gateway"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC (Simplified for portfolio, assuming default VPC or custom module)
# module "vpc" {
#   source = "./modules/vpc"
#   ...
# }

# ECR Repository
resource "aws_ecr_repository" "esg_smtp_gateway" {
  name                 = "esg-smtp-gateway"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "esg_api" {
  name                 = "esg-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "esg_dashboard" {
  name                 = "esg-dashboard"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "esg_ai_worker" {
  name                 = "esg-ai-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "esg_reputation_worker" {
  name                 = "esg-reputation-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# IAM Role for EC2 (ECR access, CloudWatch)
resource "aws_iam_role" "ec2_role" {
  name = "email-gateway-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecr_policy" {
  name = "ecr-pull-policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "email-gateway-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "esg_logs" {
  name              = "/ecs/email-security-gateway"
  retention_in_days = var.environment == "production" ? 30 : 7

  tags = {
    Name = "email-security-gateway-logs"
  }
}
