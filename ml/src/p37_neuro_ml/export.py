"""Deployment export boundary for P37 Neuro checkpoints."""

from __future__ import annotations

from pathlib import Path

import torch
from torch import Tensor, nn

from p37_neuro_ml.checkpoint import load_checkpoint
from p37_neuro_ml.model import P37Neuro


class RuntimeExportWrapper(nn.Module):
    """Tensor-only deployment surface for one-step recurrent inference."""

    def __init__(self, model: P37Neuro) -> None:
        super().__init__()
        self.model = model

    def forward(
        self,
        joint_features: Tensor,
        joint_state: Tensor,
        joint_mask: Tensor,
        task_features: Tensor,
        demonstration_images: Tensor,
        memory: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        batch = joint_state.shape[0]
        time_mask = torch.ones(
            batch,
            joint_state.shape[1],
            dtype=torch.bool,
            device=joint_state.device,
        )
        output = self.model(
            joint_features=joint_features,
            joint_state=joint_state,
            joint_mask=joint_mask,
            time_mask=time_mask,
            task_features=task_features,
            demonstration_images=demonstration_images,
            memory=memory,
        )
        return (
            output.action_mean[:, -1, :],
            output.high_level[:, -1, :],
            output.value[:, -1],
            output.memory,
        )


def export_onnx(
    checkpoint_dir: str | Path,
    output_path: str | Path,
    *,
    joints: int,
    image_height: int = 64,
    image_width: int = 64,
    demonstration_frames: int = 1,
    task_tokens: int = 1,
) -> Path:
    """Export a deployment graph for a fixed maximum embodiment shape.

    The trained checkpoint remains cross-embodiment. Deployment graphs can be
    specialized per robot/max-joint shape for lower runtime overhead.
    """
    if joints <= 0 or image_height <= 0 or image_width <= 0:
        raise ValueError("export dimensions must be positive")
    if demonstration_frames <= 0 or task_tokens <= 0:
        raise ValueError("context dimensions must be positive")

    model, _ = load_checkpoint(checkpoint_dir)
    model.eval()
    config = model.config
    wrapper = RuntimeExportWrapper(model)

    inputs = (
        torch.zeros(1, joints, config.joint_feature_dim),
        torch.zeros(1, 1, joints, config.joint_state_dim),
        torch.ones(1, joints, dtype=torch.bool),
        torch.zeros(1, task_tokens, config.task_feature_dim),
        torch.zeros(
            1,
            demonstration_frames,
            config.image_channels,
            image_height,
            image_width,
        ),
        torch.zeros(config.temporal_layers, 1, config.model_dim),
    )

    try:
        program = torch.onnx.export(
            wrapper,
            inputs,
            input_names=[
                "joint_features",
                "joint_state",
                "joint_mask",
                "task_features",
                "demonstration_images",
                "memory",
            ],
            output_names=["action", "high_level", "value", "next_memory"],
            dynamo=True,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "ONNX export dependencies are missing; install p37-neuro-ml[export]"
        ) from exc

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    program.save(str(destination))
    return destination
