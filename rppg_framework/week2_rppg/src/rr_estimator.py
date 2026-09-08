"""Task 4 extension — Respiratory rate estimation.

RR is estimated by the same FFT-peaking strategy but in the low
respiration rate band following the build guide.
"""

from __future__ import annotations

import numpy as np
from scipy import signal


def bandpass_filter_rr(signal_values: np.ndarray, sample_rate: float,
                       low_hz: float = 0.15, high_hz: float = 0.5,
                       order: int = 4) -> np.ndarray:
    """Bandpass filter in the RR band using the same style as HR estimator."""
    if signal_values.size < 3:
        return np.asarray(signal_values, dtype=float)

    nyquist = 0.5 * sample_rate
    low = low_hz / nyquist
    high = high_hz / nyquist
    b, a = signal.butter(order, [low, high], btype='bandpass')
    return signal.filtfilt(b, a, np.asarray(signal_values, dtype=float))


def estimate_rr_bpm(pulse_signal: np.ndarray, fps: float,
                    low_hz: float = 0.15, high_hz: float = 0.5) -> float:
    """Estimate passive respiratory rate BPM from pulse modulation band.

    The guide mentions the pulse signal itself carries respiratory modulation
    information. We estimate the strongest periodic component in the RR range.
    """
    pulse = np.asarray(pulse_signal, dtype=float)
    if pulse.size < 2:
        return 0.0

    filt = bandpass_filter_rr(pulse, fps, low_hz, high_hz)
    freqs = np.fft.rfftfreq(len(filt), d=1.0 / fps)
    spectrum = np.abs(np.fft.rfft(filt))

    mask = (freqs >= low_hz) & (freqs <= high_hz)
    if not np.any(mask):
        return 0.0

    candidate_freqs = freqs[mask]
    candidate_spec = spectrum[mask]
    idx = int(np.argmax(candidate_spec))
    peak_hz = float(candidate_freqs[idx])
    return peak_hz * 60.0
