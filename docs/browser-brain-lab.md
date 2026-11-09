# P37 Brain Lab — public browser evaluation

## Status (2026-11-09)

**Real robot model exploration available; P37 locomotion inference not yet demonstrated.**

The web entry point is `sim/web/index.html`. It links to MuJoCo Live real-physics models from Google DeepMind's MuJoCo Menagerie. It does not fake robot actions or synthesize P37 policy metrics. Browser users do not need an NVIDIA GPU.

Run locally:

```sh
python -m http.server 8080 --directory sim/web
# Open http://localhost:8080
```

These are external links, not locally hosted simulation engine bundles. When deploying the static page, ensure model URLs and license notices stay intact.

## Prerequisite: a genuine P37 G1 controller

The E1 roadmap currently marks cross-morphology locomotion checkpoints and physical validation as not complete. In particular, `ml/src/p37_neuro_ml/e1_smoke.py` produces a synthetic joint regression checkpoint; do **not** put that model behind a G1 controller button or describe it as a walking policy.

A real controlled G1 showcase requires:

1. Build a qualified MuJoCo G1 control environment using the actual 29-DOF Menagerie model, joint/sensor naming, actuator characteristics, units, timestep, joint/torque limits and fall termination.
2. Train or integrate an actual locomotion policy on the robot (P37 high-level inputs + compatible low-level motor policy). Keep the provenance of pretrained motor policies explicit; an external policy is not a trained P37 policy.
3. Define a canonical observation contract and inference adapter, including history/recurrent state, normalization, action scaling, missing-sensor behavior and safety enforcement.
4. Record at least 100 fixed held-out seeds with baseline and P37 runs. Freeze model identifiers, checkpoint SHA256, joint mapping, episode definitions, disturbance sequences and metrics before evaluation.
5. Export an ONNX policy only after parity testing against native Python for observation/action samples and closed-loop rollouts. A successful ONNX export is not a capability qualification.
6. For public browser execution, integrate `mjswan` (MuJoCo WASM + ONNX Runtime Web) with the verified model scene, explicit policy bundle and experiment manifest; no policy action should be replaced by a scripted animation.
7. Publish raw results and clear limitations. Physical simulation evidence must not be called physical hardware validation.

## Public benchmark targets

- Velocity-command tracking (m/s and rad/s) and fall rate over fixed horizons.
- External pushes defined by Newtons, impulse duration (s), direction and start time (s).
- Recovery fraction and recovery latency under identical seeded pushes.
- Action latency, safety rejections and actuator/joint bound violations.
- Generalization on held-out body configurations only when the *same checkpoint* actually supports those bodies.

## Release states

- `model_preview`: real physical model in MuJoCo; no P37 policy claims. **Current.**
- `controller_preview`: baseline/motor-policy demonstration with explicit provenance; no claims of P37 transfer.
- `p37_experimental`: actual P37 inference with checkpoint hash, reproducible trials and reported failures.
- `p37_qualified`: passed frozen evaluation gates for the exact asserted capability, with published evidence.
- `hardware_validated`: separately demonstrated on physical machines.

## Hosting

The entry point is a static HTML page and can deploy to Cloudflare Pages. For production, vendor/version-control the browser simulation runtime and assets rather than embedding an uncontrolled external website; host only redistributable robot models and approved weights. No secrets or proprietary checkpoints in client-delivered bundles.

## Technical references

- MuJoCo Live: https://mujoco.readthedocs.io/en/latest/studio/web_viewers.html
- MuJoCo Menagerie: https://github.com/google-deepmind/mujoco_menagerie
- mjswan browser engine: https://mjswan.readthedocs.io/en/latest/api/engine/
- P37 evaluation contract: `docs/testing.md`
- P37 qualification roadmap: `docs/roadmap.md`
