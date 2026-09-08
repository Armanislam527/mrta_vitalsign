import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pos_algorithm import compute_pos


def test_compute_pos_returns_same_length_signal():
    fps = 30.0
    r = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], dtype=float)
    g = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=float)
    b = np.array([3.0, 4.0, 5.0, 6.0, 7.0, 8.0], dtype=float)

    pulse = compute_pos(r, g, b, fps)

    assert pulse.shape == r.shape
    assert np.isfinite(pulse).all()
