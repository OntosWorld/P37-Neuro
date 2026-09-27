# Testing and Qualification Guide

This document defines how to test **P37 Neuro** as a robot-brain system.

The goal is not only to prove that the code runs. A valid P37 test should answer a capability question under controlled conditions:

- can one checkpoint operate more than one embodiment?
- can it transfer to a body excluded from training?
- can a demonstration condition a new task without fine-tuning?
- can memory improve behavior after a failure?
- can reinforcement learning improve a policy under reward?
- does the deterministic runtime reject unsafe or stale commands?
- can a candidate move through the release lifecycle and be rolled back safely?

P37 uses a staged testing model. Start with cheap deterministic checks, then move to physics simulation, then hardware. **Simulation provides scale; physical systems provide truth.**

---

## 1. Test levels

| Level | Environment | Purpose | Can it qualify physical capability? |
| --- | --- | --- | --- |
| **T0 — Software** | CI / local CPU | types, unit tests, contracts, deterministic safety, C++ build | No |
| **T1 — Synthetic smoke** | CPU | prove learning/data/memory/RL paths execute end to end | No |
| **T2 — MuJoCo** | CPU/GPU | deterministic physics, control debugging, repeatable perturbations | No |
| **T3 — Isaac Lab** | NVIDIA GPU | large-scale physics, morphology variation, RL, domain randomization | Simulation evidence only |
| **T4 — HIL/runtime** | target computer + simulated or restricted I/O | TensorRT, ROS 2, timing, watchdogs, command safety | No |
| **T5 — Physical robot** | real hardware | sim-to-real, reliability, intervention rate, recovery | Yes |
| **T6 — Fleet/release** | deployed systems + production services | feedback, promotion, rollback, dataset lineage | Required for production qualification |

A test report must always state its level. Results from T1 or T2 must never be described as physical-robot capability.

---

## 2. Freeze the test before running it

Before training or evaluation, record:

1. commit SHA;
2. model configuration;
3. dataset/version IDs;
4. training embodiments;
5. held-out embodiments;
6. training tasks;
7. held-out tasks;
8. random seeds;
9. simulator and version;
10. test metric and pass/fail threshold;
11. checkpoint/artifact ID;
12. hardware used.

Do not decide the success threshold after seeing the result.

Use [test-plan-template.md](testing/test-plan-template.md) before a serious run and [test-report-template.md](testing/test-report-template.md) after it.

---

## 3. Data leakage rules

Cross-embodiment and one-shot claims are only meaningful if the evaluation set is genuinely held out.

### Embodiment holdout

For an unseen-body test:

- the held-out robot description must not be used for policy training;
- do not train on trajectories from that exact embodiment;
- do not tune against its evaluation result repeatedly;
- record morphology family, joint count and robot-description checksum;
- if a family is held out, do not include near-identical variants under a different name.

### Task holdout

For an unseen-task test:

- evaluation tasks must be excluded from the training task set;
- task demonstrations may be supplied only according to the declared protocol;
- test examples must not be moved into training after a failed run without creating a new benchmark version.

### One-shot demonstration rule

A valid P37 one-shot trial must satisfy all three:

- task was held out;
- exactly one demonstration was supplied;
- model weights received **zero gradient updates during evaluation**.

The repository enforces this rule in `p37_neuro.benchmarks.demonstration.OneShotTrial`.

---

## 4. T0 — software and runtime checks

Every contributor should start here.

From the repository root:

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run python scripts/check_repo.py

cmake -S runtime_cpp -B runtime_cpp/build
cmake --build runtime_cpp/build --parallel
ctest --test-dir runtime_cpp/build --output-on-failure
```

Or:

```bash
make check
```

A failure at T0 blocks higher-level testing.

T0 verifies contracts, serialization, replay, deterministic safety, release state machines, the C++ runtime, ML unit tests and simulator adapters. It does **not** show that the brain has learned a useful physical skill.

---

## 5. T1 — executable synthetic smoke suite

The repository includes CPU smoke experiments for E1–E6. These catch broken learning paths cheaply before spending GPU or robot time.

### E1 — cross-morphology learning

```bash
cd ml
uv sync --all-groups
uv run python -m p37_neuro_ml.e1_smoke \
  --epochs 40 \
  --output artifacts/e1-cpu-smoke
```

This trains one checkpoint on 2–5 joint synthetic bodies and evaluates on held-out 6–7 joint bodies.

Retain:

- training and held-out joint counts;
- initial/final train loss;
- initial/final held-out loss;
- checkpoint manifest.

### E2 — cross-embodiment manipulation

```bash
cd ml
uv run python -m p37_neuro_ml.e2_manipulation_smoke \
  --epochs 60 \
  --output artifacts/e2-manipulation-smoke
```

Retain:

- training arm DOFs;
- held-out arm DOFs;
- held-out task/target split;
- held-out MSE;
- success rate under a threshold fixed before the run.

### E3 — one-shot demonstration conditioning

```bash
cd ml
uv run python -m p37_neuro_ml.e3_one_shot_smoke \
  --epochs 80 \
  --output artifacts/e3-one-shot-smoke
```

Retain:

- held-out tasks;
- demonstration count = 1;
- evaluation gradient updates = 0;
- qualifying trial count;
- success rate and error.

### E4 — long-context recovery

```bash
cd ml
uv run python -m p37_neuro_ml.e4_recovery_smoke \
  --epochs 200 \
  --output artifacts/e4-recovery-smoke
```

The important test is the **memory ablation**:

1. preserve recurrent memory across the disturbance;
2. reset recurrent memory at the disturbance.

Report both errors. A recovery-memory claim requires a meaningful improvement when memory is preserved.

### E5 — PPO self-improvement

```bash
cd ml
uv run python -m p37_neuro_ml.e5_ppo_smoke \
  --updates 60 \
  --output artifacts/e5-ppo-smoke
```

Retain:

- evaluation reward before PPO;
- evaluation reward after PPO;
- number of vector environments;
- number of updates;
- identical deterministic evaluation protocol before and after.

### E6 — release/fleet lifecycle

From the repository root:

```bash
uv run python -m p37_neuro.deployment.exercise \
  --output artifacts/e6-lifecycle-smoke
```

The smoke exercise must demonstrate:

```text
robot feedback
  → quality scoring
  → review if required
  → dataset lineage
  → candidate artifact
  → signed release
  → staging
  → production
  → rollback
```

The first recorded T1 results are in [validation/2026-09-27-cpu-smoke.md](validation/2026-09-27-cpu-smoke.md). They are reference smoke results, not fixed capability targets.

---

## 6. T2 — MuJoCo testing

Use MuJoCo when you need physics but do not yet need thousands of GPU-parallel environments.

From `sim/`:

```bash
uv sync --all-groups
uv run pytest -q
```

MuJoCo is best for:

- controller debugging;
- observation/action mapping;
- deterministic replay;
- contact behavior;
- actuator-limit testing;
- recovery scenarios;
- payload/friction sweeps;
- regression tests that should be fast and repeatable.

### Recommended MuJoCo protocol

For each robot:

1. load the robot through the P37 embodiment contract;
2. verify joint names, order, units and limits;
3. reset with a fixed seed;
4. run a known baseline action sequence;
5. confirm replay gives the same result within declared tolerance;
6. execute the learned policy;
7. inject one perturbation at a time;
8. save the episode and failure markers.

Do not use a visually successful rollout as the metric. Record task success, error, interventions, safety rejections and recovery behavior.

---

## 7. T3 — Isaac Lab qualification

Isaac Lab is the main P37 environment for serious simulation-scale capability testing.

The repository includes a P37 Isaac Lab launcher, external task registration, a manager-based rough locomotion task, morphology/domain-randomization infrastructure and PPO tooling.

### E1 locomotion

Test one checkpoint across:

- multiple morphology families;
- joint/link variations;
- mass and center-of-mass changes;
- friction changes;
- payload changes;
- actuator degradation;
- external pushes;
- held-out bodies.

The headline metric must come from held-out embodiments, not training bodies.

### E2 manipulation

Recommended task family:

- reach;
- grasp;
- pick and place;
- push;
- drawer/door interaction;
- insertion/contact-rich manipulation.

Use materially different arms/end effectors. Hold at least one embodiment out of training.

### E3 demonstration conditioning

For every evaluation trial:

```text
held-out task
    +
one demonstration
    +
frozen P37 weights
    ↓
attempt task
```

Record success, progress and intervention count.

### E4 long horizon

Create multi-stage tasks where earlier events matter later. Inject failures such as failed grasps, dropped objects, moved targets, blocked paths or degraded actuators.

Always include a memory ablation:

```text
same checkpoint + same task + same seed

A: recurrent context preserved
B: recurrent context reset
```

### E5 self-improvement

Use a fixed pre-RL evaluation set:

```text
checkpoint before PPO
    ↓
fixed evaluation
    ↓
PPO / disturbance curriculum
    ↓
same fixed evaluation
```

Do not report training reward alone.

### Isaac run metadata

Every run should retain:

- task ID;
- P37 commit;
- Isaac Lab version;
- robot USD checksum/version;
- number of environments;
- seed;
- domain-randomization settings;
- checkpoint;
- training steps;
- held-out definitions;
- evaluation results.

---

## 8. Required ablations

A strong result should prove that the claimed mechanism matters.

| Claim | Required comparison |
| --- | --- |
| embodiment conditioning helps | full model vs embodiment information removed/neutralized |
| demonstration helps | with demonstration vs no demonstration |
| memory helps | recurrent state preserved vs reset |
| PPO improves policy | frozen pre-PPO checkpoint vs post-PPO checkpoint |
| domain randomization helps | fixed physics vs randomized training on the same held-out set |
| recovery works | nominal run vs injected failure with recovery metrics |

If the ablation does not support the mechanism, report the experiment as failed or inconclusive.

---

## 9. Runtime and safety testing

The learned model is not the safety system.

The C++ runtime must be tested independently from model quality.

Required checks include:

- unknown joint rejection;
- NaN/Inf rejection;
- joint-limit enforcement;
- stale observation rejection;
- clock-error rejection;
- inference failure;
- output-shape mismatch;
- I/O failure;
- watchdog/stop behavior;
- recurrent-state reset.

Run:

```bash
cmake -S runtime_cpp -B runtime_cpp/build
cmake --build runtime_cpp/build --parallel
ctest --test-dir runtime_cpp/build --output-on-failure
```

A policy that succeeds at a task but bypasses or breaks the deterministic safety boundary fails qualification.

---

## 10. TensorRT / target-compute test

TensorRT qualification must happen on the actual NVIDIA deployment target.

```bash
cmake -S runtime_cpp -B runtime_cpp/build-trt \
  -DP37_BUILD_TENSORRT=ON
cmake --build runtime_cpp/build-trt --parallel
```

Record:

- GPU/Jetson model;
- TensorRT version;
- CUDA version;
- exported checkpoint/artifact digest;
- batch size;
- padded joint count;
- context dimensions;
- warm-up count;
- p50/p95/p99 inference latency;
- peak GPU memory;
- failure rate;
- numerical comparison against the reference model.

Do not use desktop-GPU latency as evidence for a different deployment target.

---

## 11. T4 — ROS 2 / hardware-in-the-loop

Before enabling motors, test the complete I/O path:

```text
synthetic or replayed JointState
        ↓
ROS 2 bridge
        ↓
P37 runtime
        ↓
inference
        ↓
safety envelope
        ↓
command topic
        ↓
simulated/controller HIL sink
```

Test topic rate, timestamps, joint order, missing joints, stale state, dropped messages, controller disconnect, stop requests, model restart and runtime restart.

Motor power should remain disabled during the initial integration test.

---

## 12. T5 — physical robot qualification

Move to hardware only after T0–T4 pass.

Minimum progression:

1. robot powered with actuator commands disabled;
2. state-only ROS/runtime integration;
3. restricted low-speed single-joint commands;
4. constrained workspace task;
5. supervised task evaluation;
6. perturbation/recovery tests;
7. longer-duration evaluation.

Every physical test needs an independent emergency stop and manufacturer/controller-level limits.

For product qualification, the current default P37 release gate requires:

- at least **3 held-out embodiments** in evaluation;
- at least **2 physical embodiments**;
- cross-embodiment success rate ≥ **0.70**;
- one-shot success rate ≥ **0.60**;
- long-horizon success rate ≥ **0.60**;
- interventions ≤ **1 per hour**;
- deterministic safety passed;
- fleet feedback verified;
- promotion/rollback verified;
- benchmark report present.

These are the repository defaults in `QualificationThresholds`; a program may define stricter thresholds before a run.

---

## 13. T6 — fleet and release qualification

Production testing is more than policy accuracy.

Validate robot event upload, idempotency, offline spool/retry, data quality scoring, human review, dataset lineage, artifact checksum, release signature, staging promotion, production promotion, telemetry, rollback and feedback into the next dataset version.

The simulated E6 exercise proves the state machine. Production qualification requires real cloud identities, real storage/KMS and real fleet traffic.

---

## 14. What every test report must contain

### Identity

- test ID;
- date;
- tester;
- commit SHA;
- checkpoint/artifact ID;
- dataset version;
- simulator/hardware version.

### Train/evaluation split

- training embodiments;
- held-out embodiments;
- training tasks;
- held-out tasks;
- demonstrations available during evaluation.

### Configuration

- seed;
- model config;
- environment config;
- randomization config;
- training budget;
- evaluation episode count.

### Results

- primary metric;
- secondary metrics;
- failure count;
- intervention count;
- safety rejection count;
- latency where relevant;
- per-embodiment results, not only an average.

### Evidence

- machine-readable metrics;
- logs;
- checkpoint manifest;
- episode IDs;
- videos when useful;
- simulator configuration;
- failure examples.

### Classification

Every report must end with one of:

- **software validation**;
- **synthetic smoke validation**;
- **simulation capability evidence**;
- **hardware-in-the-loop evidence**;
- **physical capability evidence**;
- **production/fleet evidence**.

Do not collapse these into a single word such as "validated."

---

## 15. Failure reporting

Failed experiments are part of P37.

When a test fails:

1. keep the checkpoint and configuration;
2. retain failed episodes;
3. classify the failure;
4. do not modify the test set in place;
5. create a new experiment/run ID for the next attempt;
6. record whether the change was model, data, reward, simulator or runtime;
7. rerun the original evaluation set.

Useful failure categories include perception/state error, task misunderstanding, embodiment mismatch, motor/control error, contact failure, memory/progress failure, recovery failure, unsafe-command rejection and runtime/infrastructure failure.

---

## 16. Recommended external tester path

```text
1. Clone repository
       ↓
2. Run T0 quality/runtime checks
       ↓
3. Reproduce E1–E5 CPU smoke tests
       ↓
4. Run MuJoCo integration tests
       ↓
5. Choose one P37 capability question
       ↓
6. Write/freeze test plan
       ↓
7. Run Isaac Lab held-out evaluation
       ↓
8. Run required ablation
       ↓
9. Produce test report
       ↓
10. Only then move to ROS 2 / physical hardware
```

A tester does not need to test every P37 stage. They should choose a capability, preserve the held-out boundary and produce enough evidence that another engineer can reproduce the result.

---

## 17. Existing reference evidence

The repository's first executable validation record is:

- [CPU / simulated validation — 2026-09-27](validation/2026-09-27-cpu-smoke.md)
- machine-readable record: `validation/smoke/2026-09-27.json`

Use it to understand report structure, not as a target to beat or a substitute for your own held-out evaluation.
