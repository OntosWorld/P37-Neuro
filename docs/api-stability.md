# API Stability and Deprecation Policy

## Purpose

P37 exposes stable product boundaries so enterprise integrations can evolve without depending on internal research implementation details.

## Public interfaces

The following are public integration surfaces:
- documented `p37` CLI commands;
- robot integration manifests under `p37_neuro.integration`;
- canonical embodiment/data contracts;
- qualification report schemas;
- signed release manifests;
- fleet rollout-plan schemas;
- documented C++ runtime headers under `runtime_cpp/include/p37`;
- documented ROS 2 bridge inputs/outputs when enabled.

Modules and symbols not documented as public should be treated as internal research implementation.

## Versioning

Published releases follow Semantic Versioning.

Before 1.0, breaking public-API changes may occur, but they must include:
1. a changelog entry;
2. a migration path or explicit replacement;
3. a schema-version change when serialized meaning changes;
4. tests covering rejection of unsupported serialized versions.

After 1.0, breaking public API/ABI changes require a major version.

## Deprecation

A public interface should normally be deprecated before removal. Deprecation documentation must identify the old interface, replacement, deprecation release and earliest removal release.

Safety-critical corrections may require immediate rejection of previously accepted inputs. Those changes must be documented as safety/security corrections rather than hidden behind compatibility behavior.

## C++ ABI

The documented C++ source API is public. A stable binary ABI is **not** guaranteed before 1.0. Enterprise deployments should consume runtime artifacts tied to an exact P37 release and toolchain.

## Model and data artifacts

Released checkpoints, manifests, qualification evidence and datasets are immutable. New results create new artifacts or reports rather than mutating historical evidence.
