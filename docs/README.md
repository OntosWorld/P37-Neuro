# P37 Neuro Documentation

This directory contains the technical and product documentation for P37 Neuro.

Documentation is organized by responsibility. Each document should have one clear purpose and link to the canonical source instead of duplicating status or implementation details.

## Interactive research lab

- [Cross-Embodiment Interactive Lab](interactive-lab/README.md) — a clearly labeled architecture explorer with task/embodiment controls, links to the current browser physics viewer, and reproducible-evidence requirements. [Open local web page](interactive-lab/index.html).

- [Steel WebGPU Physics Workcell](interactive-lab/steel/README.md) — standalone physics viewer with furnished tabletop scenes, movable objects, reference URDF arms and optional MimicGen offline data bridge; requires an independent build and has no trained P37 checkpoint attached.

- [P37-Neuro Real MimicGen Demo](interactive-lab/compare/index.html?sample=mimicgen) — two checksum-verified source robot recordings normalized and replayed through P37, with explicit provenance and no trained-policy claim.

## Start here

New users should begin with the repository [Quickstart](../QUICKSTART.md).


| Document | Audience | Purpose |
| --- | --- | --- |
| [Product and Technical Overview](overview.md) | engineers, researchers, partners | canonical definition of P37 Neuro, system scope, maturity and product boundary |
| [Architecture](architecture.md) | software/ML/robotics engineers | system layers and architectural boundaries |
| [Testing and Qualification](testing.md) | researchers, validation engineers, external testers | complete validation protocol from CI through physical robots |
| [Roadmap](roadmap.md) | engineering/research leads | implementation versus capability-validation status |

## Enterprise integration

| Document | Purpose |
| --- | --- |
| [Robot Integration Kit](integration-kit.md) | declarative robot adapters and integration boundary |
| [Enterprise Deployment](enterprise-deployment.md) | fleet targeting, canary rollout and rollback plans |
| [Observability](observability.md) | runtime metrics and monitoring boundary |
| [Data Governance](data-governance.md) | customer/site/region-aware data-use policy |
| [API Stability](api-stability.md) | public interfaces, versioning and deprecation |
| [Compatibility](../COMPATIBILITY.md) | supported software and deployment targets |
| [Quality Declaration](quality-declaration.md) | engineering, testing, security and support controls |
| Enterprise Readiness Diagnostics | `p37 doctor` checks environment, robot integration, qualification and rollout readiness |
| Artifact Schemas | `p37 schema export` emits versioned JSON Schemas for manifests, qualification, rollout and metrics |

## Engineering reference

| Document | Purpose |
| --- | --- |
| [Data Contract](data-contract.md) | canonical episode, provenance and learning-data rules |
| [Language Architecture](language-architecture.md) | Python/C++/TensorRT/cloud responsibility boundaries |
| [Safety](safety.md) | deterministic runtime safety principles and release constraints |
| [Research Principles](research-principles.md) | rules for holdouts, adaptation claims, negative results and scaling |
| [Documentation Standard](documentation-standard.md) | conventions for writing and maintaining P37 documentation |
| [Release Engineering](release.md) | software/runtime artifacts and publishing process |
| [Supply-Chain Security](supply-chain-security.md) | scanning, SBOM, attestations and artifact trust |

## Testing resources

- [Test plan template](testing/test-plan-template.md)
- [Test report template](testing/test-report-template.md)
- [Validation evidence](validation/)
- machine-readable validation records are stored under `validation/` at the repository root.

## Documentation ownership

Documentation changes are part of the engineering change, not an afterthought.

A code change should update documentation when it changes a public interface, architecture or system boundary, configuration, supported simulator/runtime behavior, qualification requirement, release/deployment process or capability/status claim.

Implementation state and capability state must remain separate in all documents.
