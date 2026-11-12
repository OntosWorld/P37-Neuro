"""Strict adapter for the published P37 experimental ONNX checkpoint.

This is an *experimental*, unqualified recurrent controller. Model bytes come
from a pinned GitHub Actions artifact and are verified before build. Inference
runs in the user's browser through mjswan/ONNX Runtime Web with actual MuJoCo
joint observations and physical actuator targets.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import mujoco
import numpy as np
import onnx
from mjswan.envs.mdp.actions import JointPositionActionCfg
from mjswan.envs.mdp.observations import ObservationBinding
from mjswan.managers.observation_manager import ObservationGroupCfg, ObservationTermCfg
from onnx import TensorProto, helper, numpy_helper

EXPECTED_ONNX_SHA256 = "894d33ac78e0d654b00cf85319b5dcf4accf1d0c93b1264b4e40f105670905e3"
EXPECTED_CHECKPOINT_SHA256 = "b3619374aa0f9b44a2fc80fa6005589abdfdac8e84cdcadbd8486df4f2285c95"
OBS_SOURCE = Path(__file__).parent / "p37_browser_observations.ts"
VALID_BODIES = {"unitree_g1", "unitree_go2"}


def _joint_names(model: mujoco.MjModel, contract: dict, robot: str) -> tuple[str, ...]:
    """Never silently reorder, pad or drop the network's action dimensions."""
    if robot == "unitree_g1":
        names = tuple(contract["policy_joint_names"])
    else:
        names = tuple(
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, int(model.actuator_trnid[i, 0]))
            for i in range(model.nu)
        )
    if len(names) != model.nu or len(set(names)) != len(names):
        raise ValueError(f"{robot}: expected one distinct joint per actuator")
    model_names = {
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in range(model.njnt)
    }
    if any(name not in model_names for name in names):
        raise ValueError(f"{robot}: policy joint name absent from MuJoCo model")
    if len(contract["default_joint_pos_rad"]) != 29:
        raise ValueError("Published G1 default pose contract has changed")
    return names


def _default_pose(model: mujoco.MjModel, names: tuple[str, ...], contract: dict, robot: str):
    if robot == "unitree_g1":
        return [float(v) for v in contract["default_joint_pos_rad"]]
    pose = model.key_qpos[0] if model.nkey else model.qpos0
    return [
        float(pose[model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]])
        for name in names
    ]


def _flatten_joint_input(graph: onnx.GraphProto, count: int) -> None:
    """mjswan observation slots are [1, 2*J]; original P37 expects [1,J,2]."""
    original = graph.input[0].name
    renamed = original + "_flat_mjswan"
    graph.input[0].name = renamed
    graph.input[0].type.tensor_type.shape.CopyFrom(
        helper.make_tensor_value_info(
            renamed, TensorProto.FLOAT, [1, 2 * count]
        ).type.tensor_type.shape
    )
    dims_name = "p37_joint_reshape_dims"
    graph.initializer.append(
        numpy_helper.from_array(np.asarray([1, count, 2], dtype=np.int64), name=dims_name)
    )
    graph.node.insert(
        0,
        helper.make_node(
            "Reshape", [renamed, dims_name], [original], name="P37JointObservationsReshape"
        ),
    )


def verified_policy(onnx_path: Path, contract_path: Path, robot: str, model: mujoco.MjModel):
    if robot not in VALID_BODIES:
        raise ValueError(f"Policy not supported for {robot}")
    contents = onnx_path.read_bytes()
    if hashlib.sha256(contents).hexdigest() != EXPECTED_ONNX_SHA256:
        raise ValueError("P37 ONNX bytes do not match the verified artifact")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if (
        contract.get("onnx_sha256") != EXPECTED_ONNX_SHA256
        or contract.get("p37_checkpoint_sha256") != EXPECTED_CHECKPOINT_SHA256
        or contract.get("qualified_for_walking") is not False
        or contract.get("control_dt_s") != 0.02
        or contract.get("action_scale_rad") != 0.35
    ):
        raise ValueError("Unrecognized experimental policy contract")
    if not OBS_SOURCE.is_file():
        raise FileNotFoundError("P37 native joint observation adapter missing")
    joint_names = _joint_names(model, contract, robot)
    pose = _default_pose(model, joint_names, contract, robot)
    network = onnx.load_from_string(contents)
    if len(network.graph.input) != 3 or len(network.graph.output) != 2:
        raise ValueError("Expected P37 recurrent ONNX: joint, task, memory -> action, next_memory")
    _flatten_joint_input(network.graph, len(joint_names))
    onnx.checker.check_model(network)
    source = str(OBS_SOURCE.resolve())
    observations = {
        "p37_joints": ObservationGroupCfg(
            terms={
                "joint_state": ObservationTermCfg(
                    func=ObservationBinding(
                        ts_name="P37JointResidual",
                        ts_src=source,
                        defaults={"count": len(joint_names), "default_pose": pose},
                    )
                ),
            }
        ),
        "p37_task": ObservationGroupCfg(
            terms={
                "task_context": ObservationTermCfg(
                    func=ObservationBinding(
                        ts_name="P37TaskContext",
                        ts_src=source,
                        defaults={"desired_velocity_x": 0.3},
                    )
                ),
            }
        ),
    }
    actions = {
        "p37_joint_target": JointPositionActionCfg(
            entity_name="",
            actuator_names=tuple(joint_names),
            scale=0.35,
            use_default_offset=True,
            stiffness=35.0,
            damping=1.5,
        )
    }
    return {
        "name": "P37 Experimental Recurrent PPO",
        "policy": network,
        "policy_joint_names": list(joint_names),
        "default_joint_pos": pose,
        "observations": observations,
        "actions": actions,
        "commands": {},
        "events": {},
        "terminations": {},
        "in_keys": ["p37_joints", "p37_task", "adapt_hx"],
        "out_keys": ["action", ["next", "adapt_hx"]],
        "metadata": {
            "status": "experimental_unqualified",
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "onnx_sha256": EXPECTED_ONNX_SHA256,
            "trained_on": "unitree_g1",
            "robot": robot,
            "qualified_for_walking": False,
            "qualified_for_task_transfer": False,
            "controller": "real_onnx_browser_inference",
        },
        "default": True,
    }
