"""Automatic quality triage for collected robot episodes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from math import isfinite

from p37_neuro.data.schema import Episode


class QualityDecision(StrEnum):
    ACCEPT = "accept"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class EpisodeQuality:
    score: float
    decision: QualityDecision
    reasons: tuple[str, ...]


def score_episode(episode: Episode) -> EpisodeQuality:
    """Conservative structural score before an episode enters a training dataset."""
    score = 1.0
    reasons: list[str] = []
    timestamps = [step.observation.timestamp_s for step in episode.steps]
    if any(later <= earlier for earlier, later in pairwise(timestamps)):
        score -= 0.45
        reasons.append("non_monotonic_time")
    if any(step.reward is not None and not isfinite(step.reward) for step in episode.steps):
        score -= 0.6
        reasons.append("non_finite_reward")
    intervention_rate = sum(step.intervention for step in episode.steps) / len(episode.steps)
    if intervention_rate > 0.2:
        score -= min(0.4, intervention_rate)
        reasons.append("high_intervention_rate")
    failures = sum(step.failure_code is not None for step in episode.steps)
    if failures:
        score -= min(0.3, failures / len(episode.steps) * 0.3)
        reasons.append("contains_failures")
    if not episode.steps[-1].terminal:
        score -= 0.1
        reasons.append("no_terminal_marker")

    score = max(0.0, min(1.0, score))
    if score < 0.4 or "non_finite_reward" in reasons:
        decision = QualityDecision.REJECT
    elif score < 0.85 or reasons:
        decision = QualityDecision.REVIEW
    else:
        decision = QualityDecision.ACCEPT
    return EpisodeQuality(score=score, decision=decision, reasons=tuple(reasons))
