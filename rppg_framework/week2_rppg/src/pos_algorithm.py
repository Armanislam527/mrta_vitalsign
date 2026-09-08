"""Task 3 — POS rPPG pulse extraction algorithm.

Implements sliding-window temporal normalization and overlap-add as
outlined in the Week 2 build guide.
"""

from __future__ import annotations

import numpy as np


def compute_pos(r_signal: np.ndarray,
                g_signal: np.ndarray,
                b_signal: np.ndarray,
                fps: float) -> np.ndarray:
    """Return a continuous pulse signal using the POS algorithm.

    This implementation follows the reference process:
      1. normalize R/G/B by channel mean
      2. compute S1 and S2
      3. estimate alpha = std(S1)/std(S2)
      4. h_window = S1 + alpha*S2
      5. de-mean per window
      6. overlap-add windows into a signal of the original length
    """
    r = np.asarray(r_signal, dtype=float)
    g = np.asarray(g_signal, dtype=float)
    b = np.asarray(b_signal, dtype=float)

    if not (r.shape == g.shape == b.shape):
        raise ValueError("R, G, and B signals must have identical lengths.")

    n = len(r)
    if n == 0:
        return np.array([], dtype=float)

    # sliding window length per guide: round(1.6 * fps)
    window_length = max(3, int(round(1.6 * fps)))
    if window_length > n:
        window_length = n

    out = np.zeros(n, dtype=float)
    counts = np.zeros(n, dtype=float)

    # Slide by one frame per step, as requested in the specification.
    for start in range(0, n - window_length + 1):
        win_r = r[start:start + window_length]
        win_g = g[start:start + window_length]
        win_b = b[start:start + window_length]

        # stack as shape 3 x L
        C = np.stack([win_r, win_g, win_b], axis=0)
        Cn = C / np.mean(C, axis=1, keepdims=True)

        S1 = Cn[1] - Cn[2]
        S2 = -2.0 * Cn[0] + Cn[1] + Cn[2]

        denom_std = np.std(S2)
        alpha = np.std(S1) / denom_std if denom_std != 0 else 0.0
        h_window = S1 + alpha * S2
        h_window = h_window - np.mean(h_window)

        out[start:start + window_length] += h_window
        counts[start:start + window_length] += 1.0

    # Normalize overlap-add by how many times each sample received contribution.
    pulse = np.zeros(n, dtype=float)
    nonzero = counts > 0
    pulse[nonzero] = out[nonzero] / counts[nonzero]

    # Final de-mean and scaling to keep the algorithm stable.
    pulse = pulse - np.mean(pulse)
    return pulse.astype(float)
