# Tabletop Arm Reference

This directory is a P37 Robot Integration Kit reference for a tabletop manipulator.

Validate the integration contract:

```bash
p37 robot validate examples/tabletop_arm/robot.yaml
```

The included URDF is intentionally small so the integration path is easy to inspect. Replace it with the real robot description and controller topics before simulation, HIL or physical qualification.

This example demonstrates software integration only. It is not evidence that the included morphology has been physically validated with a P37 checkpoint.

## MuJoCo preflight

From the `sim/` environment, run the MJCF variant:

```bash
uv run p37 simulate \
  --robot ../examples/tabletop_arm/robot-mujoco.yaml \
  --backend mujoco \
  --steps 20
```

This verifies simulator loading, embodiment mapping and the action/observation loop. It is not a learned-capability benchmark.

## Closed-loop reach benchmark

Run the deterministic inverse-kinematics baseline through the canonical action,
safety and episode contracts:

```bash
uv run p37 benchmark-reach \
  --robot ../examples/tabletop_arm/robot-mujoco.yaml \
  --seed 42 \
  --output ../artifacts/reach-baseline
```

The command writes checksummed episode evidence and benchmark metrics, including
Cartesian error, safety clamps and deterministic replay error. This establishes a
physics-backed baseline and harness; it is not evidence of a learned policy.

## Learned goal-conditioned reach

Install the simulation learning extra and run the full expert-data, training and
held-out evaluation pipeline:

```bash
cd sim
uv sync --extra learn
uv run p37-neuro-ml reach-sim \
  --robot ../examples/tabletop_arm/robot-mujoco.yaml \
  --output ../artifacts/learned-reach \
  --seed 317
```

Training and evaluation targets come from one deterministic draw and are split
before training. The output includes every expert demonstration, the integrity-
checked checkpoint, held-out learned-policy episodes, per-target comparisons and
aggregate qualification metrics. Dynamics randomization remains locked until the
nominal learned policy reaches the configured success threshold with zero safety
clamps.

Before moving to a held-out arm morphology, run the larger multi-seed gate:

```bash
uv run p37-neuro-ml reach-sim-suite \
  --robot ../examples/tabletop_arm/robot-mujoco.yaml \
  --output ../artifacts/learned-reach-suite \
  --seeds 317,401,503,607,719 \
  --validation-targets 32 \
  --candidates 3 \
  --eval-targets 100
```

The suite reports the aggregate 95% Wilson interval, best and worst training
seed, total safety clamps and per-run randomization status. A held-out morphology
is unlocked only when both the aggregate and every individual seed meet the
declared success threshold.

Each seed trains multiple independently initialized candidates. Candidate ranking
uses only the validation targets; the selected checkpoint is then frozen before
the held-out test targets are evaluated once.

Evaluate that frozen checkpoint on the separately declared held-out arm geometry:

```bash
uv run p37-neuro-ml reach-morphology-eval \
  --checkpoint ../artifacts/learned-reach-suite/seed-317/checkpoint \
  --robot ../examples/tabletop_arm/robot-heldout.yaml \
  --output ../artifacts/heldout-morphology \
  --eval-targets 100
```

The held-out arm changes the two planar link lengths from 0.22/0.18 m to
0.26/0.14 m while preserving the task and control contract. Its targets and
results must not be used for candidate selection or training.
