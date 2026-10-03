# Research and Engineering Roadmap

P37 Neuro has two completion states for every stage:

- **platform complete** — the software, contracts and execution path exist and are tested;
- **capability validated** — trained checkpoints meet held-out simulation and/or physical hardware gates.

This distinction prevents infrastructure from being mistaken for learned intelligence.

## Current program state

The repository now contains the software path from E0 through E6. The current program focus is **capability qualification**: large-scale training, target-GPU validation, real robot transfer, fleet deployment and published benchmark evidence.

A checked platform item means the implementation exists in the repository and is covered by the applicable normal CI path. It does not mean that a learned checkpoint has passed the physical product gate.

## P37-E0 — Foundation

**Platform:** complete.

- [x] package skeleton
- [x] embodiment schema
- [x] observation/action/episode schema
- [x] policy interfaces
- [x] deterministic safety envelope
- [x] simulator protocol
- [x] versioned config loader
- [x] URDF importer
- [x] MJCF importer
- [x] OpenUSD Physics importer
- [x] RLDS-like record normalizer
- [x] checksummed episode serialization
- [x] deterministic replay harness
- [x] artifact registry

## P37-E1 — Cross-morphology locomotion

**Platform:** complete baseline. **Capability qualification:** in progress — large-scale training and physical validation.

- [x] procedural morphology generator
- [x] domain-randomization registry
- [x] executable multi-embodiment behavior-cloning lifecycle
- [x] framework-neutral trainer contract
- [x] held-out-body locomotion metrics
- [x] Isaac Lab launch integration
- [x] P37-specific Isaac Lab manager-based locomotion task
- [x] external-task registration through Isaac Lab's maintained trainer
- [x] synthetic CPU cross-morphology smoke: train 2–5 joints, hold out 6–7 joints
- [ ] trained cross-morphology locomotion checkpoint
- [ ] long-context adaptation checkpoint
- [ ] held-out morphology scale run
- [ ] physical locomotion validation

## P37-E2 — Cross-embodiment manipulation

**Platform:** complete baseline. **Capability qualification:** in progress — multi-embodiment training and physical transfer.

- [x] embodiment-neutral Cartesian command
- [x] robot-specific action projector contract
- [x] teleoperation sample contract
- [x] RLDS-like dataset adapter
- [x] LeRobot v3 production adapter with explicit field/joint mapping
- [x] manipulation transfer benchmark
- [x] synthetic CPU manipulation-transfer smoke across held-out 6/7-DOF arms
- [ ] trained multi-embodiment manipulation checkpoint
- [ ] physical transfer benchmark across materially different robots

## P37-E3 — Demonstration conditioning

**Platform:** complete baseline. **Capability qualification:** in progress — production-scale held-out execution.

- [x] demonstration-video reference contract
- [x] language/goal/demo context contract
- [x] deterministic frame-time sampling
- [x] temporal visual encoder baseline
- [x] demonstration-conditioned action model
- [x] deployment export surface preserves demonstration/task inputs
- [x] one-shot qualification harness with held-out-task and zero-gradient checks
- [x] synthetic one-shot smoke with one demonstration and zero evaluation updates
- [ ] one-shot unseen-task benchmark execution on a production-scale trained checkpoint

## P37-E4 — Long horizon

**Platform:** complete baseline. **Capability qualification:** in progress — long-duration training and physical validation.

- [x] cross-trial context window
- [x] task-progress representation
- [x] attempt and recovery history
- [x] long-horizon evaluation record
- [x] recurrent learned policy core
- [x] recurrent memory reset across terminated vector environments
- [x] progressive retry/recover/replan curriculum
- [x] synthetic chunked recovery-memory smoke with a held-out morphology
- [ ] trained long-horizon recovery checkpoint
- [ ] multi-minute physical benchmark

## P37-E5 — RL post-training

**Platform:** complete baseline. **Capability qualification:** in progress — large-scale compute and physical transfer.

- [x] post-training run manifest
- [x] offline evaluation gate
- [x] safety/latency promotion thresholds
- [x] vectorized on-policy PPO rollout collector
- [x] Isaac Lab training launcher
- [x] progressive randomized/adversarial disturbance curriculum
- [x] synthetic on-policy PPO self-improvement smoke
- [ ] large-scale PPO/self-improvement run
- [ ] physical transfer gate execution

## P37-E6 — Continuous real-world learning

**Platform:** complete baseline. **Capability qualification:** in progress — production fleet validation.

- [x] append-only fleet event logger
- [x] dataset lineage record
- [x] artifact registry
- [x] candidate/staging/production lifecycle
- [x] rollback state machine
- [x] live robot episode uploader
- [x] automated quality scoring
- [x] human review queue
- [x] content-addressed local artifact store
- [x] S3/S3-compatible content-addressed production artifact backend
- [x] Ed25519 signed release manifests
- [x] Google Cloud KMS EC_SIGN_ED25519 release signer with integrity verification
- [x] Terraform configuration validates S3/KMS/IAM production infrastructure
- [x] simulated fleet feedback → review → signed candidate → staging → production → rollback exercise
- [ ] production bucket/KMS provisioning and live IAM validation
- [ ] live physical-fleet feedback and rollback exercise

## Real-time deployment plane

**Platform:** implemented. **Hardware qualification:** in progress.

- [x] independent C++20 runtime library
- [x] actuator safety envelope in C++
- [x] inference-engine ABI
- [x] deterministic reject-on-error control loop
- [x] independent CMake/CTest build
- [x] optional ROS 2 joint-state / command / stop bridge
- [x] optional TensorRT recurrent inference engine matching the ML export tensor surface
- [ ] TensorRT/CUDA compile and latency profile on the target deployment GPU
- [ ] ros2_control/controller-specific integration for selected physical robots
- [ ] hardware-in-the-loop validation

## Enterprise productization

**Platform:** implemented baseline. **Deployment qualification:** environment-specific.

- [x] declarative Robot Integration Kit
- [x] `p37 robot init` / `p37 robot validate`
- [x] executable qualification reports
- [x] runtime observability contracts and C++ diagnostics counters
- [x] customer/site/region-aware data-governance policy
- [x] organization → site → fleet → robot rollout contracts
- [x] canary/batched rollout and deterministic rollback plans
- [x] compatibility and API/deprecation policy
- [x] native runtime install bundle and Python release artifacts
- [x] OCI distribution for the non-real-time CLI/control plane
- [x] SBOM and artifact-attestation release path
- [x] CodeQL, dependency review and OpenSSF Scorecard workflows
- [x] tabletop-arm, mobile-manipulator and quadruped reference integrations
- [ ] live enterprise fleet transport integration
- [ ] customer-specific SSO/RBAC integration
- [ ] target-site observability backend validation
- [ ] production retention/deletion backend integration

These unchecked items depend on the customer's deployment environment; they do not change the core robot-brain architecture.

## Release qualification gate

The repository includes a release qualification gate so software completion cannot be confused with robot-brain capability completion.

A P37 release is only considered a validated full robot brain when evidence shows all of the following:

1. one shared checkpoint operates materially different held-out embodiments;
2. unseen task demonstrations condition behavior without per-task gradient updates;
3. multi-stage tasks preserve progress and recover from selected disturbance and recovery scenarios;
4. deterministic runtime safety gates every actuator command;
5. real robot deployments feed versioned experience back into training;
6. a candidate can be promoted, observed and rolled back through the E6 release path;
7. target deployment inference meets measured latency and reliability requirements;
8. held-out simulation and physical benchmarks are published with the immutable release.

Until those evidence gates pass, P37 Neuro should be described as a **platform-complete robot-brain research system with capability validation in progress**, not as a validated general-purpose robot brain.
