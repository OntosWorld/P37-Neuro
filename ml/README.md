# P37 Neuro ML

The ML package contains the trainable P37 robot brain and its executable training lifecycle.

## What it owns

- variable-morphology embodiment encoding;
- visual scene and demonstration encoding;
- recurrent physical memory;
- high-level task outputs;
- per-joint low-level action generation;
- behavior cloning;
- PPO post-training primitives;
- integrity-checked checkpoints;
- deployment graph export.

## Behavior-cloning experiment

Create a YAML manifest:

```yaml
schema_version: 1
seed: 42
epochs: 10
batch_size: 16
learning_rate: 0.0003
weight_decay: 0.0001
device: cuda
output_dir: runs/e1-baseline
model:
  model_dim: 256
  transformer_heads: 8
  transformer_layers: 4
  temporal_layers: 2
sources:
  - robot: ../robots/arm_a.urdf
    episodes:
      - ../episodes/arm_a_001.jsonl
  - robot: ../robots/arm_b.xml
    episodes:
      - ../episodes/arm_b_001.jsonl
```

Then run:

```bash
uv run p37-neuro-ml train-bc experiment.yaml
uv run p37-neuro-ml evaluate experiment.yaml runs/e1-baseline/final
```

The source list is intentionally multi-embodiment. Each episode is validated against its canonical robot description before entering a batch.

## Deployment export

Install export support and specialize a shared checkpoint for a target maximum joint count:

```bash
uv sync --extra export
uv run p37-neuro-ml export-onnx runs/e1-baseline/final build/p37.onnx --joints 7
```

Export uses PyTorch's current `torch.export`-based ONNX path. The training checkpoint stays cross-embodiment; deployment artifacts may be specialized per robot shape for predictable runtime latency.

## Important

A successful training command produces a model artifact, not a validated general-purpose robot brain. Promotion still requires the held-out simulation, safety and physical gates defined by the root project.

## Testing learned capability

A lower training loss is not enough to qualify P37. Use [../docs/testing.md](../docs/testing.md) for held-out embodiment/task rules, one-shot constraints, memory ablations and PPO before/after evaluation.
