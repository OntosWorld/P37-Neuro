# Language Architecture

P37 Neuro uses different languages only where they improve a system boundary.

## Python — research and learning plane

Python owns:

- datasets and episode normalization;
- robot-description importers;
- simulation orchestration;
- training and post-training;
- evaluation and qualification gates;
- demonstration conditioning;
- long-context research;
- fleet learning, artifact registry and deployment metadata;
- release signing and production artifact publication.

This keeps the model/research loop compatible with the robotics ML ecosystem.

## C++20 — real-time deployment plane

C++ owns:

- the actuator-facing safety envelope;
- low-latency inference integration;
- ROS 2 / hardware adapters;
- deterministic watchdogs and command timing;
- the deterministic reject-on-error control loop;
- accelerator-specific inference backends.

The C++ runtime has no Python dependency and is built/tested independently.

## CUDA / TensorRT — optional optimized inference

The repository now contains an optional TensorRT backend behind the C++ inference-engine ABI. It binds the same deployment tensors exported by the ML package and carries recurrent memory between control ticks.

TensorRT remains an optimization/deployment backend rather than an architecture dependency:

- the normal runtime builds without CUDA or TensorRT;
- the learned-model contract is accelerator-neutral;
- target-GPU compilation, latency and memory profiling are release gates;
- custom CUDA/Triton kernels should be added only after profiling identifies a measured bottleneck.

## Cloud backends

Production release infrastructure is also optional:

- S3/S3-compatible object storage publishes immutable content-addressed model artifacts;
- Google Cloud KMS can hold the EC_SIGN_ED25519 release private key so key material does not enter the P37 process;
- local filesystem storage and injected Ed25519 keys remain available for development and CI.

Cloud credentials, IAM policy and production key provisioning are deployment concerns and are not stored in source control.

## Why not add Rust now?

P37 already requires C++ for ROS 2, robot SDKs, TensorRT and low-level control. Adding Rust to the same deterministic deployment surface would duplicate responsibilities before there is a measured safety/performance need. It remains an option for isolated services later.
