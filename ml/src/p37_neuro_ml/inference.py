"""Stateful model execution used by simulators and validation workers."""

from __future__ import annotations

from dataclasses import dataclass, field

import torch

from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec
from p37_neuro.runtime.safety import JointSafetyEnvelope
from torch import Tensor

from p37_neuro_ml.dataset import denormalize_action, joint_features
from p37_neuro_ml.model import P37Neuro


@dataclass(slots=True)
class InferenceSession:
    """Carries recurrent P37 memory across consecutive control windows."""

    model: P37Neuro
    embodiment: EmbodimentSpec
    device: torch.device | str = "cpu"
    task_features: Tensor | None = None
    demonstration_images: Tensor | None = None
    _memory: Tensor | None = field(default=None, init=False, repr=False)
    _joint_features: Tensor = field(init=False, repr=False)
    _joint_mask: Tensor = field(init=False, repr=False)
    _safety: JointSafetyEnvelope = field(
        default_factory=JointSafetyEnvelope, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.model.to(self.device)
        self.model.eval()
        self._joint_features = torch.tensor(
            [joint_features(joint) for joint in self.embodiment.joints],
            dtype=torch.float32,
            device=self.device,
        )[None, :, :]
        self._joint_mask = torch.ones(
            1, len(self.embodiment.joints), dtype=torch.bool, device=self.device
        )
        if self.task_features is not None:
            self.task_features = self.task_features.to(self.device)
        if self.demonstration_images is not None:
            self.demonstration_images = self.demonstration_images.to(self.device)

    def reset(self) -> None:
        self._memory = None

    def act(self, observation: Observation) -> Action:
        state = torch.zeros(
            1, 1, len(self.embodiment.joints), 2, dtype=torch.float32, device=self.device
        )
        for index, joint in enumerate(self.embodiment.joints):
            state[0, 0, index, 0] = observation.joint_position.get(joint.name, 0.0)
            state[0, 0, index, 1] = observation.joint_velocity.get(joint.name, 0.0)

        with torch.no_grad():
            output = self.model(
                joint_features=self._joint_features,
                joint_state=state,
                joint_mask=self._joint_mask,
                time_mask=torch.ones(1, 1, dtype=torch.bool, device=self.device),
                demonstration_images=self.demonstration_images,
                task_features=self.task_features,
                memory=self._memory,
            )
        self._memory = output.memory
        normalized = output.action_mean[0, 0]
        commands = {
            joint.name: denormalize_action(joint, float(normalized[index]))
            for index, joint in enumerate(self.embodiment.joints)
        }
        action = Action(timestamp_s=observation.timestamp_s, joint_commands=commands)
        return self._safety.apply(action, self.embodiment).action
