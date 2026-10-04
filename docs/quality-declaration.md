# P37 Neuro Quality Declaration

This document summarizes the engineering controls that apply to the public P37 Neuro platform. It is a project quality declaration, not a safety certification.

## Version and public interfaces

- Published releases follow Semantic Versioning.
- Serialized robot, release, rollout and qualification artifacts use explicit schema versions.
- Public interfaces and deprecation rules are defined in [API Stability](api-stability.md).
- Notable changes are recorded in [CHANGELOG.md](../CHANGELOG.md).

## Change control

- Changes are reviewed through Git history and repository CI.
- Conventional Commits are required by project policy.
- Public behavior changes require corresponding documentation.
- Runtime and safety changes require tests and rollback consideration.

## Testing

The normal quality path includes:

- Ruff lint and formatting checks;
- strict mypy checks for the Python core;
- Python unit/contract tests;
- C++20 build and CTest;
- dedicated ML and MuJoCo CI;
- staged qualification from synthetic smoke through physical/fleet evidence.

See [Testing and Qualification](testing.md).

## Security

- Dependabot tracks GitHub Actions and Python dependencies.
- Pull requests run dependency review.
- CodeQL analyzes Python and C++.
- OpenSSF Scorecard evaluates repository security posture.
- Tagged releases generate SBOM/provenance artifacts.
- Model artifacts use separate content-addressing and signing controls.

See [Supply-Chain Security](supply-chain-security.md) and [SECURITY.md](../SECURITY.md).

## Platform support

Supported and qualification-required targets are declared in [COMPATIBILITY.md](../COMPATIBILITY.md). A software-supported target is not automatically a physically qualified robot.

## Safety

The learned policy cannot bypass the deterministic actuator-facing runtime boundary. Physical deployments also require independent controller/manufacturer safety systems and the staged qualification process.

See [Physical-System Safety](safety.md).

## Documentation

Canonical product, architecture, testing, status and evidence documents have defined ownership. Historical validation reports are immutable records and are not rewritten to match later results.

See [Documentation Standard](documentation-standard.md).
