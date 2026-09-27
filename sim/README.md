# P37 Neuro Simulation

The simulation package provides execution backends and launch integration for P37 Neuro.

## MuJoCo

MuJoCo is the fast local/debug backend. It implements the canonical P37 simulator contract and is covered by normal CI.

## Isaac Lab

Isaac Lab is the scale backend for GPU-parallel reinforcement learning and domain randomization.

P37 integrates at the task/experiment boundary and uses Isaac Lab's maintained CLI rather than copying its runner code:

```python
from p37_neuro_sim.isaac_lab import IsaacLabRun, IsaacLabRunner

run = IsaacLabRun(
    task="Isaac-Reach-Franka-v0",
    run_name="p37-e1-baseline",
    num_envs=4096,
    seed=42,
)

IsaacLabRunner().run(run)
```

The launcher is intentionally usable only when Isaac Lab is installed in the execution environment. Normal repository CI validates the launch specification without requiring an Omniverse/Isaac installation.

For P37-specific tasks, register the environment with Isaac Lab and keep reward, observation, action, event/domain-randomization, termination and curriculum configuration in the task package. The P37 ML collector consumes normalized vector observations through its own model contracts.

## Qualification protocol

For held-out morphology rules, Isaac/MuJoCo test levels, ablations and required evidence, see [../docs/testing.md](../docs/testing.md).
