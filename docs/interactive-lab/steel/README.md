# P37-Neuro Steel WebGPU workcell + MimicGen data bridge

This is an **additive** research demo. Nothing in the existing Brain Lab, the
MuJoCo experiment runner, architecture explorer, or recorded evidence viewer is
removed or replaced.

## What runs in the browser

A separate React/Three.js/WebGPU app built on the official
[@skild-ai/steel-webgpu](https://github.com/skild-ai/steel-webgpu)
package (Apache-2.0):

- Three tabletop environments: robotics workcell, packing station, inspection bench
- Physical ground, oak/metal workbench, chair, monitoring hardware
- Dynamic parcels, cans, balls, and bins with mass, contact geometry and Steel picking/dragging
- Two **original procedural URDF** reference arm morphologies (compact and extended)
- Deterministic joint position targets, pause/reset, contact stats and collision-debug toggle
- Procedural woodgrain, metallic/ceramic materials, shadows, multiple lighting sources
- WebGPU capability fallback and clear source/evidence status in the UI

**These robot models are reference geometry, not Panda, Sawyer, IIWA or UR5e.**
The reference joint commands use the Steel joint-control API: there is **no
trained P37-Neuro checkpoint connected** to the browser demo.

### Run locally

```bash
cd docs/interactive-lab/steel
npm install
npm run dev
# Visit http://localhost:5173
```

For production static assets: `npm run build`. The resulting `dist/` can be
deployed under any existing site's subdirectory. Do **not** replace the existing
GitHub Pages site root or Brain Lab with this directory. It is intentionally a
separate Vite project with relative production asset paths.

A workflow named **Steel WebGPU workcell** compiles and uploads the static bundle
as `p37-steel-workcell-static-preview`. A successful compilation is not proof of
browser GPU functionality; test an actual WebGPU browser as a separate acceptance gate.

## MimicGen dataset integration

Official released dataset: [amandlek/mimicgen_datasets](https://huggingface.co/datasets/amandlek/mimicgen_datasets).

The *dataset* is CC BY 4.0. The *MimicGen generation code* has a distinct
NVIDIA Source Code License; **this implementation does not use or vendor that
code**. Cite the original MimicGen authors and retain source attribution.

Suggested first comparison: download the original robot-transfer versions
`robot/square_d0_panda.hdf5` and `robot/square_d0_sawyer.hdf5` from the
official Hugging Face dataset, after confirming file availability, version and
size. Do not try to download the entire 149 GB collection for a demo.

From the repository root, with Python 3.12+ and `h5py` installed:

```bash
uv run --with h5py python scripts/mimicgen_to_p37.py \
  --source panda=/path/to/robot/square_d0_panda.hdf5 \
  --source sawyer=/path/to/robot/square_d0_sawyer.hdf5 \
  --task square_d0 --demo demo_0 --control-hz 20 \
  --output artifacts/mimicgen-square-offline.json
```

`--control-hz` is an **explicit required value**. Check the rate against
the actual source environment. The value shown is an example, not a claim
about every dataset's frequency.

Upload the generated JSON in the existing
[recorded experiment comparison viewer](../compare/index.html).
The converted records include actual source joint positions/velocities and
the source-native action vector. Native actions are preserved as
`observation.state.source_action_*` so they cannot be mistaken for joint
actuator commands. Without explicit controller semantics and replay
compatibility, `Action.joint_commands` remains empty.

A converted demonstration is **offline dataset playback**, not a P37 policy
rollout. The exporter marks these records `policy_attached=false`,
`outcome=unverified`, and `evidence_level=T1` conservatively.
No held-out cross-embodiment success rate is inferred from MimicGen
demonstration availability.

### Next integration gates

1. Read real datasets and verify source controller/action conventions per robot.
2. Implement a typed controller-specific action projection for training P37.
3. Train a frozen **shared checkpoint**, with explicitly separate training and
   held-out robot/task splits.
4. Run in closed-loop **MuJoCo/robosuite** under the matching task environment.
5. Export qualified episode traces with hashes, failures and success metrics.
6. Only then connect a browser policy adapter or label P37 learned transfer.
7. Add source-licensed manufacturer robot meshes and calibrated PBR materials
   for industrial-grade visuals; current geometric arms remain reference designs.

## License and asset boundaries

| Component | Provenance | Use |
| --- | --- | --- |
| Steel WebGPU | skild-ai/steel-webgpu; Apache-2.0 | Browser solver and React rendering bindings |
| Reference URDF arms | Original assets created in Ontos repository | Procedural demonstration models |
| Furniture and objects | Procedural meshes/textures written in this project | No external asset downloads |
| MimicGen datasets | Original MimicGen authors; CC BY 4.0 | External operator-provided HDF5 source |
| MimicGen source code | NVIDIA Source Code License | **Not used or redistributed** |

## Verification

- CI: `npm run build` (TypeScript and Vite) and local HDF5 fixture tests.
- Browser QA: WebGPU startup, URDF loading, contact/picking/drag, pause/reset,
  object insertion, shadow/material rendering and mobile fallback.
- Dataset QA: source attribution, no fabricated action conversion or success
  claims, two-embodiment trace export.

## Public, genuine source-data replay

The repository now ships two **real** published MimicGen Square source episodes,
verified against the official 16.5 MB HDF5 SHA-256 and converted into P37's
canonical episode/evidence format:

- [Official source recording in the experiment comparison viewer](../compare/index.html?sample=mimicgen) — a one-click timeline displaying source joint states, recorded end-effector trajectory and controller-native action channels
- [Public trace JSON](../compare/samples/mimicgen-square-source.json) and [source manifest](../compare/samples/manifest.json)
- The standalone Steel workcell's **Show real MimicGen motion** control overlays the recorded end-effector trajectory in 3D, with two selectable original source episodes

The original data are CC BY 4.0: Ajay Mandlekar et al., *MimicGen: A Data
Generation System for Scalable Robot Learning using Human Demonstrations*, CoRL
2023, hosted by `amandlek/mimicgen_datasets`.

**Exactly what works:** genuine HDF5 decoding, P37 canonical episode normalization,
source-verifiable trace export, synchronized browser playback, and 3D visualization
of an original robot's recorded end-effector positions. The workcell additionally
has Steel-powered interactive contact physics for furniture and objects.

**Not yet demonstrated:** trained P37-Neuro control, P37 autonomous task success,
learned cross-body transfer or calibrated replay of robot-object contact in Steel.
The original recordings are two episodes from the *same* Panda source embodiment.
The reference URDF in the workcell is not the Panda model; source coordinates are
shown as an independent overlay, not used as actuator targets.

The offline source replay is generated by `scripts/publish_mimicgen_replay.py`
and reproducibly validated by the read-only GitHub Actions workflow
`publish-mimicgen-replay.yml`. Dataset integrity is checked before publication.

## Visual and contact-quality upgrade (v3)

- Full-mesh **Franka Emika Panda** is an **optional** Steel model. Its geometry,
  kinematics, masses and joint definitions come from Google DeepMind's
  [MuJoCo Menagerie Panda](https://github.com/google-deepmind/mujoco_menagerie/tree/main/franka_emika_panda),
  Apache-2.0, pinned to commit 370c43965323c0944b433b202aac5058b5f907a9.
  These are manufacturer-derived assets, not trained P37-Neuro weights.
- 69 upstream files (~34.3 MB) download only at build/dev time, after which
  every file is checked against its git blob hash. They are hosted on the
  same website, omitted from git history and included in the produced bundle.
  Run the npm script sync:assets if the local model cache needs refreshing.
- The upstream panda.xml and LICENSE retain original verified bytes. The
  generated panda-steel.xml is an explicitly marked compatibility derivative
  that adds physical finger position actuators: Steel 0.1.0 does not import
  MuJoCo tendon drives. This is a model adaptation, not a manufacturer-tested
  controller.
- Compact and extended original URDFs now contain **independent, moving,
  collision-enabled prismatic fingers**. Steel 0.1.0 imports joint damping but
  not URDF motor stiffness; P37's deterministic force-limited PD controller
  uses the real GPU solver's joint coordinates and velocities instead.
  This is not a trained AI policy.
- Gripper target and measured clearance are displayed separately. The drop
  test reports a real rigid body's height and travel, read back from the
  solver. Worktop visual and contact surface are both at 0.814 meters.
- A non-coplanar matte workshop floor replaces the overlapping studio floors
  that had produced visible striping; lighting now avoids duplicate harsh
  shadows.

**Do not claim pick-and-place or reliable grasping** until a contact-qualified
task evaluation demonstrates them. Original data playback in the MimicGen
viewer remains separate from these deterministic control experiments.

**Validation:** production build and pinned assets, WebGPU physics on macOS
Metal, measured jaw response, gravity-drop settling and existing Brain Lab
regression checks.
