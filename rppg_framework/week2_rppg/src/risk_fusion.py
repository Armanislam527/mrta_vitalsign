"""Task 7 — Fused risk score function.

Implements the NEWS2-inspired risk fusion policy requested in the build guide.
"""

from __future__ import annotations


HR_POINTS = {
    'resting': None,
}


CLINICAL_POINT_TABLE = {
    'heart_rate_bpm': {
        'low': (61, 90),
        'mid': (51, 60, 91, 110),
        'high': (111, 130),
        'severe': (None, 50, 131, None),
    },
}


def heart_rate_points(hr_bpm: float) -> int:
    """Return the NEWS2-style clinical point contribution for HR."""
    if 61 <= hr_bpm <= 90:
        return 0
    if 51 <= hr_bpm <= 60 or 91 <= hr_bpm <= 110:
        return 1
    if 111 <= hr_bpm <= 130:
        return 2
    if hr_bpm <= 50 or hr_bpm >= 131:
        return 3
    return 0


def respiratory_rate_points(rr_bpm: float) -> int:
    """Return the NEWS2-style clinical point contribution for RR."""
    if 12 <= rr_bpm <= 20:
        return 0
    if 9 <= rr_bpm <= 11 or 21 <= rr_bpm <= 24:
        return 1
    if rr_bpm <= 8 or rr_bpm >= 25:
        return 3
    return 0


def temperature_points(temp_c: float) -> int:
    """Return the NEWS2-style clinical point contribution for temperature."""
    if 20 <= temp_c <= 26:
        return 0
    if 18 <= temp_c <= 19 or 27 <= temp_c <= 29:
        return 1
    if temp_c <= 17 or temp_c >= 30:
        return 3
    return 0


def noise_modifier(noise_db: float, threshold_low: float = 55.0,
                   threshold_high: float = 70.0) -> float:
    """Return the context-only modifier based on noise DB range."""
    if noise_db < threshold_low:
        return 0
    if noise_db < threshold_high:
        return 1
    return 2


def fused_risk_score(hr_bpm: float, rr_bpm: float, temperature_c: float,
                     noise_db: float,
                     hr_weight: float = 1.0,
                     rr_weight: float = 1.0,
                     temp_weight: float = 1.0,
                     noise_weight: float = 0.3) -> float:
    """Return fused risk: clinical score + small noise modifier.

    The requested guide specifies the point table and the following final
    formula: clinical_risk + 0.3 * noise_modifier.
    """
    clinical_risk = (
        heart_rate_points(hr_bpm) * hr_weight +
        respiratory_rate_points(rr_bpm) * rr_weight +
        temperature_points(temperature_c) * temp_weight
    )
    modifier = noise_modifier(noise_db)
    return float(clinical_risk + noise_weight * modifier)
