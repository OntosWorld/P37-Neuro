"""Domain-randomization contracts used by simulated training."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True, slots=True)
class DomainRandomization:
    """Ranges applied to one simulated rollout."""

    mass_scale: tuple[float, float] = (0.8, 1.2)
    friction_scale: tuple[float, float] = (0.6, 1.4)
    motor_strength_scale: tuple[float, float] = (0.85, 1.15)
    sensor_noise_std: tuple[float, float] = (0.0, 0.02)
    latency_s: tuple[float, float] = (0.0, 0.03)

    def sample(self, seed: int) -> dict[str, float]:
        rng = Random(seed)
        return {
            "mass_scale": rng.uniform(*self.mass_scale),
            "friction_scale": rng.uniform(*self.friction_scale),
            "motor_strength_scale": rng.uniform(*self.motor_strength_scale),
            "sensor_noise_std": rng.uniform(*self.sensor_noise_std),
            "latency_s": rng.uniform(*self.latency_s),
        }
