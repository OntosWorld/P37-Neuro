"""Attach the real recurrent P37 G1 ONNX checkpoint to native MuJoCo.

The adapter makes the checkpoint's explicit observation and recurrent-memory
contract consumable by mjswan's browser ONNX Runtime. It does not change
weights, fabricate motor actions, or qualify locomotion.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import mujoco
import onnx
import torch
from mjlab.envs.mdp import observations as obs_fns
from mjlab.managers.scene_entity_config import SceneEntityCfg
from mjswan.envs.mdp.actions import JointPositionActionCfg
from mjswan.managers.observation_manager import ObservationGroupCfg, ObservationTermCfg
from mjswan.mjlab.env import build_single_entity_trace_env
from onnx import TensorProto, helper

EXPECTED_ONNX_SHA256 = "894d33ac78e0d654b00cf85319b5dcf4accf1d0c93b1264b4e40f105670905e3"
EXPECTED_CHECKPOINT_SHA256 = "b3619374aa0f9b44a2fc80fa6005589abdfdac8e84cdcadbd8486df4f2285c95"
CONTROL_DT = 0.02


_ROBOT = SceneEntityCfg(name="robot")


def _gravity_z(env, *, asset_cfg: SceneEntityCfg = _ROBOT):
    """Training input is the *last component* of projected local gravity."""
    robot = env.scene[asset_cfg.name]
    return robot.data.projected_gravity_b[:, 2:3]


def _forward_command(env, *, asset_cfg: SceneEntityCfg = _ROBOT):
    """The experimental G1 checkpoint was trained with a fixed 0.3 m/s goal."""
    robot = env.scene[asset_cfg.name]
    return torch.ones_like(robot.data.joint_pos[:, :1]) * 0.3


def _dims(value):
    return [dim.dim_value for dim in value.type.tensor_type.shape.dim]


def make_mjswan_recurrent_actor(original: onnx.ModelProto) -> onnx.ModelProto:
    """Wrap [1,29,2], [1,1,8], [1,1,32] inputs as actor [1,66] + carry.

    All learned nodes/initializers remain unchanged. No zeroed or frozen
    recurrent memory: mjswan feeds and retains the adapt_hx carry each step.
    """
    source_inputs = {item.name: item for item in original.graph.input}
    for name in ("joint_state", "task_context", "memory"):
        if name not in source_inputs:
            raise ValueError("P37 ONNX input missing: " + name)
    if _dims(source_inputs["joint_state"]) != [1, 29, 2]:
        raise ValueError("P37 joint state must be [1,29,2]")
    if _dims(source_inputs["task_context"]) != [1, 1, 8]:
        raise ValueError("P37 task context must be [1,1,8]")
    memory_dims = _dims(source_inputs["memory"])
    if memory_dims != [1, 1, 32]:
        raise ValueError("Unexpected P37 recurrent memory dimensions: " + str(memory_dims))
    if [item.name for item in original.graph.output] != ["action", "next_memory"]:
        raise ValueError("P37 ONNX output names do not match recurrent contract")
    model = onnx.ModelProto()
    model.CopyFrom(original)
    graph = model.graph
    del graph.input[:]
    graph.input.extend([
        helper.make_tensor_value_info("actor", TensorProto.FLOAT, [1, 66]),
        helper.make_tensor_value_info("adapt_hx", TensorProto.FLOAT, [1, 1, 32]),
    ])
    # Torch exported joint_state was position residual and velocity
    # interleaved per joint. Reconstruct that original ordering exactly.
    adapter = [
        helper.make_node(
            "Split", ["actor", "p37_obs_split"],
            ["p37_q", "p37_dq", "p37_lin", "p37_ang", "p37_grav", "p37_goal"],
            axis=1, name="p37_obs_unpack",
        ),
        helper.make_node("Unsqueeze", ["p37_q", "p37_axis2"], ["p37_q3"]),
        helper.make_node("Unsqueeze", ["p37_dq", "p37_axis2"], ["p37_dq3"]),
        helper.make_node("Concat", ["p37_q3", "p37_dq3"], ["joint_state"], axis=2),
        helper.make_node("Concat", ["p37_lin", "p37_ang", "p37_grav", "p37_goal"],
                         ["p37_task_flat"], axis=1),
        helper.make_node("Unsqueeze", ["p37_task_flat", "p37_axis1"], ["task_context"]),
        helper.make_node("Identity", ["adapt_hx"], ["memory"]),
    ]
    graph.initializer.extend([
        helper.make_tensor("p37_axis1", TensorProto.INT64, [1], [1]),
        helper.make_tensor("p37_axis2", TensorProto.INT64, [1], [2]),
        helper.make_tensor("p37_obs_split", TensorProto.INT64, [6], [29, 29, 3, 3, 1, 1]),
    ])
    nodes = list(graph.node)
    del graph.node[:]
    graph.node.extend(adapter + nodes)
    onnx.checker.check_model(model)
    return model


def attach_g1_policy(scene, model_path: Path, artifact: Path):
    """Register real motor control on the full manufacturer-derived G1 body."""
    contract_file = artifact / "g1-p37-onnx" / "policy-contract.json"
    onnx_file = artifact / "g1-p37-onnx" / "p37-g1-experimental.onnx"
    data = json.loads(contract_file.read_text(encoding="utf-8"))
    if data["qualified_for_walking"] is not False:
        raise ValueError("Experimental G1 checkpoint must not claim walking qualification")
    if data["onnx_sha256"] != EXPECTED_ONNX_SHA256:
        raise ValueError("Unexpected policy contract SHA")
    if data["p37_checkpoint_sha256"] != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError("Unexpected checkpoint identity")
    if hashlib.sha256(onnx_file.read_bytes()).hexdigest() != EXPECTED_ONNX_SHA256:
        raise ValueError("ONNX weights do not match reviewed experimental artifact")
    if data["control_dt_s"] != CONTROL_DT or data["action_scale_rad"] != 0.35:
        raise ValueError("Policy control rate or target scale differs from training")
    model = mujoco.MjModel.from_xml_path(str(model_path))
    actuator_joint_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, int(model.actuator_trnid[i, 0]))
        for i in range(model.nu)
    ]
    if actuator_joint_names != data["policy_joint_names"]:
        raise ValueError("Native G1 actuators do not match checkpoint joint order")
    if len(actuator_joint_names) != 29:
        raise ValueError("P37 G1 policy must drive 29 actuators")
    scene.set_trace_env(build_single_entity_trace_env(
        lambda: mujoco.MjSpec.from_file(str(model_path)),
    ))
    actor = make_mjswan_recurrent_actor(onnx.load(str(onnx_file)))
    # 29 joint-position residuals, 29 joint velocities, six root velocities,
    # body-local gravity Z and fixed forward goal = 66 features. The recurrent
    # carry is distinct and maintained by the browser engine.
    observations = ObservationGroupCfg(terms={
        "joint_position_residual": ObservationTermCfg(func=obs_fns.joint_pos_rel),
        "joint_velocity": ObservationTermCfg(func=obs_fns.joint_vel_rel),
        "base_linear_velocity": ObservationTermCfg(func=obs_fns.base_lin_vel),
        "base_angular_velocity": ObservationTermCfg(func=obs_fns.base_ang_vel),
        "gravity_z": ObservationTermCfg(func=_gravity_z),
        "forward_goal": ObservationTermCfg(func=_forward_command),
    })
    result = scene.add_policy(
        name="P37 G1 experimental recurrent PPO",
        policy=actor,
        default=True,
        policy_joint_names=actuator_joint_names,
        default_joint_pos=data["default_joint_pos_rad"],
        in_keys=["actor", "adapt_hx"],
        out_keys=["action", ["next", "adapt_hx"]],
        observations=observations,
        actions={"joint_pos": JointPositionActionCfg(
            actuator_names=(".*",),
            scale=0.35,
            use_default_offset=True,
            stiffness=45.0,
            damping=2.0,
        )},
        extras={
            "experimental": True,
            "qualified_for_walking": False,
            "qualified_for_recovery": False,
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "policy_control_dt_s": CONTROL_DT,
        },
    )
    return result
