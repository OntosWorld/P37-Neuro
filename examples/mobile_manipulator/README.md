# Mobile Manipulator Reference

This directory is a P37 Robot Integration Kit reference for a mobile manipulator.

Validate the integration contract:

```bash
p37 robot validate examples/mobile_manipulator/robot.yaml
```

The included URDF is intentionally small so the integration path is easy to inspect. Replace it with the real robot description and controller topics before simulation, HIL or physical qualification.

This example demonstrates software integration only. It is not evidence that the included morphology has been physically validated with a P37 checkpoint.
