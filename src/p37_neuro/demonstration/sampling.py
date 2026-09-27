"""Deterministic temporal sampling for demonstration video."""

from __future__ import annotations


def uniform_timestamps(start_s: float, end_s: float, frames: int) -> tuple[float, ...]:
    if frames <= 0:
        raise ValueError("frames must be positive")
    if end_s <= start_s:
        raise ValueError("end_s must exceed start_s")
    if frames == 1:
        return ((start_s + end_s) / 2.0,)
    step = (end_s - start_s) / (frames - 1)
    return tuple(start_s + index * step for index in range(frames))
