# P37 Brain Lab — verifiable simulation demos

The public demos gallery lives at `/P37-Neuro/demos/` and takes inspiration from the
clear interaction model of the Skild Steel demo, without borrowing its code,
design assets or performance claims. The P37 site uses **real MuJoCo
WebAssembly physics**, not recorded animation or a fake P37 controller.

## What visitors can actually run

- **Live robot simulations:** Unitree G1 and Go2, Franka Panda, Hello Robot
  Stretch and Crazyflie 2 are selected scene examples. The underlying lab
  still supports ten Menagerie robot models.
- **Two-body comparison:** Independent live MuJoCo scenes show two robot
  morphologies simultaneously. Metadata such as actuator and joint counts
  comes from compiled source models. This is a *simulation and embodiment
  inspection test*; different bodies here are **not** controlled by a
  shared P37 checkpoint.
- **Measured physical disturbances:** Native MuJoCo applies 90 N to G1
  and 40 N to Go2 for 0.15 seconds, with identical no-push control runs
  and deterministic repeated runs. The display shows measured base
  displacement, not recovery. Different applied forces preclude a fair
  performance comparison.
- **Native P37 PPO smoke test:** A genuine `P37Neuro` recurrent checkpoint
  produced actuator commands for G1. Two three-seed smoke episodes fell,
  and one reached a two-second evaluation horizon. This does not establish
  walking, recovery, transfer, or improved performance relative to any
  competitor.

**Verified shared-checkpoint inference smoke:** the unchanged experimental P37\ncheckpoint generated 60 joint-actuator commands for G1 (29 actuators) and Go2\n(12 actuators), over two 1.2-second native MuJoCo trials per robot. No Go2\nretraining occurred. See the original [GitHub Actions experiment](https://github.com/OntosRobotics/P37-Neuro/actions/runs/42896162520).\nThis is a model interface and actuation test, **not useful task transfer**.\n\nNo live gallery robot is labeled P37-controlled until a **trained,
qualified** policy is attached, tested and replicated on that body.

## Why this is useful for P37

The project has a body-aware architecture and shared robot integration
contracts. The gallery helps demonstrate that *distinct morphology models*
and their simulation assets can be loaded and inspected through the same
platform. It also makes a key research gap visible: the same trained policy
still has to demonstrate held-out task success on materially different
robot bodies.

There is **no evidence that P37 outperforms other robot brains** from the
current smoke results, and no such comparison is made here. To make a
cross-embodiment capability claim, publish a fixed checkpoint hash, mapping,
task/goal definition, separate held-out robot models, repeated seeds,
success criteria, and a comparable baseline. Include failures.

## Evidence plumbing

`sim/web/build_demo_evidence.py` creates `demos/evidence.json` from:
1. Real MuJoCo Menagerie scene files, with joints, actuators and body
   counts extracted through `mujoco.MjModel.from_xml_path`.
2. `sim/web/disturbance_test.py` output, which refuses missing/invalid
   measurement and verifies deterministic repeated trials.
3. `sim/web/p37-evidence.json`, which links native training and ONNX
   inference-parity artifacts.

The build **fails** if body models or measurements are missing, if the
same-checkpoint across bodies field is wrongly marked verified, or if the
P37 checkpoint is represented as qualified to walk.

Build locally:

```bash
git clone --depth 1 https://github.com/google-deepmind/mujoco_menagerie.git _menagerie
python -m pip install mjswan pytest playwright
python sim/web/disturbance_test.py --menagerie _menagerie --out _physics/force.json
python sim/web/build_demo_evidence.py \
  --menagerie _menagerie --forces _physics/force.json --output _demo_evidence.json
python sim/web/build_mjswan.py --menagerie _menagerie --base-path /P37-Neuro/simulator/
python sim/web/assemble_site.py --output _pages --demo-evidence _demo_evidence.json
python -m playwright install chromium
python sim/web/e2e_test.py --site _pages --url-prefix /P37-Neuro/ --screenshots _screenshots
```

The GitHub Pages and browser-build workflows run these gates automatically.
The interactive comparison starts only when selected and pauses the main
simulation, limiting simultaneous GPU contexts. Evidence and policy labels
are separate from the actual physics engine.

## Presentation rules

- Never label model-only physics as learned control.
- Never show scripted locomotion as a P37 action.
- Never interpret pushing a model as autonomous balance recovery.
- Use the exact model and experiment revision from the published build.
- Show negative results where they exist.
- Only say "cross-embodiment transfer" after the same checkpoint succeeds
  on at least two materially different bodies with held-out evaluation.
