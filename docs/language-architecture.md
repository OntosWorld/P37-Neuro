# Language Architecture

P37 Neuro uses different languages only where they improve a system boundary.

## Python — research and learning plane

Python owns:

- datasets and episode normalization;
- robot-description importers;
- simulation orchestration;
- training and post-training;
- evaluation and benchmarks;
- demonstration conditioning;
- long-context research;
- fleet learning, artifact registry and deployment metadata.

This keeps the model/research loop compatible with the robotics ML ecosystem.

## C++20 — real-time deployment plane

C++ owns:

- the actuator-facing safety envelope;
- low-latency inference integration;
- ROS 2 / hardware adapters;
- deterministic watchdogs and command timing;
- TensorRT/CUDA integration when deployment profiling requires it.

The C++ runtime has no Python dependency and is built/tested independently.

## CUDA / TensorRT — optimization, not architecture

Custom CUDA/Triton kernels or TensorRT-specific code should be introduced only after profiling identifies a bottleneck. Model and runtime contracts must not depend on one accelerator vendor.

## Why not add Rust now?

P37 already requires C++ for ROS 2, robot SDKs, TensorRT and low-level control. Adding Rust to the same deterministic deployment surface would duplicate responsibilities before there is a measured safety/performance need. It remains an option for isolated services later.
