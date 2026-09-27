# P37 Neuro C++ Runtime

The C++20 runtime is the actuator-facing deployment plane. It is intentionally independent of Python.

## Core runtime

The core library provides:

- normalized model-action conversion;
- deterministic joint safety constraints;
- stale-observation rejection;
- recurrent inference-engine ABI;
- a fail-closed runtime loop;
- observation-source and command-sink interfaces.

Build and test without ROS:

```bash
cmake -S runtime_cpp -B runtime_cpp/build
cmake --build runtime_cpp/build --parallel
ctest --test-dir runtime_cpp/build --output-on-failure
```

## Runtime loop

`RuntimeLoop::tick()` performs one deterministic control iteration:

1. read the latest observation;
2. reject missing/stale/clock-invalid data;
3. execute the configured inference engine;
4. convert normalized outputs into physical units;
5. enforce the safety envelope;
6. write commands only when the full chain is allowed;
7. request a stop on every rejected/error path.

## ROS 2 bridge

The optional bridge consumes `sensor_msgs/JointState` in a configured joint order. Its observation vector is:

```text
[position_0 ... position_N, velocity_0 ... velocity_N]
```

It publishes a physical command vector to a configured `Float64MultiArray` topic and publishes a separate `Bool` stop request. A robot integration layer must map that command vector to the correct ros2_control controller and wire the stop topic to the machine's independent safety path.

Build in a sourced ROS 2 environment with:

```bash
cmake -S runtime_cpp -B runtime_cpp/build-ros \
  -DP37_BUILD_ROS2_BRIDGE=ON
cmake --build runtime_cpp/build-ros --parallel
```

The ROS bridge does not replace a certified emergency stop, controller watchdog or robot-manufacturer safety system.

## TensorRT inference

The optional TensorRT backend executes the exact deployment surface exported by
`p37-neuro-ml export-onnx`.

It binds these inputs:

```text
joint_features
joint_state
joint_mask
task_features
demonstration_images
memory
```

and these outputs:

```text
action
high_level
value
next_memory
```

`joint_features`, `joint_mask`, task features and demonstration frames are
loaded as static deployment context. `joint_state` is supplied by the runtime
loop every tick. The backend retains `next_memory` and feeds it back as
`memory` on the next tick; `reset()` clears that recurrent state.

Build it only on a CUDA/TensorRT host:

```bash
cmake -S runtime_cpp -B runtime_cpp/build-trt \
  -DP37_BUILD_TENSORRT=ON
cmake --build runtime_cpp/build-trt --parallel
```

The TensorRT backend intentionally requires fixed tensor shapes. Export a graph
specialized for the robot's padded joint count and selected context sizes.
TensorRT/CUDA compilation and latency validation remain hardware-specific gates.

## Runtime qualification

The runtime must pass independently of model quality. See [../docs/testing.md](../docs/testing.md) for fail-closed runtime, TensorRT, ROS 2, HIL and physical-hardware qualification requirements.
