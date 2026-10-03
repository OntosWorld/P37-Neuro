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
