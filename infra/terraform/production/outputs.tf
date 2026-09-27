output "artifact_bucket_name" {
  description = "S3 bucket used by S3ArtifactStore."
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifact_bucket_arn" {
  description = "Artifact bucket ARN."
  value       = aws_s3_bucket.artifacts.arn
}

output "artifact_writer_policy_json" {
  description = "Least-privilege policy to attach to the workload identity that publishes P37 artifacts."
  value       = data.aws_iam_policy_document.artifact_writer.json
}

output "release_kms_key_version_prefix" {
  description = "Crypto key resource. Configure P37 with a concrete cryptoKeyVersions/<n> child."
  value       = google_kms_crypto_key.release_signing.id
}

output "release_kms_key_ring" {
  value = google_kms_key_ring.releases.id
}
