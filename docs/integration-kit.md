# Robot Integration Kit

The Robot Integration Kit is the enterprise entry point for connecting a robot to P37 without modifying the robot-brain internals.

## Manifest

Each integration uses a versioned `robot.yaml` that declares:
- robot identity and family;
- URDF, MJCF or OpenUSD description;
- transport type;
- control frequency;
- ROS 2 state/command/stop topics when used;
- safety requirements;
- sensor mappings;
- deployment metadata.

Create a starter manifest:

```bash
p37 robot init my-robot
```

Point the manifest at the real robot description and validate it:

```bash
p37 robot validate robots/my-robot/robot.yaml
```

Validation checks the manifest schema, robot description, controllable joints, runtime interface and declared safety profile.

## Integration boundary

P37 owns normalized embodiment/state/action contracts and the deterministic runtime boundary. The customer/vendor adapter owns the last mapping to the manufacturer controller, safety PLC or robot-specific SDK.

The P37 bridge does not replace manufacturer safety functions, certified emergency stops or controller-level protections.

## Recommended enterprise sequence

```text
robot description + interface map
            ↓
p37 robot validate
            ↓
MuJoCo / simulator mapping
            ↓
P37 qualification report
            ↓
ROS 2 / controller HIL
            ↓
restricted physical qualification
            ↓
fleet rollout plan
```

See `examples/` for reference layouts and `docs/testing.md` for qualification.

## Stable adapter API

Custom vendor integrations should implement `p37_neuro.integration.RobotAdapter`.

The adapter boundary exposes only:

- the canonical `EmbodimentSpec`;
- normalized observation reads;
- already-qualified action writes;
- an explicit stop request;
- controller/adapter health.

`AdapterHealth` reports connection, state freshness, controller readiness, external E-stop availability and watchdog availability. This keeps manufacturer SDKs outside the learned-policy layer and gives enterprise teams one stable place to integrate proprietary controllers.

Adapters should be packaged separately from P37 when they contain vendor SDKs, customer credentials or proprietary controller logic.
