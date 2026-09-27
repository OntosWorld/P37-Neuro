# Architecture

For the canonical product definition, scope and maturity model, see [overview.md](overview.md).

## Design objective

P37 Neuro should support increasingly capable learned policies without forcing robot-vendor details, simulation APIs or deployment transport into model code.

## Layer boundaries

### Core

Owns shared semantic types, units and versioning. It must not depend on ROS, CUDA, a simulator, or a model framework.

### Embodiment

Owns canonical machine descriptions. Importers for URDF, MJCF, USD or vendor formats translate **into** this representation; policy code does not parse those formats directly.

### Data

Owns the canonical episode contract and provenance. Large binary sensor payloads should be referenced rather than embedded directly in metadata objects.

### Policy

Defines high-level and low-level policy contracts. Concrete PyTorch/JAX implementations remain behind these interfaces.

### Runtime

Owns deterministic checks between a learned policy and physical actuation. Safety is not a model-side convention.

### Simulation

Owns adapters into Isaac Lab, MuJoCo and future engines. Simulator state must be normalized into the same observation model used for physical machines.

## Control hierarchy

P37 Neuro uses a hierarchical design because semantic task decisions and actuator stabilization operate at different timescales.

- **High-level policy:** lower frequency, long context, task progress, manipulation/navigation intent.
- **Low-level policy:** higher frequency, embodiment-specific control, contact dynamics and whole-body behavior.
- **Safety runtime:** deterministic final authority over whether a command is admissible.

## Future model boundaries

The architecture intentionally leaves model choice open. Candidate research areas include:

- vision encoders for temporal physical state;
- graph/token-based embodiment encoders;
- recurrent/long-context transformers;
- diffusion or flow action heads;
- autoregressive action tokenization;
- latent motor primitives;
- model-based or world-model auxiliary objectives;
- RL post-training.

Model experiments must conform to the shared input/output contracts so architecture research does not fragment the runtime stack.
