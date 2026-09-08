import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from rr_estimator import estimate_rr_bpm


def test_estimate_rr_bpm_returns_valid_value():
    fps = 30.0
    signal_length = int(10 * fps)
    t = np.arange(signal_length) / fps
    pulse = np.sin(2 * np.pi * 0.25 * t)

    rr = estimate_rr_bpm(pulse, fps)

    assert np.isfinite(rr)
    assert rr > 0
