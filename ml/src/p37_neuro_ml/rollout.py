"""Canonical rollout collection from a P37 policy and simulator backend."""

from __future__ import annotations

from collections.abc import Callable

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.simulation.base import SimulatorAdapter
from p37_neuro_ml.inference import InferenceSession

RewardFunction = Callable[[Observation, Action, Observation], float]
TerminalFunction = Callable[[Observation], bool]


def collect_episode(
    simulator: SimulatorAdapter,
    session: InferenceSession,
    *,
    episode_id: str,
    task_id: str,
    seed: int,
    max_steps: int,
    reward: RewardFunction,
    terminal: TerminalFunction | None = None,
) -> Episode:
    """Run a deterministic evaluation/collection episode through canonical contracts."""
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if simulator.embodiment.embodiment_id != session.embodiment.embodiment_id:
        raise ValueError("simulator and inference session embodiments differ")

    session.reset()
    observation = simulator.reset(seed)
    trajectory: list[EpisodeStep] = []
    for _ in range(max_steps):
        action = session.act(observation)
        next_observation = simulator.step(action)
        score = reward(observation, action, next_observation)
        done = terminal(next_observation) if terminal is not None else False
        trajectory.append(
            EpisodeStep(
                observation=observation,
                action=action,
                reward=score,
                terminal=done,
            )
        )
        observation = next_observation
        if done:
            break

    return Episode(
        episode_id=episode_id,
        embodiment_id=session.embodiment.embodiment_id,
        task_id=task_id,
        steps=tuple(trajectory),
        source="p37-policy-rollout",
        metadata={"seed": str(seed)},
    )
