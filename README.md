# P37 Neuro

**P37 Neuro** is Ontos World's general-purpose robot intelligence program: a shared robot brain designed to learn across different embodiments, understand task context, convert intent into physical behavior, and improve from simulation and real-world experience.

The long-term goal is simple to state and hard to achieve:

> **A new robot body or a new task should not automatically require a new model.**

P37 Neuro is being built as a full physical-intelligence stack rather than a single vision-language model. It separates high-level task intelligence from fast motor control, represents robot bodies explicitly, keeps deterministic safety outside the learned policy, and treats every successful or failed episode as training data.

## What P37 Neuro is

P37 Neuro is a research and engineering system for building **cross-embodiment robot policies**. The same learned system should eventually be able to:

- operate different robot morphologies;
- reason over camera, proprioceptive and machine-state inputs;
- learn tasks from demonstrations and context;
- perform locomotion and manipulation;
- adapt behavior from previous attempts without retraining for every small change;
- recover from errors and changing physical conditions;
- improve through imitation learning, reinforcement learning and simulation;
- transfer learned behavior from simulation to real machines;
- run behind deterministic safety constraints on physical hardware.

P37 Neuro is not intended to be a thin ROS wrapper, a prompt layer around an LLM, or one task-specific control model. It is the program for the **shared learned intelligence that connects perception, task understanding, embodiment and action**.

## Core idea

A general robot brain has to solve four problems together:

1. **What is happening?** Understand the current physical state from sensors.
2. **What body am I controlling?** Understand joints, limits, actuators, sensors and kinematics.
3. **What am I trying to achieve?** Infer task intent from language, demonstrations, goals and previous attempts.
4. **What should this body do next?** Produce safe, physically meaningful actions through a hierarchy of policies.

P37 Neuro models these as explicit system boundaries instead of hiding them inside an opaque application layer.

## Architecture

```text
Task demonstration / language / goal
                  │
                  ▼
        Context + Intent Encoder
                  │
                  ├───────────────┐
                  │               │
Sensors ──► Perception + State    │
                  │               │
Robot spec ─► Embodiment Encoder  │
                  │               │
                  ▼               ▼
          High-Level Policy ◄── Long Context / Memory
                  │
        embodiment-neutral intent
                  │
                  ▼
          Low-Level Policy
                  │
        joint / actuator command
                  │
                  ▼
     Deterministic Safety Runtime
                  │
                  ▼
               Robot
                  │
                  ▼
        Episode + Outcome Store
                  │
                  ▼
    Training / Evaluation Flywheel
```

### 1. Perception and state

The perception layer normalizes observations from heterogeneous machines. Supported inputs are expected to grow over time, but the core contract includes:

- RGB / stereo / depth observations;
- joint position and velocity;
- base pose and IMU data;
- end-effector state;
- force / torque and tactile signals where available;
- platform health and runtime state.

The system must tolerate missing modalities. A robot without tactile sensors should not require a completely different intelligence stack.

### 2. Embodiment representation

Every robot is represented as structured machine data rather than as a hard-coded policy assumption.

The initial schema captures:

- links and joints;
- joint type and axis;
- position, velocity and effort limits;
- actuator/control mode;
- end effectors;
- sensor inventory;
- morphology metadata;
- action-space metadata.

The long-term representation will include tokenized kinematic graphs and learned embodiment embeddings so a policy can transfer concepts such as *reach*, *grasp*, *walk* or *move the end effector* across physically different machines.

### 3. High-level policy

The high-level policy operates at a slower semantic/control horizon. Its responsibility is to determine **what physical behavior should happen next**, including:

- task progress;
- subgoal selection;
- manipulation intent;
- navigation intent;
- object interaction;
- recovery planning;
- coordination between locomotion and manipulation.

It should output an embodiment-neutral or weakly embodiment-dependent command rather than raw torque.

### 4. Low-level policy

The low-level policy converts high-level intent into fast, body-specific motor behavior.

Its responsibilities include:

- locomotion;
- balance;
- whole-body control;
- contact handling;
- trajectory realization;
- joint command generation;
- compensation for payload and dynamics changes.

This layer is where broad morphology randomization, reinforcement learning and sim-to-real training become especially important.

### 5. Long-context physical memory

P37 Neuro is designed around the idea that a robot should be able to use **previous attempts as context**. A failed grasp, a changed payload or a blocked joint should be information, not simply discarded history.

Memory therefore spans more than a short control window. The research roadmap includes cross-trial context, recurrent attention and explicit task-progress representations.

### 6. Safety runtime

Learned intelligence never gets unrestricted actuator access.

The runtime safety boundary is deterministic and testable. It is responsible for enforcing constraints such as:

- joint position limits;
- velocity limits;
- effort / torque limits;
- command freshness;
- workspace bounds;
- watchdogs;
- emergency-stop integration;
- hardware health checks;
- human-proximity policies where applicable.

The current codebase begins with typed safety envelopes for joint commands. Hardware-specific safety layers will remain outside the neural policy.

## Data is part of the system

A general physical model is limited by the diversity and quality of its experience. P37 Neuro therefore treats the data engine as a first-class subsystem.

Planned data sources include:

- large-scale simulation trajectories;
- public robot datasets;
- Ontos teleoperation;
- human demonstration video;
- autonomous robot episodes;
- failures, interventions and recovery attempts.

All sources are normalized into a canonical episode model so data from different robots can be trained together.

### Canonical episode

```text
episode
├── identity + provenance
├── embodiment specification
├── task / goal / demonstration references
├── observation[t]
│   ├── sensor frames
│   ├── proprioception
│   └── machine state
├── action[t]
├── reward / outcome
├── intervention markers
├── failure markers
└── timing metadata
```

A core engineering rule for P37 Neuro is:

> **Robot-specific adapters may differ; the stored learning contract must not fragment by manufacturer.**

## Simulation strategy

P37 Neuro will use simulation for scale and physical hardware for truth.

The primary simulation target is **NVIDIA Isaac Lab / Isaac Sim**, with **MuJoCo** as a lightweight research and controller-validation environment. Simulation integrations are deliberately optional adapters rather than core dependencies.

The simulation program will cover:

- procedural robot-body generation;
- dynamics randomization;
- sensor randomization;
- object and scene variation;
- actuator degradation;
- payload changes;
- latency and observation noise;
- reinforcement learning;
- imitation learning;
- sim-to-real evaluation.

## Research milestones

### P37-E0 — Foundations

Build the shared contracts first:

- canonical robot-body schema;
- canonical episode schema;
- policy interfaces;
- deterministic safety envelope;
- simulation adapter interface;
- tests and CI.

### P37-E1 — Omni-body locomotion

Train a single low-level policy across broad simulated morphology distributions and evaluate it on held-out bodies and dynamics changes.

### P37-E2 — Cross-embodiment manipulation

Train common manipulation policies across arms, dual-arm systems and mobile manipulators with different kinematics and end effectors.

### P37-E3 — Demonstration-conditioned behavior

Condition the policy on task demonstrations so new tasks can be attempted without creating a task-specific model.

### P37-E4 — Long-horizon in-context learning

Extend memory and training to multi-stage tasks, retries, recovery and persistent task progress.

### P37-E5 — Reinforcement learning and self-improvement

Use reinforcement learning for capabilities where imitation data is insufficient, including dynamic balance, contact-rich behaviors and recovery.

### P37-E6 — Continuous real-world learning

Turn robot deployments into a controlled learning flywheel with logging, evaluation gates and model versioning.

## Repository structure

```text
P37-Neuro/
├── configs/            robot and experiment configuration
├── docs/               architecture, safety and research documentation
├── scripts/            development and validation utilities
├── src/p37_neuro/
│   ├── core/           shared typed contracts
│   ├── data/           episode and dataset contracts
│   ├── embodiment/     robot-body representation
│   ├── policy/         learned policy interfaces
│   ├── runtime/        deterministic runtime/safety boundaries
│   └── simulation/     simulator abstraction
└── tests/              unit and contract tests
```

The repository will grow by adding adapters and learned implementations behind these contracts rather than breaking the core interfaces for each robot.

## Engineering principles

1. **Safety is a system boundary.** Neural policies cannot bypass deterministic actuator constraints.
2. **Embodiment is data.** Robot morphology should be represented explicitly and learned over, not hidden in per-robot code.
3. **One canonical learning contract.** Manufacturer-specific integration happens at the edge.
4. **Simulation provides scale; hardware provides truth.**
5. **Failures are training data.** Recovery and adaptation require failed episodes to remain observable.
6. **Evaluation comes before demos.** Every capability needs held-out tasks, bodies and environments.
7. **Reproducibility is mandatory.** Experiments must record code, configuration, data and model versions.
8. **Heavy dependencies stay optional.** The framework core remains testable without requiring a simulator or ROS installation.
9. **No secret-bearing configuration in source control.**
10. **Changes follow Conventional Commits.**

## Development status

P37 Neuro is in active research and validation. The repository now contains the **software path from P37-E0 through P37-E6** rather than only the E0 contracts.

Implemented platform pieces include:

- URDF, MJCF and OpenUSD robot ingestion;
- canonical multi-robot episode/data contracts plus LeRobot v3 ingestion;
- a trainable variable-morphology recurrent robot-brain baseline;
- behavior cloning, PPO collection/training primitives and recovery/disturbance curricula;
- MuJoCo execution plus a P37-specific Isaac Lab locomotion task and launcher;
- demonstration/task conditioning and one-shot leakage-controlled evaluation;
- content-addressed artifacts, signed releases, S3-compatible publication and KMS-backed signing;
- a fail-closed C++20 actuator runtime, optional ROS 2 bridge and optional TensorRT recurrent inference backend.

What is **not** complete is the capability evidence: large-scale training runs, held-out embodiment results, target-GPU TensorRT profiling, multi-robot physical validation, long-duration task recovery, and live production fleet rollout.

See [docs/roadmap.md](docs/roadmap.md) for the exact platform-versus-capability status and [docs/validation/2026-09-27-cpu-smoke.md](docs/validation/2026-09-27-cpu-smoke.md) for the first executable smoke results.

## Testing and qualification

P37 is tested in stages: software checks → synthetic smoke tests → MuJoCo → Isaac Lab → hardware-in-the-loop → physical robots → fleet/release validation.

External testers should start with [docs/testing.md](docs/testing.md). It defines held-out rules, commands, simulation strategy, required ablations, evidence requirements and release qualification criteria. Reusable templates are in [docs/testing/](docs/testing/).

## Local development

P37 Neuro uses Python 3.12 as the primary development target.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

Run all local quality checks:

```bash
make check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

## Security and physical safety

P37 Neuro controls physical systems. A defect can have consequences beyond software failure.

Do not deploy research policies directly onto unrestricted actuators. Hardware integrations must provide independent emergency stops, controller-level limits, watchdogs and tested failure states.

Security or safety-sensitive issues should follow [SECURITY.md](SECURITY.md).

## License

No public software license has been granted yet. Unless and until a license file is added, all rights are reserved by Ontos World.


## End-to-end product implementation

P37 Neuro is one continuous program from **P37-E0 through P37-E6**. The repository now contains executable platform boundaries for every stage, while learned capabilities are promoted only after training and evaluation gates pass.

| Stage | Product responsibility | Platform status |
| --- | --- | --- |
| **E0** | robot/config ingestion, canonical episodes, replay, artifact registry | platform complete |
| **E1** | morphology generation, Isaac locomotion task, locomotion training/evaluation | platform complete baseline |
| **E2** | cross-embodiment manipulation, teleoperation/data normalization | platform complete baseline |
| **E3** | demonstration/video-conditioned task context and one-shot qualification | platform complete baseline |
| **E4** | long-context memory, progress and recovery curricula | platform complete baseline |
| **E5** | PPO post-training, disturbance curriculum and promotion gates | platform complete baseline |
| **E6** | fleet data, signed releases, remote artifacts, KMS, promotion/rollback | platform complete baseline |
| **Runtime** | fail-closed C++ runtime, ROS 2 and optional TensorRT | implemented; hardware qualification pending |

"Implemented baseline" means the executable product contract exists and is tested. It does **not** mean a frontier-quality checkpoint has already been trained. Training, simulation-scale evaluation and physical validation remain measurable release work.

### Language boundaries

- **Python:** model/data/research plane from E0–E6.
- **C++20:** deterministic real-time runtime and hardware/inference boundary.
- **CUDA/TensorRT:** introduced behind the C++ runtime only when profiling justifies accelerator-specific optimization.

See [docs/language-architecture.md](docs/language-architecture.md) and [docs/roadmap.md](docs/roadmap.md).
