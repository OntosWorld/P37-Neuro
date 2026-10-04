# P37 Neuro Compatibility

This document defines the supported software and deployment surface for the public P37 Neuro platform.

A listed platform is **supported by the software contract** when the relevant code path is maintained and tested. Hardware capability claims require the separate qualification process in `docs/testing.md`.

## Core platform

| Component | Supported baseline | Notes |
| --- | --- | --- |
| Python | 3.12, 3.13 | Python 3.12 is the primary CI target |
| Linux | Ubuntu 24.04 CI baseline | Other modern Linux distributions may work but are not the release baseline |
| C++ | C++20 | Required for the deterministic runtime |
| CMake | 3.20+ | Runtime build baseline |
| MuJoCo | 3.13+ in the simulation package | Local deterministic physics and integration work |
| NVIDIA Isaac Lab 3.x / Isaac Sim 6.x | integration target | Python 3.12; GPU qualification remains environment-specific |
| ROS 2 Jazzy | integration baseline | Ubuntu 24.04 is the primary ROS 2 integration target; controller mapping requires HIL qualification |
| TensorRT / CUDA | optional integration | Must be compiled and profiled on the deployment target |
| S3-compatible storage | optional cloud backend | Immutable model artifacts |
| Google Cloud KMS | optional signing backend | EC_SIGN_ED25519 release-signing path |

## Deployment targets

P37 separates **software support** from **hardware qualification**.

| Target class | Software path | Qualification state |
| --- | --- | --- |
| Linux x86_64 workstation | supported | normal CI/software validation |
| Linux ARM64 / Jetson | architecture supported | target-device runtime/TensorRT qualification required |
| ROS 2 robot controller | bridge available | controller-specific HIL qualification required |
| Physical robot | integration contract available | per-robot physical qualification required |

A deployment target is not physically validated merely because its operating system or architecture is supported.

## Compatibility guarantees

P37 uses Semantic Versioning for published releases.

Before 1.0, intentional breaking changes to public interfaces must:
- be documented in `CHANGELOG.md`;
- include a migration note;
- avoid silent schema reinterpretation;
- preserve immutable historical artifacts and validation reports.

Robot manifests, qualification reports, rollout plans, release manifests and canonical episode data use explicit schema versions. Readers must reject unsupported schema versions rather than guess.

See `docs/api-stability.md`.

## Version pinning for enterprise deployments

Enterprise deployments should pin the exact P37 release, robot manifest schema, ROS distribution, simulator version, CUDA/TensorRT stack and compiler toolchain used during qualification.

A newer compatible dependency is not automatically a qualified replacement. Dependency or driver changes that can affect timing, control, physics or inference must be re-evaluated at the appropriate qualification level.
