import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from hr_estimator import estimate_hr_bpm, estimate_hr_series


def test_estimate_hr_bpm_from_sinusoidal_signal():
    fps = 30.0
    signal_length = int(10 * fps)
    t = np.arange(signal_length) / fps
    pulse = np.sin(2 * np.pi * 1.2 * t)

    hr = estimate_hr_bpm(pulse, fps)

    assert np.isfinite(hr)
    assert abs(hr - 72.0) < 5.0


def test_estimate_hr_series_returns_updates():
    fps = 30.0
    signal_length = int(10 * fps)
    t = np.arange(signal_length) / fps
    pulse = np.sin(2 * np.pi * 1.2 * t)

    hrs = estimate_hr_series(pulse, fps, window_seconds=5, update_seconds=5)

    assert isinstance(hrs, list)
    assert len(hrs) >= 1
    assert all(np.isfinite(h) for h in hrs)
