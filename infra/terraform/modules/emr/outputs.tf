output "cluster_id" {
  value = aws_emr_cluster.nextcart.id
}

output "master_public_dns" {
  value = aws_emr_cluster.nextcart.master_public_dns
}
