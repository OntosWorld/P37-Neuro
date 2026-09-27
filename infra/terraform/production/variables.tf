variable "environment" {
  description = "Deployment environment name used in resource labels."
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region for the immutable P37 artifact bucket."
  type        = string
}

variable "artifact_bucket_name" {
  description = "Globally unique S3 bucket name used by the P37 artifact store."
  type        = string
}

variable "gcp_project_id" {
  description = "Google Cloud project containing the release signing key."
  type        = string
}

variable "gcp_region" {
  description = "Provider region. KMS location is configured separately."
  type        = string
  default     = "us-central1"
}

variable "gcp_kms_location" {
  description = "Cloud KMS location for release signing."
  type        = string
  default     = "global"
}

variable "gcp_kms_key_ring_name" {
  description = "Cloud KMS key ring name."
  type        = string
  default     = "p37-releases"
}

variable "gcp_kms_crypto_key_name" {
  description = "EC_SIGN_ED25519 release signing key name."
  type        = string
  default     = "p37-release-signing"
}

variable "gcp_kms_protection_level" {
  description = "Cloud KMS protection level. Use HSM only where EC_SIGN_ED25519 is supported in the selected location."
  type        = string
  default     = "SOFTWARE"

  validation {
    condition     = contains(["SOFTWARE", "HSM"], var.gcp_kms_protection_level)
    error_message = "gcp_kms_protection_level must be SOFTWARE or HSM."
  }
}

variable "kms_signer_member" {
  description = "Optional IAM member granted signer/verifier and public-key read access, e.g. serviceAccount:p37-release@project.iam.gserviceaccount.com."
  type        = string
  default     = ""
}
