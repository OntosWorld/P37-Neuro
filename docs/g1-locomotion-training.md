# G1 locomotion training — experimental MuJoCo PPO baseline

The G1 training environment is a real MuJoCo simulation wrapped as a Gymnasium environment. It uses joint position residual actions and a PD torque controller, commanded forward velocity, torso orientation, and proprioceptive feedback. It is **not yet a trained P37-Neuro shared checkpoint**. Stable-Baselines3 is a baseline optimizer; producing a working PPO controller will establish a locomotion starting point but does not validate general-purpose intelligence or cross-embodiment transfer.

## Requirements

Python 3.12; MuJoCo; gymnasium; stable-baselines3; PyTorch; the actual G1 MJCF and referenced assets from MuJoCo Menagerie; and CPU or GPU compute. For meaningful locomotion, train much longer than a smoke test and tune the reward, reset distribution and contacts; no walking success is guaranteed.

```sh
git clone https://github.com/google-deepmind/mujoco_menagerie.git /tmp/mujoco_menagerie
cd sim
uv sync --extra train --group dev
uv run pytest -q tests/test_g1_locomotion_env.py tests/test_g1_rollout.py
uv run python -m p37_neuro_sim.g1_train \
  --model /tmp/mujoco_menagerie/unitree_g1/scene.xml \
  --output artifacts/g1-ppo --timesteps 100000 --seed 37
uv run python -m p37_neuro_sim.g1_train \
  --model /tmp/mujoco_menagerie/unitree_g1/scene.xml \
  --output artifacts/g1-ppo-eval \
  --evaluate artifacts/g1-ppo/g1_ppo.zip
```

The evaluator runs fixed held-out seeds 1000–1099 and writes trial-level fall, duration, and final forward speed measurements. These metrics are insufficient for full qualification until controller evaluation is expanded to repeated velocity commands, tracking error, measured disturbance recovery and independent randomized initial conditions.

## Engineering limitations

- The actuator interface currently supports only directly joint-driven torque motors; incompatible G1 model versions should fail before training.
- Stand keyframe or first model keyframe is used to set the joint reference. Validate initial pose visually before optimizing.
- The current environment reward is a minimal experiment intended to establish learning wiring. It is not a validated locomotion curriculum.
- CPU training of a humanoid may be prohibitively slow; use compute infrastructure for large-scale results.
- No P37 policy checkpoint is consumed by this trainer. P37 integration needs a learned hierarchical policy training adapter, complete observation normalization, action and safety mapping, and checkpoint provenance.
- Passing CI smoke tests confirms basic physics execution only, never that the G1 walks.

## Required next step

Confirm GitHub Actions smoke is green, verify real Menagerie G1 loads, then run a tiny training experiment. Inspect learning curves and actual physics rollouts before scaling training. After that train P37 on qualified locomotion data or connect P37's recurrent policy to the environment and evaluate against this baseline with paired held-out conditions.

## P37-native recurrent PPO experiment

P37 now also has a G1 MuJoCo bridge backed by the actual `P37Neuro` recurrent model, `OnPolicyCollector`, and `PPOTrainer`. This is separate from the Stable-Baselines3 benchmark. **No successful G1 walking checkpoint is claimed yet.**

```sh
cd sim
uv sync --extra train --extra learn --group dev
uv run python -m p37_neuro_sim.g1_p37_train \
  --model /tmp/mujoco_menagerie/unitree_g1/scene.xml \
  --output artifacts/g1-p37 --updates 1000 --seed 37

uv run python -m p37_neuro_sim.g1_p37_train \
  --model /tmp/mujoco_menagerie/unitree_g1/scene.xml \
  --output artifacts/g1-p37-evaluation \
  --evaluate artifacts/g1-p37/checkpoint
```

The training command produces P37's integrity-checked `checkpoint/model.pt` and `checkpoint/manifest.json`, plus `history.json`. Evaluation writes `heldout.json` for seeds 1000–1099.

This bridge currently uses a single MuJoCo environment, unnormalized joint residual/velocity features and a small global context vector. It is a genuine P37 neural PPO update pathway, but is still an *experimental training baseline*, lacking the broader locomotion curriculum, meaningful held-out morphology tests, domain randomization, measured disturbance recovery and browser inference export. Do not use its mere training completion to claim that the G1 can walk, that P37 generalizes, or that the model is qualified.

**Next acceptance gate:** verify official G1 loading in Actions, train with sufficient compute, produce rollouts from saved checkpoint, evaluate frozen held-out seeds, and publish video + metrics only if genuinely observed. Subsequent work should add multi-body training and mjswan ONNX parity validation.
