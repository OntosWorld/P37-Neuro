# Cross-body MuJoCo reaching experiment — T2 baseline

## Purpose

This experiment runs **two different physical MuJoCo models** against the **same fixed Cartesian reach target**. It records canonical P37 episodes and exports them in the `p37-trace-v1` format accepted by the [recorded comparison viewer](../compare/index.html).

The robot arms are **procedural 2-joint reference models**, not real manufacturer hardware. They have different link lengths, mass distributions, and joint inertias.

## Controller and claims

The controller is **analytic inverse kinematics + joint-space PD + gravity compensation**. No P37 learned policy is loaded. Neither morphology is held out from training because there is **no training**.

Valid statement: "Two robot models execute the same reach target under a deterministic baseline controller in MuJoCo, with separately measured recorded outcomes."

Invalid statements: "P37 learned cross-embodiment transfer", "one frozen trained policy controls both arms", "real-world success", "better than another robot brain".

**Evidence:** T2 — MuJoCo physics only. Results remain unqualified for learned cross-body intelligence or real hardware.

## Frozen protocol

- Task: `reach-fixed-target-v1`
- Target: world position x = 0.65 m, z = 0.75 m (y = 0)
- Models: compact link lengths (0.45 m, 0.35 m), extended (0.65 m, 0.55 m)
- Simulation: MuJoCo, gravity = (0,0,-9.81) m/s², timestep = 0.005 s
- Duration: 3.0 s, samples every 10 simulation steps
- Success criterion: terminal end-effector Euclidean X/Z position error <= 0.045 m
- Seed: 7 by default (recorded in the artifact; no stochastic model perturbations)
- Recorded signals: both joint positions/velocities, commanded motor torques, tip X/Z, target X/Z, positional error, interventions/failures
- Provenance: source revision, XML SHA-256 per model, MuJoCo version, evidence level, controller identity, declared outcome

## Reproduce

Install the optional simulation package:

```bash
uv sync --project sim
uv run --project sim python scripts/mujoco_cross_body_demo.py --output artifacts/cross-body-mujoco.json
```

Upload `artifacts/cross-body-mujoco.json` to the existing offline [comparison viewer](../compare/index.html) to scrub and compare recorded joint states.

The separate [GitHub Actions workflow](../../../.github/workflows/cross-body-mujoco.yml) runs the same experiment and saves the JSON output as an Actions artifact. **Artifacts are evidence of execution, not a certified benchmark.** A failed run or unsuccessful reach must remain visible; do not manipulate thresholds after reviewing results.

## Publication rules

Only publish the JSON on the site after the workflow has successfully executed and its records have been inspected. The site must show the exact controller and evidence tier. Training, held-out-body, and physical-deployment claims require separate qualification under [the testing protocol](../../../docs/testing.md).

Do not modify or replace the existing GitHub Pages MuJoCo viewer. This runner is additive and operates behind the existing canonical episode and trace export contracts.
