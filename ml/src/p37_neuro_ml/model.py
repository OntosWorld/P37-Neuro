"""Hierarchical cross-embodiment robot-brain model."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn


@dataclass(frozen=True, slots=True)
class NeuroConfig:
    """Shape and capacity configuration for the trainable robot brain."""

    joint_feature_dim: int = 10
    joint_state_dim: int = 2
    task_feature_dim: int = 128
    model_dim: int = 128
    high_level_dim: int = 32
    transformer_heads: int = 4
    transformer_layers: int = 2
    temporal_layers: int = 2
    context_length: int = 128
    image_channels: int = 3
    dropout: float = 0.1

    def __post_init__(self) -> None:
        positive = (
            self.joint_feature_dim,
            self.joint_state_dim,
            self.task_feature_dim,
            self.model_dim,
            self.high_level_dim,
            self.transformer_heads,
            self.transformer_layers,
            self.temporal_layers,
            self.context_length,
            self.image_channels,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("all model dimensions must be positive")
        if self.model_dim % self.transformer_heads:
            raise ValueError("model_dim must be divisible by transformer_heads")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")


@dataclass(slots=True)
class P37Output:
    """Outputs used by imitation learning, RL and the runtime exporter."""

    high_level: Tensor
    action_mean: Tensor
    action_log_std: Tensor
    value: Tensor
    memory: Tensor


class VisionEncoder(nn.Module):
    """Compact visual encoder used for current scene and demonstration frames."""

    def __init__(self, channels: int, model_dim: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(channels, 32, kernel_size=5, stride=2, padding=2),
            nn.GELU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, model_dim),
            nn.LayerNorm(model_dim),
        )

    def forward(self, images: Tensor) -> Tensor:
        if images.ndim != 4:
            raise ValueError("images must have shape [N, C, H, W]")
        return self.network(images)


class P37Neuro(nn.Module):
    """Hierarchical variable-morphology robot brain.

    The model separates four signals:
    - static embodiment/joint features;
    - time-varying proprioception;
    - current visual state;
    - task context from demonstrations or external semantic features.

    A recurrent temporal core gives deployment-time memory without changing weights.
    The low-level action head is joint-token based, allowing one checkpoint to emit
    commands for different joint counts using a padding mask.
    """

    def __init__(self, config: NeuroConfig) -> None:
        super().__init__()
        self.config = config
        d = config.model_dim

        self.joint_feature_projection = nn.Sequential(
            nn.Linear(config.joint_feature_dim, d),
            nn.LayerNorm(d),
            nn.GELU(),
        )
        self.joint_state_projection = nn.Sequential(
            nn.Linear(config.joint_state_dim, d),
            nn.LayerNorm(d),
            nn.GELU(),
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d,
            nhead=config.transformer_heads,
            dim_feedforward=d * 4,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.embodiment_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.transformer_layers,
            enable_nested_tensor=False,
        )

        context_layer = nn.TransformerEncoderLayer(
            d_model=d,
            nhead=config.transformer_heads,
            dim_feedforward=d * 4,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.context_encoder = nn.TransformerEncoder(
            context_layer,
            num_layers=config.transformer_layers,
            enable_nested_tensor=False,
        )
        self.context_position = nn.Parameter(torch.zeros(1, config.context_length, d))
        nn.init.normal_(self.context_position, std=0.02)

        self.task_projection = nn.Linear(config.task_feature_dim, d)
        self.vision_encoder = VisionEncoder(config.image_channels, d)

        self.fusion = nn.Sequential(
            nn.Linear(d * 4, d * 2),
            nn.GELU(),
            nn.LayerNorm(d * 2),
            nn.Linear(d * 2, d),
            nn.GELU(),
        )
        self.temporal_core = nn.GRU(
            input_size=d,
            hidden_size=d,
            num_layers=config.temporal_layers,
            batch_first=True,
            dropout=config.dropout if config.temporal_layers > 1 else 0.0,
        )
        self.temporal_norm = nn.LayerNorm(d)

        self.high_level_head = nn.Sequential(
            nn.Linear(d, d),
            nn.GELU(),
            nn.Linear(d, config.high_level_dim),
        )
        self.action_head = nn.Sequential(
            nn.Linear(d * 3, d),
            nn.GELU(),
            nn.Linear(d, 1),
            nn.Tanh(),
        )
        self.value_head = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.action_log_std_parameter = nn.Parameter(torch.tensor(-1.0))

    @staticmethod
    def _masked_mean(tokens: Tensor, mask: Tensor, dim: int) -> Tensor:
        weights = mask.to(tokens.dtype)
        while weights.ndim < tokens.ndim:
            weights = weights.unsqueeze(-1)
        numerator = (tokens * weights).sum(dim=dim)
        denominator = weights.sum(dim=dim).clamp_min(1.0)
        return numerator / denominator

    def _encode_images(self, images: Tensor) -> Tensor:
        leading = images.shape[:-3]
        flattened = images.reshape(-1, *images.shape[-3:])
        encoded = self.vision_encoder(flattened)
        return encoded.reshape(*leading, self.config.model_dim)

    def _context(
        self,
        batch_size: int,
        demonstration_images: Tensor | None,
        task_features: Tensor | None,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        tokens: list[Tensor] = []
        if demonstration_images is not None:
            if demonstration_images.ndim != 5:
                raise ValueError("demonstration_images must be [B, D, C, H, W]")
            tokens.append(self._encode_images(demonstration_images))
        if task_features is not None:
            if task_features.ndim != 3:
                raise ValueError("task_features must be [B, K, F]")
            tokens.append(self.task_projection(task_features))
        if not tokens:
            return torch.zeros(batch_size, self.config.model_dim, device=device, dtype=dtype)

        context_tokens = torch.cat(tokens, dim=1)
        if context_tokens.shape[1] > self.config.context_length:
            raise ValueError("context exceeds configured context_length")
        context_tokens = context_tokens + self.context_position[:, : context_tokens.shape[1]]
        encoded = self.context_encoder(context_tokens)
        return encoded.mean(dim=1)

    def forward(
        self,
        *,
        joint_features: Tensor,
        joint_state: Tensor,
        joint_mask: Tensor,
        time_mask: Tensor | None = None,
        scene_images: Tensor | None = None,
        demonstration_images: Tensor | None = None,
        task_features: Tensor | None = None,
        memory: Tensor | None = None,
    ) -> P37Output:
        """Run one sequence through the brain.

        Shapes:
        joint_features: [B, J, F]
        joint_state: [B, T, J, S]
        joint_mask: [B, J], True for real joints
        time_mask: optional [B, T], True for recorded timesteps
        scene_images: optional [B, T, C, H, W]
        demonstration_images: optional [B, D, C, H, W]
        task_features: optional [B, K, task_feature_dim]
        memory: optional [temporal_layers, B, model_dim]
        """
        if joint_features.ndim != 3 or joint_state.ndim != 4 or joint_mask.ndim != 2:
            raise ValueError("invalid joint tensor rank")
        batch, joints, _ = joint_features.shape
        if joint_state.shape[0] != batch or joint_state.shape[2] != joints:
            raise ValueError("joint_state does not match joint_features")
        if joint_mask.shape != (batch, joints):
            raise ValueError("joint_mask shape mismatch")
        if not torch.all(joint_mask.any(dim=1)):
            raise ValueError("every embodiment needs at least one active joint")

        steps = joint_state.shape[1]
        if time_mask is None:
            time_mask = torch.ones(batch, steps, dtype=torch.bool, device=joint_state.device)
        if time_mask.shape != (batch, steps):
            raise ValueError("time_mask shape mismatch")
        if not torch.all(time_mask.any(dim=1)):
            raise ValueError("every sequence needs at least one valid timestep")
        transitions = time_mask[:, 1:].to(torch.int8) - time_mask[:, :-1].to(torch.int8)
        if torch.any(transitions > 0):
            raise ValueError("time_mask must contain a contiguous valid prefix")
        padding_mask = ~joint_mask.bool()
        joint_tokens = self.joint_feature_projection(joint_features)
        joint_tokens = self.embodiment_encoder(joint_tokens, src_key_padding_mask=padding_mask)
        embodiment = self._masked_mean(joint_tokens, joint_mask, dim=1)

        state_tokens = self.joint_state_projection(joint_state)
        body_tokens = state_tokens + joint_tokens[:, None, :, :]
        state_mask = joint_mask[:, None, :].expand(batch, steps, joints)
        body_state = self._masked_mean(body_tokens, state_mask, dim=2)

        if scene_images is None:
            visual_state = torch.zeros_like(body_state)
        else:
            if scene_images.shape[:2] != (batch, steps):
                raise ValueError("scene_images must align with batch and time")
            visual_state = self._encode_images(scene_images)

        context = self._context(
            batch,
            demonstration_images,
            task_features,
            device=joint_state.device,
            dtype=joint_state.dtype,
        )
        context_sequence = context[:, None, :].expand(batch, steps, -1)
        embodiment_sequence = embodiment[:, None, :].expand(batch, steps, -1)
        fused = self.fusion(
            torch.cat((body_state, visual_state, context_sequence, embodiment_sequence), dim=-1)
        )

        lengths = time_mask.sum(dim=1).to(torch.int64).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(
            fused, lengths, batch_first=True, enforce_sorted=False
        )
        packed_temporal, next_memory = self.temporal_core(packed, memory)
        temporal, _ = nn.utils.rnn.pad_packed_sequence(
            packed_temporal, batch_first=True, total_length=steps
        )
        temporal = self.temporal_norm(temporal)
        temporal = temporal.masked_fill(~time_mask[:, :, None], 0.0)
        high_level = self.high_level_head(temporal)
        value = self.value_head(temporal).squeeze(-1)

        temporal_joint = temporal[:, :, None, :].expand(batch, steps, joints, -1)
        joint_sequence = joint_tokens[:, None, :, :].expand(batch, steps, joints, -1)
        action_input = torch.cat((temporal_joint, joint_sequence, state_tokens), dim=-1)
        action_mean = self.action_head(action_input).squeeze(-1)
        valid_action = state_mask & time_mask[:, :, None]
        action_mean = action_mean.masked_fill(~valid_action, 0.0)
        log_std = self.action_log_std_parameter.expand_as(action_mean)
        log_std = log_std.masked_fill(~valid_action, 0.0)
        high_level = high_level.masked_fill(~time_mask[:, :, None], 0.0)
        value = value.masked_fill(~time_mask, 0.0)

        return P37Output(
            high_level=high_level,
            action_mean=action_mean,
            action_log_std=log_std,
            value=value,
            memory=next_memory,
        )
