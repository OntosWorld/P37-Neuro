# P37 Neuro ML

This package contains the trainable robot-brain model used by P37 Neuro.

It is intentionally separated from the lightweight platform package so data tooling, registries and robot/runtime contracts do not require PyTorch.

## Current model

`P37Neuro` is a hierarchical, variable-morphology policy with:

- a joint/embodiment Transformer encoder;
- per-step proprioceptive state encoding;
- a visual encoder shared by scene and demonstration frames;
- task/demo context attention;
- recurrent temporal memory;
- a high-level intent head;
- a per-joint low-level action distribution;
- a value head for reinforcement-learning post-training.

Padded joints are masked, allowing batches to contain robots with different joint counts. The model returns its memory state explicitly so inference can carry context across control windows.

## Training

The reference trainer implements behavior cloning. `ppo_loss` provides the post-training objective used after a stable imitation-trained base policy exists.

The package also provides integrity-checked checkpoints: weights are stored with a manifest containing the model configuration and SHA-256 digest.

## Development

```bash
cd ml
uv sync
uv run pytest
```

The current tests are CPU-safe and are intended as architecture/gradient/checkpoint smoke tests. Large-scale training belongs on GPU workers.
