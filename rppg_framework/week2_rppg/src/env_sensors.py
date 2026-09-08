"""Task 6 — Environmental sensor reading utilities.

This module provides small serial-friendly helper objects and sensor
reading conversions for temperature and microphone-derived noise levels.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class SensorReading:
    """Simple sensor reading container with a value and source timestamp."""
    value: float
    timestamp: float | None = None


def read_temperature(celsius: float) -> SensorReading:
    """Return a temperature reading in Celsius as a stable object."""
    return SensorReading(value=float(celsius), timestamp=None)


def read_noise_level(noise_db: float) -> SensorReading:
    """Return a microphone-derived approximate dB-level reading as a stable object."""
    return SensorReading(value=float(noise_db), timestamp=None)


def estimate_noise_db(samples: np.ndarray) -> float:
    """Estimate an approximate noise level in dB using RMS over a sample window."""
    if samples is None or len(samples) == 0:
        return 0.0
    samples = np.asarray(samples, dtype=float)
    rms = np.sqrt(np.mean(np.square(samples)))
    return float(20.0 * np.log10(max(rms, 1e-9)) + 60.0)
