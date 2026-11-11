"""Read official MimicGen (robomimic HDF5) data into canonical P37 episodes.

The dataset's actions are *controller-native*, often end-effector commands rather
than joint targets. They are preserved as numeric state channels prefixed
"source_action_" and are NOT mislabeled as physical joint commands.
No learned P37 policy is run or implied by these recorded trajectories.

MimicGen dataset: CC BY 4.0. MimicGen source code has separate license terms.
This adapter does not import or redistribute MimicGen's source code.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation


@dataclass(frozen=True, slots=True)
class MimicGenSelection:
    """An explicit source dataset and trajectory selected by an operator."""

    path: Path
    demo_id: str
    embodiment_id: str
    task_id: str
    control_hz: float

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.demo_id, self.embodiment_id, self.task_id)):
            raise ValueError("demo_id, embodiment_id and task_id are required")
        if not isfinite(self.control_hz) or self.control_hz <= 0:
            raise ValueError("control_hz must be positive and finite")


def _h5py() -> Any:
    try:
        import h5py  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("MimicGen HDF5 import requires h5py: pip install h5py") from exc
    return h5py


def list_demos(path: str | Path) -> list[str]:
    """List source episode IDs without loading image or rollout arrays."""
    with _h5py().File(path, "r") as file:
        if "data" not in file:
            raise ValueError("invalid robomimic HDF5: missing data group")
        return sorted(str(name) for name in file["data"] if str(name).startswith("demo_"))


def _matrix(group: Any, key: str, rows: int | None = None) -> Any:
    """Validate a numeric two-dimensional HDF5 array without changing semantics."""
    import numpy as np

    if key not in group:
        raise ValueError("MimicGen HDF5 missing required array: " + key)
    values = np.asarray(group[key])
    if values.ndim != 2 or values.shape[0] == 0:
        raise ValueError(key + " must be a nonempty matrix")
    if rows is not None and values.shape[0] != rows:
        raise ValueError(key + " episode length does not match actions")
    if not np.issubdtype(values.dtype, np.number):
        raise ValueError(key + " must contain numeric values")
    if not np.isfinite(values).all():
        raise ValueError(key + " contains non-finite values")
    return values


def read_mimicgen_episode(selection: MimicGenSelection, *, max_steps: int = 2000) -> Episode:
    """Import a recorded demonstration with lossless source action channel values.

    The caller must provide the actual control frequency; it is not safe to
    infer timing from a robot family or silently assume 20Hz.
    """
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    with _h5py().File(selection.path, "r") as file:
        group_path = "data/" + selection.demo_id
        if group_path not in file:
            raise ValueError("MimicGen episode not present: " + group_path)
        group = file[group_path]
        if "obs" not in group:
            raise ValueError("MimicGen episode missing obs group")
        obs = group["obs"]
        actions = _matrix(group, "actions")
        joints = _matrix(obs, "robot0_joint_pos", actions.shape[0])
        velocities = (
            _matrix(obs, "robot0_joint_vel", actions.shape[0])
            if "robot0_joint_vel" in obs
            else None
        )
        eef = _matrix(obs, "robot0_eef_pos", actions.shape[0]) if "robot0_eef_pos" in obs else None
        steps: list[EpisodeStep] = []
        count = min(max_steps, actions.shape[0])
        for i in range(count):
            t = i / selection.control_hz
            joint_positions = {
                "joint_" + str(j): float(joints[i, j]) for j in range(joints.shape[1])
            }
            joint_velocities = (
                {"joint_" + str(j): float(velocities[i, j]) for j in range(velocities.shape[1])}
                if velocities is not None
                else {}
            )
            state = {
                "source_action_" + str(j): float(actions[i, j]) for j in range(actions.shape[1])
            }
            if eef is not None:
                state.update(
                    {"eef_position_" + str(j): float(eef[i, j]) for j in range(eef.shape[1])}
                )
            steps.append(
                EpisodeStep(
                    observation=Observation(
                        timestamp_s=t,
                        joint_position=joint_positions,
                        joint_velocity=joint_velocities,
                        state=state,
                    ),
                    action=Action(timestamp_s=t, joint_commands={}),
                    terminal=i == count - 1,
                )
            )
        return Episode(
            episode_id=selection.embodiment_id + "-" + selection.demo_id,
            embodiment_id=selection.embodiment_id,
            task_id=selection.task_id,
            source="mimicgen-robomimic-hdf5-recorded-demonstration",
            steps=steps,
            metadata={
                "dataset": "amandlek/mimicgen_datasets",
                "dataset_license": "CC-BY-4.0",
                "source_filename": selection.path.name,
                "demo_id": selection.demo_id,
                "controller_frequency_hz": str(selection.control_hz),
                "action_semantics": "source-controller-native; not joint commands",
                "policy_attached": "false",
                "steps_loaded": str(count),
                "truncated": str(count < actions.shape[0]).lower(),
            },
        )
