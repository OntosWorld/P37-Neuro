# P37 Brain Lab: scene-first robotics workbench

The browser lab presents **10 actual MuJoCo Menagerie robots** with physical
simulation run in WebAssembly. The scene occupies the primary viewport and
includes camera, pause/reset and pointer interactions from the mjswan engine.

## Robot catalog

| Group | Body | Menagerie source |
| --- | --- | --- |
| Humanoids | Unitree G1 | `unitree_g1` |
| Humanoids | Unitree H1 | `unitree_h1` |
| Humanoids | Booster T1 | `booster_t1` |
| Quadrupeds | Unitree Go2 | `unitree_go2` |
| Quadrupeds | Boston Dynamics Spot | `boston_dynamics_spot` |
| Quadrupeds | ANYmal C | `anybotics_anymal_c` |
| Manipulators | Franka Panda | `franka_emika_panda` |
| Manipulators | Universal Robots UR5e | `universal_robots_ur5e` |
| Mobile | Hello Robot Stretch | `hello_robot_stretch` |
| Aerial | Crazyflie 2 | `bitcraze_crazyflie_2` |

The robot list, categories and scene IDs are defined in
`sim/web/catalog.py`. Adding an entry requires a real Menagerie MJCF
`scene.xml` and successful physics compilation, not a generated animation.

## Presentation

The new workbench uses a restrained dark interface influenced by modern
interactive robotics demos. Changes to the **physical scene** are isolated:

- A neutral graphite procedural sky/floor replaces the saturated Menagerie
  colors; no collision shape or actuator dynamics are replaced.
- Two studio lights make robot geometry legible under changing camera angles.
- Four subtle floor-reference markers are collision-disabled.
- The native MuJoCo controls panel is hidden by default so the actual robot
  fills the viewport. Press **Controls** to expose mjswan's interactions.
- The right inspector separates real simulation parameters from P37's measured
  training experiment results.

This is an independent Ontos design; it does not reuse Skild's application code
or imply that we have reproduced Skild's trained robot capabilities.

## P37 evidence is separate from the interactive simulator

The **P37 Research** inspector shows the actual recurrent P37 checkpoint's
short G1 MuJoCo evaluation and verified ONNX output parity. Two of the three
original short held-out trials fell. The third survived a two-second horizon.
A 45 N push scheduled at 2.0 seconds was not demonstrated to be recovered from.
This checkpoint is **experimental** and **not qualified for walking**.

The interactive 10-body physics engine does not run this neural checkpoint.
Users can move and perturb the physical models, but should not interpret passive
physics or mjswan viewer manipulation as a trained P37 behavior.

### To genuinely enable browser P37 behavior

1. Train a G1 controller with longer episodes, velocity tracking, curriculum,
   ground contacts, disturbance randomization and successful held-out tests.
2. Freeze actor observation order and scales, joint/actuator mapping, control
   rate, action bounds, default pose and recurrent state.
3. Export the qualified P37 checkpoint into mjswan-compatible ONNX policy
   input and output groups. Verify joint order and frame conventions.
4. Compare full native-P37-vs-browser closed-loop rollouts, including falls,
   pushes and velocity commands across fixed seeds. Publish failure rates.
5. Only then expose an active **P37-controlled** mode with walking commands.

Until all five steps succeed, the UI must indicate **Model-only** and
**Trained P37 policy: NOT ATTACHED**.

## Build and deployment

```bash
git clone --depth 1 https://github.com/google-deepmind/mujoco_menagerie.git _menagerie
python -m pip install mjswan pytest playwright
python sim/web/build_mjswan.py --menagerie _menagerie --base-path /P37-Neuro/simulator/
python sim/web/assemble_site.py --output _pages
python -m playwright install chromium
python sim/web/e2e_test.py --site _pages --url-prefix /P37-Neuro/ --screenshots _screenshots
```

The GitHub Pages workflow builds the ten-scene bundle, asserts the catalog and
asset presence, and launches Chromium against the project URL prefix. It
collects screenshots as provenance and publishes to
`https://ontosrobotics.github.io/P37-Neuro/` only after a successful build.

The Menagerie model licenses and the mjswan notice remain part of the shipped
viewer. Preserve robot source attribution; inspect each model license before
redistributing beyond the standard simulation use.
