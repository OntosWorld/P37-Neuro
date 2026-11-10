"""Generate *measured MuJoCo* reach trials for two different two-link arms.

This is an engineering baseline using analytic IK and MuJoCo position servos.
No P37 trained policy is loaded. Execution is T2 simulated physics evidence only.

Run (with MuJoCo installed):
    uv run --project sim python scripts/mujoco_cross_body_demo.py \
        --output docs/interactive-lab/experiments/mujoco-reach-baseline.json
"""

from __future__ import annotations

import argparse
import hashlib
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.data.trace_export import (
    TraceProvenance,
    export_comparison,
    write_comparison,
)


@dataclass(frozen=True)
class RobotConfig:
    name: str
    first_link_m: float
    second_link_m: float


CONFIGS = (
    RobotConfig("compact-two-link", 0.45, 0.35),
    RobotConfig("extended-two-link", 0.65, 0.55),
)
TASK_ID = "reach-fixed-target-v1"
TARGET_X_M = 0.65
TARGET_Z_M = 0.75
BASE_Z_M = 0.4
DURATION_S = 3.0
DT_S = 0.005
SAMPLE_EVERY = 10
SUCCESS_ERROR_M = 0.045


def robot_xml(config: RobotConfig) -> str:
    """Generate a small, deterministic, *physical* MuJoCo arm, not a CAD replica."""
    a, b = config.first_link_m, config.second_link_m
    return f"""<mujoco model="{config.name}">
  <compiler angle="radian"/>
  <option timestep="{DT_S}" gravity="0 0 -9.81" integrator="implicitfast"/>
  <worldbody>
    <geom type="plane" size="4 4 .1" rgba=".09 .13 .16 1"/>
    <body name="root" pos="0 0 {BASE_Z_M}">
      <joint name="shoulder" type="hinge" axis="0 1 0" range="-2.7 2.7"
             limited="true" damping="0.25"/>
      <geom name="upper" type="capsule" fromto="0 0 0 {a} 0 0" size=".035" mass="1.2"/>
      <body name="forearm" pos="{a} 0 0">
        <joint name="elbow" type="hinge" axis="0 1 0" range="-2.7 2.7"
               limited="true" damping="0.18"/>
        <geom name="lower" type="capsule" fromto="0 0 0 {b} 0 0" size=".03" mass="0.85"/>
        <site name="tip" pos="{b} 0 0" size=".016" rgba=".7 1 .8 1"/>
      </body>
    </body>
    <site name="goal" pos="{TARGET_X_M} 0 {TARGET_Z_M}" size=".022" rgba="1 .8 .45 1"/>
  </worldbody>
  <actuator>
    <position name="shoulder_servo" joint="shoulder" kp="220" kv="30"/>
    <position name="elbow_servo" joint="elbow" kp="180" kv="24"/>
  </actuator>
</mujoco>"""


def ik_target(config: RobotConfig) -> tuple[float, float]:
    """Closed-form planar IK; MuJoCo uses positive Y rotation toward -Z."""
    x, z = TARGET_X_M, TARGET_Z_M - BASE_Z_M
    a, b = config.first_link_m, config.second_link_m
    cosine = (x * x + z * z - a * a - b * b) / (2 * a * b)
    if not -1 <= cosine <= 1:
        raise ValueError(f"target out of geometric reach for {config.name}")
    theta2 = math.acos(max(-1.0, min(1.0, cosine)))
    theta1 = math.atan2(z, x) - math.atan2(b * math.sin(theta2), a + b * math.cos(theta2))
    return -theta1, -theta2


def commit_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def record_run(
    config: RobotConfig,
    *,
    code_commit: str,
    seed: int,
) -> tuple[Episode, TraceProvenance]:
    try:
        import mujoco
    except ImportError as exc:
        raise RuntimeError("MuJoCo required: uv sync --project sim") from exc

    xml = robot_xml(config)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    model.opt.timestep = DT_S
    target = ik_target(config)
    tip_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "tip")
    assert tip_id >= 0

    # No learned P37 checkpoint is attached. MuJoCo position servos track analytic IK.
    total_steps = round(DURATION_S / DT_S)
    recorded: list[EpisodeStep] = []
    for i in range(total_steps + 1):
        mujoco.mj_forward(model, data)
        controls = list(target)
        if i % SAMPLE_EVERY == 0:
            tip = data.site_xpos[tip_id]
            error = math.hypot(float(tip[0]) - TARGET_X_M, float(tip[2]) - TARGET_Z_M)
            recorded.append(
                EpisodeStep(
                    observation=Observation(
                        timestamp_s=round(float(data.time), 8),
                        joint_position={
                            "shoulder": float(data.qpos[0]),
                            "elbow": float(data.qpos[1]),
                        },
                        joint_velocity={
                            "shoulder": float(data.qvel[0]),
                            "elbow": float(data.qvel[1]),
                        },
                        state={
                            "tip_x_m": float(tip[0]),
                            "tip_z_m": float(tip[2]),
                            "target_x_m": TARGET_X_M,
                            "target_z_m": TARGET_Z_M,
                            "position_error_m": error,
                        },
                    ),
                    action=Action(
                        timestamp_s=round(float(data.time), 8),
                        joint_commands={
                            "shoulder": controls[0],
                            "elbow": controls[1],
                        },
                    ),
                    terminal=i == total_steps,
                    failure_code=None,
                    intervention=False,
                )
            )
        if i != total_steps:
            data.ctrl[0], data.ctrl[1] = controls
            mujoco.mj_step(model, data)

    final_error = recorded[-1].observation.state["position_error_m"]
    outcome = "success" if final_error <= SUCCESS_ERROR_M else "failure"
    episode = Episode(
        episode_id=f"{TASK_ID}-{config.name}-seed-{seed}",
        embodiment_id=config.name,
        task_id=TASK_ID,
        source="mujoco-closed-loop-pd-ik-baseline",
        steps=recorded,
        metadata={"controller": "analytic-ik-mujoco-position-servo", "training": "none"},
    )
    provenance = TraceProvenance(
        checkpoint_sha256="",
        code_commit=code_commit,
        simulator="MuJoCo",
        simulator_version=mujoco.__version__,
        robot_description_sha256=hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        adapter_version="analytic-ik-position-servo-v2",
        seed=seed,
        training_membership="unknown",
        evidence_level="T2",
        policy_attached=False,
        evaluation_protocol="docs/interactive-lab/experiments/PROTOCOL.md",
        outcome=outcome,
    )
    return episode, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/interactive-lab/experiments/mujoco-reach-baseline.json"),
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    revision = commit_sha(root)
    trials = [record_run(c, code_commit=revision, seed=args.seed) for c in CONFIGS]
    artifact: dict[str, Any] = export_comparison(
        [trial[0] for trial in trials],
        [trial[1] for trial in trials],
        title="Two-body reaching: analytic IK + PD baseline (MuJoCo)",
    )
    write_comparison(args.output, artifact)
    for trial, config in zip(trials, CONFIGS, strict=True):
        print(
            config.name,
            trial[1].outcome,
            f"final error={trial[0].steps[-1].observation.state['position_error_m']:.4f} m",
            f"q={dict(trial[0].steps[-1].observation.joint_position)}",
            f"tip=({trial[0].steps[-1].observation.state['tip_x_m']:.3f}, "
            f"{trial[0].steps[-1].observation.state['tip_z_m']:.3f})",
        )
    print(f"Recorded {len(trials)} T2 physics episodes to {args.output}")


if __name__ == "__main__":
    main()
