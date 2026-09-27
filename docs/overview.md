# P37 Neuro — Product and Technical Overview

## Status

**Program state:** platform-complete baseline, capability validation in progress.

P37 Neuro is Ontos World's general-purpose robot-brain program. It is designed as a shared learned intelligence layer that can operate across different robot embodiments, interpret task context, convert intent into physical behavior, retain useful context from prior attempts, and improve through simulation, imitation learning, reinforcement learning and real-world experience.

The program objective is:

> **A new robot body or a new task should not automatically require a new model.**

This document is the canonical high-level description of P37 Neuro. Architecture details, testing procedures and implementation status are maintained in the linked documents rather than duplicated here.

---

## 1. What P37 Neuro is

P37 Neuro is a **robot-brain system**, not a single model file and not a thin integration layer.

The product spans the learned policy, embodiment representation, memory, data contracts, simulation, real-time runtime, safety boundary, training/evaluation infrastructure and controlled release lifecycle required to turn learned intelligence into physical robot behavior.

At a high level, P37 answers four questions continuously:

1. **What is happening?** Interpret the robot's current physical state from sensors and machine state.
2. **What body am I controlling?** Represent the robot's joints, limits, actuators, sensors, kinematics and control interface.
3. **What am I trying to achieve?** Infer task intent from goals, demonstrations, language, environment state and previous attempts.
4. **What should this body do next?** Produce physically meaningful actions through a hierarchy of learned policies, subject to deterministic runtime safety.

---

## 2. Product boundary

P37 Neuro owns the shared intelligence and the infrastructure required to train, evaluate and deploy it.

### P37 owns

- canonical robot embodiment representation;
- observation, action and episode contracts;
- perception/state inputs to learned policy code;
- task and demonstration conditioning;
- high-level task policy;
- low-level embodiment-aware action policy;
- recurrent physical memory;
- behavior cloning and RL post-training;
- simulation integration;
- held-out evaluation and qualification gates;
- model export and accelerator runtime integration;
- deterministic actuator-facing safety enforcement;
- fleet data feedback and dataset lineage;
- model artifact integrity, signing, promotion and rollback.

### P37 does not replace

- certified robot emergency-stop systems;
- manufacturer motor-controller protections;
- mechanical safety engineering;
- robot-specific firmware;
- every sensor or actuator driver;
- a fleet-management product;
- a general cloud platform.

Those systems integrate with P37 at defined boundaries.

---

## 3. System architecture

```text
Task / goal / demonstration / language
                │
                ▼
       Context + Intent Encoder
                │
                ├─────────────────┐
                │                 │
Sensors ──► Perception + State    │
                │                 │
Robot spec ─► Embodiment Encoder  │
                │                 │
                ▼                 ▼
          High-Level Policy ◄── Physical Memory
                │
        task / motion intent
                │
                ▼
           Low-Level Policy
                │
        normalized robot action
                │
                ▼
      Deterministic C++ Runtime
                │
          safety + watchdogs
                │
                ▼
              Robot
                │
                ▼
        Episode / Outcome Data
                │
                ▼
      Training + Evaluation Loop
                │
                ▼
       Candidate → Production
```

The learned policy is not granted direct, unrestricted actuator authority. Commands pass through an independent deterministic runtime boundary.

For detailed layer boundaries, see [architecture.md](architecture.md).

---

## 4. Core technical properties

### Cross-embodiment intelligence

Robot morphology is represented explicitly as data. The learned system is designed to condition on body structure instead of encoding one fixed robot in the architecture.

Current embodiment ingestion includes URDF, MJCF, OpenUSD Physics and typed canonical joint/control metadata.

The long-term requirement is transfer across materially different bodies, not only small variations of one robot.

### Hierarchical control

P37 separates slower task-level reasoning from faster embodiment-specific control.

**High-level policy**

- task progress;
- subgoals;
- object interaction;
- locomotion/manipulation intent;
- recovery strategy.

**Low-level policy**

- joint action generation;
- locomotion;
- balance;
- contact;
- trajectory realization;
- morphology/dynamics adaptation.

### Demonstration conditioning

P37 can condition learned behavior on task context and demonstrations. The evaluation contract distinguishes demonstration-conditioned behavior from task-specific fine-tuning.

A valid one-shot evaluation requires a held-out task, exactly one demonstration and zero model-weight updates during evaluation.

### Physical memory

P37 maintains recurrent context across control windows so earlier observations, failed attempts and changing machine state can affect later action.

Memory claims must be evaluated with an ablation: preserved recurrent state versus reset recurrent state under the same task and seed.

### Self-improvement

P37 includes behavior cloning and on-policy PPO infrastructure. RL is used as a post-training mechanism for capabilities that benefit from reward-driven improvement, disturbance curricula and contact-rich interaction.

### Deterministic safety

Safety enforcement is outside the neural policy.

The actuator-facing runtime is implemented in C++20 and includes fail-closed behavior for invalid commands, stale observations, inference errors and I/O failures. Hardware-specific safety systems remain independent.

---

## 5. Data and learning system

P37 treats data as part of the product, not as an offline preprocessing concern.

The canonical learning record preserves embodiment identity, task identity, observations, actions, rewards/outcomes, timing, interventions, failure markers, source/provenance and dataset lineage.

Implemented ingestion paths include canonical P37 episodes, RLDS-like normalization and LeRobot v3 mapping.

The central rule is:

> **Robot-specific adapters may differ; the stored learning contract must not fragment by manufacturer.**

---

## 6. Simulation and physical validation

P37 uses different environments for different levels of evidence.

### MuJoCo

Used for deterministic control tests, repeatable physics, controller debugging, contact/perturbation regressions and low-cost research iteration.

### NVIDIA Isaac Lab / Isaac Sim

Used for GPU-parallel training, morphology diversity, locomotion, domain randomization, large-scale PPO and held-out simulation qualification.

### Physical robots

Used for sim-to-real validation, intervention-rate measurement, real contact/dynamics, real recovery and product-level capability evidence.

Simulation provides scale. Physical systems provide truth.

See [testing.md](testing.md) for the complete qualification protocol.

---

## 7. Program stages

P37 is developed as one continuous product program.

| Stage | Responsibility |
| --- | --- |
| **E0** | canonical robot/data/runtime foundations |
| **E1** | cross-morphology locomotion |
| **E2** | cross-embodiment manipulation |
| **E3** | demonstration-conditioned behavior |
| **E4** | long-horizon memory and recovery |
| **E5** | reinforcement learning and self-improvement |
| **E6** | continuous real-world learning and release lifecycle |

The repository currently contains an executable platform path across E0–E6.

That statement describes **software completeness**, not learned capability maturity.

See [roadmap.md](roadmap.md) for the current implementation and validation status.

---

## 8. Current evidence

The repository has executable synthetic evidence that:

- one variable-morphology policy can train across multiple joint counts and reduce held-out synthetic error;
- manipulation conditioning can transfer partially to held-out arm sizes;
- one-demo conditioning can affect held-out synthetic tasks without evaluation-time weight updates;
- recurrent memory can materially affect post-failure behavior;
- on-policy PPO can improve a policy under reward;
- the E6 feedback, signing, promotion and rollback lifecycle can execute end to end;
- the production Terraform configuration validates.

These results are classified as **synthetic smoke validation**.

They do not establish robust locomotion in realistic physics, real-object manipulation, natural human-video task learning, multi-minute physical autonomy, large-scale self-improvement, sim-to-real transfer, performance on multiple physical robot platforms or production fleet reliability.

See [validation/2026-09-27-cpu-smoke.md](validation/2026-09-27-cpu-smoke.md).

---

## 9. What “robot brain” means in P37

Within P37 documentation, **robot brain** means the shared intelligence system that connects:

```text
perception
+ robot embodiment
+ task context
+ physical memory
        ↓
learned decision/control policy
        ↓
safe physical action
        ↓
experience
        ↓
continued learning
```

The term does not imply that all capability targets have already been validated.

### Current accurate description

> **P37 Neuro is a platform-complete general-purpose robot-brain research system with initial synthetic validation and capability validation in progress.**

### After simulation qualification

Once held-out physics-simulation capability suites pass:

> **P37 Neuro is a cross-embodiment robot-brain system validated in held-out simulation.**

### After physical qualification

Only after the physical release gate passes:

> **P37 Neuro is a validated general-purpose robot brain across the documented robot/task scope.**

The scope must always accompany the claim.

---

## 10. Product qualification

A release is not considered a validated full robot brain merely because the software stack exists.

The current default release gate requires evidence for:

- at least 3 held-out embodiments;
- at least 2 physical embodiments;
- cross-embodiment success rate ≥ 0.70;
- one-shot success rate ≥ 0.60;
- long-horizon success rate ≥ 0.60;
- intervention rate ≤ 1 per hour;
- deterministic safety validation;
- fleet-feedback validation;
- production promotion and rollback validation;
- a benchmark report tied to the immutable release.

These values are implemented in the repository qualification contract and may be made stricter for a particular program.

---

## 11. Engineering principles

P37 follows these system-level principles:

1. **Safety is an independent boundary.**
2. **Embodiment is explicit data.**
3. **One canonical learning contract spans robot vendors.**
4. **Evaluation uses held-out bodies, tasks and environments.**
5. **Adaptation must be distinguished from retraining.**
6. **Failures are retained as useful data.**
7. **Simulation provides scale; hardware provides truth.**
8. **Experiments must be reproducible.**
9. **Heavy integrations remain optional at the core boundary.**
10. **Capability claims must be supported by evidence at the correct test level.**

---

## 12. Related documentation

- [Documentation index](README.md)
- [Architecture](architecture.md)
- [Language architecture](language-architecture.md)
- [Data contract](data-contract.md)
- [Safety](safety.md)
- [Testing and qualification](testing.md)
- [Research principles](research-principles.md)
- [Roadmap](roadmap.md)
- [Validation evidence](validation/)
