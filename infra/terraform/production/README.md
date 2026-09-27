# P37 Production Infrastructure

This Terraform root provisions the production resources already supported by the P37 release code:

- a private, versioned, TLS-only S3 artifact bucket;
- a least-privilege S3 writer policy document for the deployment workload;
- a Google Cloud KMS asymmetric signing key using `EC_SIGN_ED25519`;
- optional KMS IAM grants for the production release signer.

It does **not** create long-lived access keys or store credentials in Terraform.

## Why two providers?

The current product code supports an S3/S3-compatible artifact backend and Google Cloud KMS release signing. The two resources are independent and can be deployed together or split later behind the same software interfaces.

## Validate locally

```bash
cd infra/terraform/production
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

## Plan

Copy the example variables file and fill in real account/project values:

```bash
cp terraform.tfvars.example terraform.tfvars
terraform plan
```

Use normal short-lived provider authentication:

- AWS: workload identity / IAM role / SSO environment supported by the AWS provider.
- Google Cloud: Application Default Credentials or workload identity.

Do not put credentials, private keys or tokens in `terraform.tfvars`.

## Apply policy

Production apply should happen from a protected CI environment or an operator workstation with reviewed credentials. Before applying:

1. choose the real AWS account and GCP project;
2. confirm regions and data-residency requirements;
3. replace the placeholder bucket name;
4. use a dedicated service account/workload identity for `kms_signer_member`;
5. review the generated S3 writer policy before attaching it;
6. confirm whether KMS `SOFTWARE` or `HSM` is required and supported for the chosen key/location;
7. record the resulting concrete KMS key version in deployment configuration.

The KMS crypto key uses Terraform `prevent_destroy` because accidental deletion of a release-signing root would break release verification.
