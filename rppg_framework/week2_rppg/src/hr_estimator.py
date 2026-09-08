"""Task 4 — Heart-rate estimation from rPPG pulse signal.

This module wraps the required filter + FFT peak approach described in
Week 2. It also exposes a rolling update helper for repeated HR outputs.
"""

from __future__ import annotations

import numpy as np
from scipy import signal


DEFAULT_HR_BAND = (0.7, 4.0)


def bandpass_filter(signal_values: np.ndarray, low_hz: float, high_hz: float,
                     sample_rate: float, order: int = 4) -> np.ndarray:
    """Apply Butterworth band-pass filtering using scipy.signal.butter + filtfilt."""
    if signal_values.size < 3:
        return np.asarray(signal_values, dtype=float)

    nyquist = 0.5 * sample_rate
    low = low_hz / nyquist
    high = high_hz / nyquist
    b, a = signal.butter(order, [low, high], btype='bandpass')
    return signal.filtfilt(b, a, np.asarray(signal_values, dtype=float))


def estimate_hr_bpm(pulse_signal: np.ndarray, fps: float,
                     low_hz: float = 0.7, high_hz: float = 4.0) -> float:
    """Estimate heart rate BPM by FFT peak finding in the HR band.

    The implementation uses a simple spectral peak finder over the
    frequency range described by the build guide.
    """
    pulse = np.asarray(pulse_signal, dtype=float)
    if pulse.size < 2:
        return 0.0

    filt = bandpass_filter(pulse, low_hz, high_hz, fps)
    freqs = np.fft.rfftfreq(len(filt), d=1.0 / fps)
    spectrum = np.abs(np.fft.rfft(filt))

    mask = (freqs >= low_hz) & (freqs <= high_hz)
    if not np.any(mask):
        return 0.0

    # Peak frequency in allowed band
    candidate_freqs = freqs[mask]
    candidate_spec = spectrum[mask]
    idx = int(np.argmax(candidate_spec))
    peak_hz = float(candidate_freqs[idx])
    return peak_hz * 60.0


def estimate_hr_series(pulse_signal: np.ndarray, fps: float,
                       window_seconds: int = 10,
                       update_seconds: int = 5) -> list[float]:
    """Return updating HR estimates using overlapping windows.

    This is a simple serial implementation for a continuous stream:
    every update_seconds, compute the estimate using the most recent
    window_seconds of data.
    """
    pulse = np.asarray(pulse_signal, dtype=float)
    n = len(pulse)
    if n == 0:
        return []

    window_frames = int(window_seconds * fps)
    update_frames = int(update_seconds * fps)
    estimates = []

    for start in range(0, n - window_frames + 1, update_frames):
        end = min(start + window_frames, n)
        window = pulse[start:end]
        if len(window) < 2:
            continue
        estimates.append(estimate_hr_bpm(window, fps))

    return estimates
