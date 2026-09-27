# Physical-System Safety

P37 Neuro is research software that will eventually interface with machines capable of causing physical harm. Safety is therefore an architectural boundary, not a final deployment checklist.

## Principles

1. **Fail closed.** Unknown joints, stale commands, non-finite values and undefined control semantics are rejected.
2. **Independent enforcement.** Learned policies cannot disable deterministic constraints.
3. **Explicit control mode.** Position, velocity and effort commands are never inferred from context.
4. **Hardware has final limits.** Software limits do not replace drive/controller limits, emergency stops or manufacturer safety systems.
5. **Simulation is not certification.** Passing simulation tests does not authorize deployment.
6. **Progressive access.** New policies move through offline replay, simulation, hardware-in-the-loop and restricted physical testing before broader deployment.

## Release gates for physical execution

Before a model can control real hardware, the deployment should define and verify:

- supported embodiment/version;
- maximum command rates;
- position/velocity/effort envelopes;
- timeout behavior;
- emergency-stop behavior;
- watchdog ownership;
- collision/workspace constraints;
- operator intervention path;
- logging and replay completeness;
- rollback model/checkpoint.

## Non-goals of the current safety module

The initial `JointSafetyEnvelope` is a software contract test, not a complete robot safety controller. It does not provide certified collision avoidance, functional safety, redundant braking or human-safe motion planning.
