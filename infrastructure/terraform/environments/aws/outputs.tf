output "eks_cluster_name" {
  value = aws_eks_cluster.this.name
}

output "eks_cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "postgres_host" {
  description = "Feed to the Helm chart as postgres.host"
  value       = aws_db_instance.postgres.address
}

output "redis_url" {
  description = "Feed to the Helm chart as redis.url"
  value       = "rediss://:$${TF_VAR_redis_auth_token}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
}

output "ecr_repository_urls" {
  description = "Push each service image here (matches the chart's image.repository-<service> convention)"
  value       = { for name, repo in aws_ecr_repository.service : name => repo.repository_url }
}

output "helm_install_hint" {
  value = <<-EOT
    aws eks update-kubeconfig --name ${aws_eks_cluster.this.name} --region ${var.region}
    helm install convmem ./helm/conv-memory \
      --set postgres.host=${aws_db_instance.postgres.address} \
      --set redis.url=rediss://:$${TF_VAR_redis_auth_token}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0 \
      --set postgres.password=$TF_VAR_db_password
  EOT
}
