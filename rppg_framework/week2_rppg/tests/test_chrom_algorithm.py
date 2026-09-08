import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from chrom_algorithm import compute_chrom


def test_compute_chrom_returns_same_length_signal():
    r = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
    g = np.array([2.0, 3.0, 4.0, 5.0], dtype=float)
    b = np.array([3.0, 4.0, 5.0, 6.0], dtype=float)

    pulse = compute_chrom(r, g, b)

    assert pulse.shape == r.shape
    assert np.isfinite(pulse).all()
