locals {
  tags = {
    Project     = "P37-Neuro"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = var.artifact_bucket_name

  tags = local.tags
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "artifact_bucket_transport" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = data.aws_iam_policy_document.artifact_bucket_transport.json

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}

data "aws_iam_policy_document" "artifact_writer" {
  statement {
    sid    = "P37ArtifactReadWrite"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]

    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }

  statement {
    sid       = "P37ArtifactList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]
  }
}

resource "google_kms_key_ring" "releases" {
  name     = var.gcp_kms_key_ring_name
  location = var.gcp_kms_location
}

resource "google_kms_crypto_key" "release_signing" {
  name     = var.gcp_kms_crypto_key_name
  key_ring = google_kms_key_ring.releases.id
  purpose  = "ASYMMETRIC_SIGN"

  version_template {
    algorithm        = "EC_SIGN_ED25519"
    protection_level = var.gcp_kms_protection_level
  }

  labels = {
    project     = "p37-neuro"
    environment = var.environment
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "signer" {
  count = var.kms_signer_member == "" ? 0 : 1

  crypto_key_id = google_kms_crypto_key.release_signing.id
  role          = "roles/cloudkms.signerVerifier"
  member        = var.kms_signer_member
}

resource "google_kms_crypto_key_iam_member" "public_key_viewer" {
  count = var.kms_signer_member == "" ? 0 : 1

  crypto_key_id = google_kms_crypto_key.release_signing.id
  role          = "roles/cloudkms.publicKeyViewer"
  member        = var.kms_signer_member
}
