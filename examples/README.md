# P37 Neuro Reference Integrations

These examples demonstrate the Robot Integration Kit contract across materially different robot layouts.

They are **integration examples**, not physical-capability evidence or vendor support claims.

Validate any example from the repository root:

```bash
p37 robot validate examples/tabletop_arm/robot.yaml
p37 robot validate examples/mobile_manipulator/robot.yaml
p37 robot validate examples/quadruped/robot.yaml
```

Use them as starting points for:
- manifest structure;
- robot-description mapping;
- ROS 2 topic contracts;
- safety declarations;
- sensor naming.

A real deployment must replace the reference URDF and topics with the actual machine/controller interface and complete HIL/physical qualification.
