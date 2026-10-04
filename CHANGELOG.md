# Changelog

All notable public changes to P37 Neuro are recorded here.

The project follows Semantic Versioning for published releases. Capability evidence is versioned separately from software features and is never inferred from a version number.

## Unreleased

### Added
- enterprise Robot Integration Kit with declarative robot manifests;\n- robot manifest schema v2 with explicit joint/controller mappings, sensor requirements, canonical observation mappings, end effectors, adapter capabilities and per-joint safety overrides;\n- executable robot I/O mapping plus a manifest-backed adapter for translating vendor/controller observations and commands at runtime;
- `p37 robot init` and `p37 robot validate`;
- executable staged qualification via `p37 qualify --level integration|simulation|hil|physical|fleet`;
- evidence-based release qualification reports via `p37 qualify --evidence`;
- stable vendor-neutral `RobotAdapter` contract and adapter health model;
- runtime observability contracts, readiness health evaluation and Prometheus/JSONL export;
- customer/site/region-aware data-governance policy;
- fleet-scoped rollout plans with canary batches, approvals, maintenance windows and rollback policy;
- `p37 deploy`, `p37 status` and `p37 rollback`;
- compatibility, API stability, enterprise deployment, quality and support documentation;
- CodeQL, dependency review, OpenSSF Scorecard, SBOM and build-provenance controls.

### Changed
- enterprise-facing maturity language now uses qualification-focused terminology;
- Apache-2.0 licensing is declared consistently across public package metadata.

## 0.4.0

Public platform baseline spanning P37-E0 through P37-E6, with synthetic validation evidence, C++20 runtime, ROS 2/TensorRT integration surfaces, signed release manifests and controlled deployment lifecycle primitives.
