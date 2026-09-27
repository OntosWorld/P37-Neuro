"""Isaac Lab execution integration.

This module intentionally shells out to Isaac Lab's maintained CLI rather than
vendoring its training implementation. P37 experiment metadata remains separate
from Isaac's task/agent configuration.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class IsaacLabUnavailableError(RuntimeError):
    """Raised when an Isaac Lab installation cannot be located."""


@dataclass(frozen=True, slots=True)
class IsaacLabRun:
    """Reproducible Isaac Lab RL launch specification."""

    task: str
    run_name: str
    num_envs: int = 4096
    seed: int = 0
    rl_library: str = "rsl_rl"
    headless: bool = True
    checkpoint: Path | None = None
    external_callback: str | None = (
        "p37_neuro_sim.isaac_tasks.registration.register_from_isaac_cli"
    )
    extra_args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task.strip() or not self.run_name.strip():
            raise ValueError("task and run_name cannot be empty")
        if self.num_envs <= 0 or self.seed < 0:
            raise ValueError("invalid num_envs or seed")

    def command(self, executable: str = "isaaclab") -> tuple[str, ...]:
        command = [
            executable,
            "train",
            "--rl_library",
            self.rl_library,
            "--task",
            self.task,
            "--num_envs",
            str(self.num_envs),
            "--seed",
            str(self.seed),
            "--run_name",
            self.run_name,
        ]
        if self.headless:
            command.append("--headless")
        if self.external_callback is not None:
            command.extend(("--external_callback", self.external_callback))
        if self.checkpoint is not None:
            command.extend(("--checkpoint", str(self.checkpoint)))
        command.extend(self.extra_args)
        return tuple(command)


class IsaacLabRunner:
    """Launch Isaac Lab while preserving an inspectable command line."""

    def __init__(self, executable: str = "isaaclab") -> None:
        self.executable = executable

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def run(self, spec: IsaacLabRun, *, cwd: str | Path | None = None) -> None:
        if not self.available():
            raise IsaacLabUnavailableError(f"Isaac Lab executable not found: {self.executable}")
        subprocess.run(
            spec.command(self.executable),
            cwd=None if cwd is None else Path(cwd),
            check=True,
        )
