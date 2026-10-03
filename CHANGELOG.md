# Changelog

All notable public changes to P37 Neuro are recorded here.

The project follows Semantic Versioning for published releases. Capability evidence is versioned separately from software features and is never inferred from a version number.

## Unreleased

### Added
- enterprise Robot Integration Kit with declarative robot manifests;
- `p37 robot init` and `p37 robot validate`;
- executable release qualification reports via `p37 qualify`;
- runtime observability contracts and Prometheus/JSONL export;
- customer/site/region-aware data-governance policy;
- fleet-scoped rollout plans with canary batches and rollback generation;
- `p37 deploy`, `p37 status` and `p37 rollback`;
- compatibility, API stability, enterprise deployment and support documentation.

### Changed
- enterprise-facing maturity language now uses qualification-focused terminology;
- Apache-2.0 licensing is declared consistently across public package metadata.

## 0.4.0

Public platform baseline spanning P37-E0 through P37-E6, with synthetic validation evidence, C++20 runtime, ROS 2/TensorRT integration surfaces, signed release manifests and controlled deployment lifecycle primitives.
