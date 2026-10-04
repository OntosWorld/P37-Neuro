# Robot Integration Kit

The Robot Integration Kit is the enterprise entry point for connecting a robot to P37 without modifying robot-brain internals.

## Robot manifest v2

New integrations use `schema_version: 2`. The manifest is the stable contract between P37 and the robot/controller integration.

It declares:

- robot identity and family;
- URDF, MJCF or OpenUSD description;
- transport and control frequency;
- ROS 2 state/command/stop topics when used;
- canonical-joint to controller command/state mappings;
- control mode and units for every controllable joint;
- per-joint safety overrides;
- sensor sources, modalities and required/optional status;
- canonical observation mappings with units/conversion;
- end-effector mappings;
- adapter capabilities;
- deployment metadata.

Create a starter:

~~~bash
p37 robot init my-robot
~~~

Then replace the placeholders with the real robot description and controller names:

~~~bash
p37 robot validate robots/my-robot/robot.yaml
~~~

## Example

~~~yaml
schema_version: 2
robot_id: acme-arm-01
family: manipulator

description:
  format: urdf
  path: robot.urdf

runtime:
  transport: ros2
  control_frequency_hz: 100
  state_topic: /acme/joint_states
  command_topic: /acme/commands
  stop_topic: /acme/stop

safety:
  max_observation_age_s: 0.1
  require_external_estop: true
  require_controller_watchdog: true

joints:
  - joint: shoulder
    command: axis_1_target
    state: axis_1_position
    control_mode: position
    unit: rad
    scale: 1.0
    offset: 0.0
    safety:
      position_min: -2.5
      position_max: 2.5
      velocity_limit: 1.5
      effort_limit: 60.0

sensor_mappings:
  - name: joint_state
    source: /acme/joint_states
    modality: proprioception
    requirement: required

  - name: wrist_rgb
    source: /acme/wrist/image
    modality: rgb
    requirement: optional
    frame: wrist_camera

observation_mappings:
  - target: proprioception.shoulder_position
    source: axis_1_position
    unit: rad
    scale: 1.0
    offset: 0.0
    required: true

  - target: vision.wrist_rgb
    source: /acme/wrist/image
    required: false

end_effectors:
  - name: gripper
    link: tool0
    command_group: gripper
    frame: tool0

capabilities:
  observation_read: true
  action_write: true
  stop_request: true
  health: true
  position_control: true
  velocity_control: false
  effort_control: false
  time_synchronized: true
~~~

## Joint mapping rules

Every controllable joint in the robot description must have exactly one v2 mapping.

`joint` is the canonical name from the URDF/MJCF/USD embodiment. `command` and `state` are the controller/vendor-side identifiers used by the adapter.

P37 validates:

- complete controllable-joint coverage;
- no unknown canonical joints;
- unique command and state identifiers;
- adapter support for the declared control mode;
- `rad` for revolute/continuous joints and `m` for prismatic joints;
- safety overrides that are equal to or stricter than the robot-description limits.

A manifest cannot use a safety override to expand the physical limits declared by the robot description.

`scale` and `offset` are explicit conversion fields for integrations whose controller representation differs from the canonical P37 value. A zero scale is rejected.

## Sensor contract

`sensor_mappings` names the normalized input P37 expects and the concrete source supplied by the robot integration.

Each sensor declares a stable P37-facing name, vendor/transport source, modality, whether it is required or optional, and an optional coordinate frame.

Required sensors become part of integration validation and later qualification evidence.

## Observation mapping

`observation_mappings` defines how controller- or sensor-side values become the stable P37 observation contract.

Each mapping declares:

- `target`: canonical P37 observation name;
- `source`: a declared joint-state identifier or sensor source;
- optional unit;
- scale and offset conversion;
- whether the observation is required.

Validation rejects observation mappings that reference a source not declared by the joint or sensor integration contract. This keeps model-facing observations independent of manufacturer naming.

For example, a vendor field such as `axis_1_position` can map to `proprioception.shoulder_position` without changing the policy or dataset contract.

## End effectors

`end_effectors` makes tool/gripper boundaries explicit without putting vendor SDK details into the learned policy.

An entry may identify the physical link, controller command group and reference frame.

## Adapter capabilities

The manifest declares what the integration can actually provide.

The core enterprise adapter boundary requires observation reads, action writes, explicit stop requests and health reporting.

Control capabilities are declared separately for position, velocity and effort control. Validation rejects a joint mapping that requests a mode the adapter does not advertise.

`time_synchronized` records whether the integration can provide a synchronized timing source. It is not assumed automatically.

## Safety relationship

The robot description remains the outer physical contract. Manifest safety overrides may narrow those limits for a site, task or deployment, but may not expand them.

P37 does not replace certified emergency stops, safety PLCs, controller-level limits, manufacturer interlocks or site safety procedures.

The learned policy never gains permission to bypass those systems.

## Compatibility

Schema v1 manifests remain readable for existing integrations, but validation emits a migration warning because v1 does not provide explicit joint/controller mappings.

New integrations should use schema v2.

## Runtime mapping

The v2 manifest is executable, not only descriptive.

`RobotIOMapper` translates raw controller/vendor I/O into the existing P37 learning/runtime contracts:

~~~text
vendor/controller observation
            ↓
RawRobotObservation
            ↓
RobotIOMapper
            ↓
P37 Observation

P37 Action
    ↓
RobotIOMapper
    ↓
ControllerCommand
    ↓
vendor/controller
~~~

Joint mappings use one reversible conversion convention:

~~~text
controller_command = canonical_action * scale + offset
canonical_joint_state = (controller_state - offset) / scale
~~~

Explicit `observation_mappings` use:

~~~text
canonical_observation = source_value * scale + offset
~~~

Required sources fail closed when they are missing. Optional observation sources may be absent.

Manifest safety overrides are checked again before controller command conversion. This means a site/task-specific limit cannot be bypassed merely by calling the mapping layer directly.

### Wrapping a vendor transport

Most integrations should use `MappedRobotAdapter` instead of calling the mapper directly.

The vendor-specific layer only implements `RawRobotTransport`:

~~~python
from p37_neuro.integration import (
    AdapterHealth,
    ControllerCommand,
    MappedRobotAdapter,
    RawRobotObservation,
)


class VendorTransport:
    def read_observation(self) -> RawRobotObservation: ...

    def write_command(self, command: ControllerCommand) -> None: ...

    def request_stop(self, reason: str) -> None: ...

    def health(self) -> AdapterHealth: ...


adapter = MappedRobotAdapter("robots/acme-arm/robot.yaml", VendorTransport())
~~~

The resulting adapter satisfies the existing P37 robot boundary: canonical embodiment, normalized observations, canonical actions, stop requests and health.

This keeps manufacturer SDKs, field names and controller command identifiers outside the policy and dataset layers.

## Integration boundary

P37 owns normalized embodiment/state/action contracts and the deterministic runtime boundary. The customer/vendor adapter owns the last mapping to the manufacturer controller, safety PLC or robot-specific SDK.

Custom vendor integrations should implement `p37_neuro.integration.RobotAdapter`.

The adapter exposes canonical `EmbodimentSpec`, normalized observation reads, already-qualified action writes, explicit stop requests and controller/adapter health.

Adapters should be packaged separately when they contain vendor SDKs, customer credentials or proprietary controller logic.

## Recommended enterprise sequence

~~~text
robot description + v2 interface map
            ↓
p37 robot validate
            ↓
simulation preflight
            ↓
p37 qualify --level simulation
            ↓
ROS 2 / controller HIL
            ↓
restricted physical qualification
            ↓
release evidence gate
            ↓
fleet rollout plan
~~~

See `examples/` for complete reference manifests and `docs/testing.md` for qualification.
