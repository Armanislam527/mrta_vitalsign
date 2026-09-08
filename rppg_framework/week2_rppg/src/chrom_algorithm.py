"""Task 3 — CHROM rPPG pulse extraction algorithm.

Reference formula described in the build guide.
"""

from __future__ import annotations

import numpy as np


def compute_chrom(r_signal: np.ndarray,
                  g_signal: np.ndarray,
                  b_signal: np.ndarray) -> np.ndarray:
    """Compute CHROM pulse signal from RGB triplets.

    Steps:
      1. Normalize individual channels by their temporal mean.
      2. Form Xs and Ys.
      3. Estimate alpha = std(Xs)/std(Ys).
      4. pulse_signal = Xs - alpha * Ys.
    """
    r = np.asarray(r_signal, dtype=float)
    g = np.asarray(g_signal, dtype=float)
    b = np.asarray(b_signal, dtype=float)

    if not (r.shape == g.shape == b.shape):
        raise ValueError("R, G, and B signals must have identical lengths.")

    if r.size == 0:
        return np.array([], dtype=float)

    Rn = r / np.mean(r)
    Gn = g / np.mean(g)
    Bn = b / np.mean(b)

    Xs = 3.0 * Rn - 2.0 * Gn
    Ys = 1.5 * Rn + Gn - 1.5 * Bn

    alpha = np.std(Xs) / np.std(Ys)
    pulse_signal = Xs - alpha * Ys
    pulse_signal = pulse_signal - np.mean(pulse_signal)
    return pulse_signal.astype(float)
