# P37 Brain Lab: Real Robots in Browser Physics

This directory is the source for a **real MuJoCo browser simulation** of the official Unitree G1, Unitree Go2 and Franka Panda Menagerie scenes. It builds a self-contained `mjswan` static simulator and a P37-branded selection page. No NVIDIA GPU, Python runtime or backend is required for visitors.

**Evidence level: model-only physics.** At this stage, gravity, contacts, joints and mouse perturbations are real simulated dynamics. Robots can fall. No trained P37 locomotion, cross-embodiment, memory, recovery or manipulation policy is included, and none of those capabilities may be claimed from this build.

## Build locally

Python 3.12+, access to the public MuJoCo Menagerie repository, and internet access during the one-time build are needed.

```bash
git clone --depth 1 https://github.com/google-deepmind/mujoco_menagerie.git _menagerie
python -m pip install mjswan pytest
python sim/web/build_mjswan.py --menagerie _menagerie --base-path /simulator/
python sim/web/assemble_site.py --output _site
python -m http.server 8080 --directory _site
# Open http://localhost:8080
```

The builder produces `sim/web/dist/` from a bundled MuJoCo WebAssembly physics engine and real Menagerie MJCF model assets. The assembler creates `_site/index.html` (P37 portal) and `_site/simulator/` (mjswan viewer with all models). Run over HTTP or HTTPS: do **not** open the generated index as a `file://` URL.

Use the simulator's built-in controls for camera orbit/zoom, playback/reset, and physical pointer interaction. The portal switches between the three real robot models and reloads to reset a simulation. On a build without bundled assets, it links to the equivalent official MuJoCo Live viewer.

## Preview and publishing

The `Browser Brain Lab` GitHub Actions workflow builds all three models, checks the generated manifest, includes upstream model provenance in `build-info.json`, and uploads the entire site as a downloadable Actions artifact. You can serve that extracted artifact locally with `python -m http.server` from the extracted directory.

On a `main` push, the workflow also attempts GitHub Pages deployment to the repository project path. **GitHub Pages must be enabled and configured for GitHub Actions**, and private-repository eligibility depends on account and organization settings. No live URL is promised before deployment succeeds.

For Cloudflare Pages, build with `--base-path /simulator/` and publish `_site/` as the static output directory. This requires a Cloudflare Pages project and appropriate deployment credentials or GitHub integration. No API tokens should be committed.

## Policy integration gate

When P37 has a trained qualified checkpoint for a specific robot:

1. Freeze the robot model revision, actuator mapping, observation normalization, action scaling and control frequency.
2. Export the full model and state handling to ONNX, preserving recurrent memory.
3. Validate native-vs-ONNX parity on fixed observation sets and full closed-loop MuJoCo trials.
4. Add the policy using mjswan's `scene.add_policy()` with matching observation/action MDP terms. Attach only verified assets.
5. Expose user velocity commands and disturbance events **after** the real policy is loaded. Do not translate a scripted movement into a claimed model output.
6. Publish baseline/P37 paired trials and failures with seeds, checkpoint digest, model hashes and exact build version.

Until then, the interface must display `Model-only physics` and contain no fabricated walking, task or recovery metrics.

## Licenses and provenance

The viewer includes mjswan's own credits dialog and collects third-party licenses from MuJoCo Menagerie assets when built from local scenes. Preserve these files in deployments. Verify the terms for each robot model, texture, skin and policy before publishing.

Technical documentation: https://mjswan.readthedocs.io/en/latest/getting-started/examples/ and https://mujoco.readthedocs.io/en/latest/studio/web_viewers.html

## Real measured push tests

The Browser Brain Lab CI executes `sim/web/disturbance_test.py` against the real G1 and Go2 MuJoCo Menagerie models before assembling the website. It compares identical reset states with and without a horizontal force applied from 0.15 to 0.30 seconds. The report records applied force, nominal impulse, final base displacement compared with the unpushed trial, and exact repeatability. The current first pass observed a 0.06315 m difference at 90 N on G1, and 0.00898 m at 40 N on Go2. These are simulation force responses without a learned controller; **do not call them P37 disturbance recovery**.

The mjswan browser has direct mouse/pointer force interaction. Drag the robot using its viewer controls. The native tests verify the underlying MuJoCo force response; pointer interactions still need separate interaction-specific automated validation.

## Genuine recurrent P37 inference in real G1 physics

The native research entrypoint is `sim/src/p37_neuro_sim/g1_p37_train.py` (introduced in PR #14). It trains the actual `P37Neuro` recurrent model with P37's PPO collector and trainer in the official G1 MuJoCo model, persists an integrity-checked checkpoint, reloads it, and sends its actions to the robot's joint actuators. The GitHub Actions workflow `P37 G1 native policy qualification smoke` publishes an **experimental, unqualified** artifact with held-out trial results. Running one PPO update is an integration smoke test; it is not evidence of learned walking or recovery.

To reproduce locally, install the training dependencies and fetch Menagerie:

```bash
git clone --depth 1 https://github.com/google-deepmind/mujoco_menagerie.git _menagerie
cd sim
uv sync --extra train --extra learn --group dev
uv run python -m p37_neuro_sim.g1_p37_train \
  --model ../_menagerie/unitree_g1/scene.xml \
  --output artifacts/g1-p37-experimental --updates 1 --seed 37
uv run python -m p37_neuro_sim.g1_p37_train \
  --model ../_menagerie/unitree_g1/scene.xml \
  --evaluate artifacts/g1-p37-experimental/checkpoint \
  --output artifacts/g1-p37-evaluation \
  --eval-seeds 3 --eval-steps 100 --push-newtons 45
```

**Qualification gate:** the P37 model must demonstrate meaningful commanded locomotion, sustained balance and paired disturbance recovery over at least 100 held-out seeds; disclose failures and compare a realistic baseline. No checkpoint is eligible for the public walking demo until qualification, ONNX export and native-vs-browser closed-loop parity are verified. The public lab remains labeled model-only physics until then.

## Publishing publicly

PR #14 adds `.github/workflows/p37-public-deploy.yml`, which watches for successful `Browser Brain Lab` builds on `main`, downloads their verified artifact, preserves the `/P37-Neuro/` project URL prefix and uploads to Cloudflare Pages using Wrangler. Set **Actions secrets** `CLOUDFLARE_API_TOKEN` (Pages Edit) and `CLOUDFLARE_ACCOUNT_ID` on this repository or at organization level. Optionally set Actions variable `P37_CLOUDFLARE_PROJECT` (default `p37-brain-lab`). After successful deployment and an external HTTPS check, the public URL is under the selected project at `/P37-Neuro/`. A configured workflow is not proof that a site has been deployed.

GitHub Pages is an alternative only when explicitly enabled for the private repository (and when its plan permits). Earlier Pages deployments failed with 404 because Pages is not enabled. Do not claim a live site before a successful deployment response.
