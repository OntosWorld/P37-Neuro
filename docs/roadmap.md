# Research and Engineering Roadmap

P37 Neuro has two completion states for every stage:

- **platform complete** — the software, contracts and execution path exist and are tested;
- **capability validated** — trained checkpoints meet held-out simulation and/or physical hardware gates.

This distinction prevents infrastructure from being mistaken for learned intelligence.

## P37-E0 — Foundation

**Platform:** implemented.

- [x] package skeleton
- [x] embodiment schema
- [x] observation/action/episode schema
- [x] policy interfaces
- [x] deterministic safety envelope
- [x] simulator protocol
- [x] versioned config loader
- [x] URDF importer
- [x] MJCF importer
- [x] RLDS-like record normalizer
- [x] checksummed episode serialization
- [x] deterministic replay harness
- [x] artifact registry
- [ ] USD importer

## P37-E1 — Cross-morphology locomotion

**Platform:** implemented baseline contracts and benchmark tooling. **Capability:** training pending.

- [x] procedural morphology generator
- [x] domain-randomization registry
- [x] executable multi-embodiment behavior-cloning lifecycle
- [x] framework-neutral trainer contract
- [x] held-out-body locomotion metrics
- [x] Isaac Lab launch integration
- [ ] P37-specific Isaac Lab task package
- [ ] trained cross-morphology locomotion checkpoint
- [ ] long-context adaptation checkpoint
- [ ] physical locomotion validation

## P37-E2 — Cross-embodiment manipulation

**Platform:** implemented baseline contracts and dataset normalization. **Capability:** training pending.

- [x] embodiment-neutral Cartesian command
- [x] robot-specific action projector contract
- [x] teleoperation sample contract
- [x] RLDS-like dataset adapter
- [x] manipulation transfer benchmark
- [ ] public dataset production adapters
- [ ] trained multi-embodiment manipulation checkpoint
- [ ] physical transfer benchmark

## P37-E3 — Demonstration conditioning

**Platform:** learned baseline implemented. **Capability:** large-scale training pending.

- [x] demonstration-video reference contract
- [x] language/goal/demo context contract
- [x] deterministic frame-time sampling
- [x] temporal visual encoder baseline
- [x] demonstration-conditioned action model
- [x] deployment export surface preserves demonstration/task inputs
- [ ] one-shot unseen-task benchmark execution

## P37-E4 — Long horizon

**Platform:** learned baseline implemented. **Capability:** training pending.

- [x] cross-trial context window
- [x] task-progress representation
- [x] failure history
- [x] long-horizon evaluation record
- [x] recurrent learned policy core
- [x] recurrent memory reset across terminated vector environments
- [ ] recovery curriculum
- [ ] multi-minute physical benchmark

## P37-E5 — RL post-training

**Platform:** executable PPO collection/training primitives implemented. **Capability:** compute runs pending.

- [x] post-training run manifest
- [x] offline evaluation gate
- [x] safety/latency promotion thresholds
- [x] vectorized on-policy PPO rollout collector
- [x] Isaac Lab training launcher
- [ ] adversarial disturbance curriculum
- [ ] physical transfer gate execution

## P37-E6 — Continuous real-world learning

**Platform:** deployment-data and release lifecycle implemented. **Capability:** fleet integration pending.

- [x] append-only fleet event logger
- [x] dataset lineage record
- [x] artifact registry
- [x] candidate/staging/production lifecycle
- [x] rollback state machine
- [x] live robot episode uploader
- [x] automated quality scoring
- [x] human review queue
- [x] content-addressed production artifact store
- [x] Ed25519 signed release manifests
- [ ] remote production object-store backend
- [ ] fleet signing-key/KMS integration

## Real-time deployment plane

- [x] independent C++20 runtime library
- [x] actuator safety envelope in C++
- [x] inference-engine ABI
- [x] independent CMake/CTest build
- [ ] ROS 2 hardware bridge
- [ ] TensorRT engine implementation
- [ ] hardware-in-the-loop validation

## Product completion definition

P37 Neuro becomes a validated full robot brain only when one release has passed all of the following:

1. one shared checkpoint operates materially different held-out embodiments;
2. unseen task demonstrations can condition behavior without per-task gradient updates;
3. multi-stage tasks preserve progress and recover from selected failures;
4. deterministic runtime safety gates every actuator command;
5. real robot deployments feed versioned experience back into training;
6. a candidate can be promoted, observed and rolled back through the E6 release path;
7. held-out simulation and physical benchmarks are published with the checkpoint.
