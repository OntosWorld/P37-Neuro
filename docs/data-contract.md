# Data Contract

## Goals

The P37 data contract exists to make trajectories from different robot bodies trainable together while preserving the information required for safety, provenance and replay.

## Requirements

Every episode must identify:

- an immutable episode ID;
- embodiment ID and embodiment schema version;
- task/goal identifier;
- collection source;
- timestamps in one declared clock domain;
- observations;
- actions;
- outcome and termination reason;
- intervention and failure markers;
- dataset/provenance metadata.

## Physical units

Public fields use SI units unless a field explicitly states otherwise:

- position: radians or metres depending on joint type;
- angular velocity: rad/s;
- linear velocity: m/s;
- effort: N·m for rotational joints, N for linear joints;
- time: seconds.

Unit conversion occurs at adapters, never implicitly inside the policy.

## Binary payloads

Images, video, point clouds and large tensor streams should live in content-addressed/object storage. Episode records carry immutable references and checksums.

## Dataset immutability

Published dataset versions are immutable. Corrections produce a new version with lineage back to the source version.

## Failure preservation

A failed rollout is not automatically bad data. Failure type, intervention, unsafe-command rejection and recovery attempts should be retained when consent/provenance requirements allow.
