# Software Supply-Chain Security

P37 uses separate controls for source, software builds and model artifacts.

## Source controls

- dependency updates are tracked with Dependabot;
- pull requests run dependency review;
- CodeQL scans Python and C++;
- OpenSSF Scorecard evaluates repository security posture.

## Release controls

Tagged builds generate:
- immutable GitHub Release assets;
- SHA-256 checksums;
- SPDX SBOM;
- GitHub artifact attestations;
- signed P37 model release manifests for model artifacts.

The release workflow uses GitHub OIDC for attestations and optional PyPI trusted publishing; long-lived package-publishing secrets are not required.

## Model artifacts

P37 model releases remain content-addressed and signed separately from the software package. A valid software release does not make a model qualified for physical deployment; release-manifest verification and qualification evidence remain independent gates.
