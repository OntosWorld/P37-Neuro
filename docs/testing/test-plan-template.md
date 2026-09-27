# P37 Neuro Test Plan Template

Complete this **before** the experiment starts.

## Test identity

- Test ID:
- Owner:
- Date planned:
- P37 commit SHA:
- Test level: T0 / T1 / T2 / T3 / T4 / T5 / T6
- P37 stage: E0 / E1 / E2 / E3 / E4 / E5 / E6 / Runtime

## Question

What single capability question is this test trying to answer?

## Hypothesis

State the expected result before running the test.

## Model

- Base checkpoint:
- Model configuration:
- Initialization/pretraining:
- Trainable parameters:
- Frozen parameters:

## Training data

- Dataset/version:
- Training embodiments:
- Training tasks:
- Demonstrations:
- Episode count:
- Known limitations:

## Held-out evaluation

- Held-out embodiments:
- Held-out tasks:
- Why they are genuinely held out:
- Evaluation episode count:
- Evaluation demonstrations available:
- Gradient updates allowed during evaluation: yes / no

## Environment

- Simulator/hardware:
- Version:
- Robot description IDs/checksums:
- Physics settings:
- Randomization:
- Sensors:
- Control frequency:
- Seed(s):

## Perturbations

List payload, friction, force, actuator degradation, sensor noise, failures or other disturbances.

## Primary metric

- Metric:
- Pass threshold:
- Why this threshold was selected:

## Secondary metrics

- Success rate:
- Progress:
- Interventions:
- Recovery:
- Safety rejections:
- Latency:
- Other:

## Required ablation

What will be removed/reset/disabled to verify the claimed mechanism?

## Safety

- Deterministic safety enabled:
- E-stop path:
- Workspace/velocity/effort limits:
- Human supervision:
- Hardware restrictions:

## Evidence to retain

- [ ] config
- [ ] commit SHA
- [ ] dataset/version IDs
- [ ] checkpoint manifest
- [ ] metrics JSON
- [ ] episode logs
- [ ] failure logs
- [ ] video if useful
- [ ] simulator/hardware metadata
