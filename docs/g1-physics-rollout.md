# P37 G1 native-physics rollout

This is an **actual MuJoCo physics harness**, not a trained P37 walking demonstration. It executes joint commands, applies an external push (newtons), and records real simulated positions, velocities, fall outcomes, and actuator clamps.

## Run

From the repository root:

```sh
git clone https://github.com/google-deepmind/mujoco_menagerie.git /tmp/mujoco_menagerie
cd sim
uv sync --all-groups
uv run python -m p37_neuro_sim.g1_rollout \
  --model /tmp/mujoco_menagerie/unitree_g1/scene.xml \
  --output artifacts/g1-baseline/seed-1000 --seed 1000 --push-newtons 45
uv run pytest -q tests/test_g1_rollout.py
```

The default controller is **PD hold** (not a locomotion policy). Model keyframe `stand` is preferred, else the first keyframe, else model reset defaults. Falls are defined by base body height dropping 0.30 m. Force is applied from t=2.00 to t=2.15 seconds in a seed-determined horizontal direction. Control period is 20 ms, with the actual MuJoCo timestep taken from the model. Unsupported transmissions fail closed.

The outputs are `summary.json`, `timeseries.csv`, and `trajectory.json`. They are native physics measurements and are suitable for future real trajectory replay. This feature does not implement video, browser policy inference or an end-to-end G1 walking model.

## P37 checkpoint gate

A checkpoint trained only by `e1_smoke` cannot be called a G1 locomotion policy. To test an actual trained policy, implement a locally trusted `my_policy:act` Python entrypoint accepting `(model, data, trial)` and returning one finite MuJoCo actuator control per actuator, then pass `--policy my_policy:act`. **This interface does not perform P37 observation normalization, embodiment encoding or model loading automatically.** Those must be implemented and verified against the concrete checkpoint before any public demo.

Next: train/obtain a true G1 walking checkpoint; freeze observation/action mapping and recurrent state; compare 100 matched held-out seeds against the same baseline; quantify commanded velocity tracking, falls and recovery; export verified ONNX and bundle with MuJoCo WASM/mjswan. Do not publish synthetic scores as genuine P37 capability.

## Validation status

Python source has been syntax-checked locally. Full tests and G1 rollout require the `mujoco` package and locally available Menagerie assets, neither of which were available to execute in the assistant runtime. CI must run the physics test before merge.
