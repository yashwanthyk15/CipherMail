# Outputs for declared resources only
# RDS and ElastiCache outputs will be added when those resources are provisioned

output "vpc_id" {
  value = aws_vpc.main.id
}

output "ecr_smtp_gateway_url" {
  value = aws_ecr_repository.esg_smtp_gateway.repository_url
}

output "ecr_api_url" {
  value = aws_ecr_repository.esg_api.repository_url
}

output "ecr_dashboard_url" {
  value = aws_ecr_repository.esg_dashboard.repository_url
}
