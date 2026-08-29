"""NEWS2-inspired fused risk score.

Used by the simulated world (to generate true_risk) and by risk_fusion_node
(identical math on noisy observations). Keep this module free of rospy so it
can run unchanged on real hardware and in offline unit tests.
"""

from __future__ import division

# NEWS2 component maxima (HR + RR + temp) = 3+3+3; extras add up to 3.
NEWS2_MAX = 12.0


def _band_score(value, bands):
    """Return the score of the first (lo, hi, score) band that contains value.

    Bands are half-open [lo, hi). Use hi=None for an unbounded upper end.
    """
    for lo, hi, score in bands:
        if value >= lo and (hi is None or value < hi):
            return score
    return bands[-1][2]


def news2_heart_rate(hr_bpm):
    # NEWS2 pulse bands (adult).
    return _band_score(hr_bpm, [
        (0.0, 41.0, 3),
        (41.0, 51.0, 1),
        (51.0, 91.0, 0),
        (91.0, 111.0, 1),
        (111.0, 131.0, 2),
        (131.0, None, 3),
    ])


def news2_resp_rate(rr):
    return _band_score(rr, [
        (0.0, 9.0, 3),
        (9.0, 12.0, 1),
        (12.0, 21.0, 0),
        (21.0, 25.0, 2),
        (25.0, None, 3),
    ])


def news2_temperature(temp_c):
    return _band_score(temp_c, [
        (0.0, 35.1, 3),
        (35.1, 36.1, 1),
        (36.1, 38.1, 0),
        (38.1, 39.1, 1),
        (39.1, None, 2),
    ])


def hrv_component(hrv_proxy):
    """Map a unitless stress proxy in roughly [0, 1] onto {0,1,2,3}."""
    if hrv_proxy < 0.25:
        return 0
    if hrv_proxy < 0.5:
        return 1
    if hrv_proxy < 0.75:
        return 2
    return 3


def noise_component(noise_db):
    """Ward noise as an environmental aggravating factor."""
    if noise_db < 45.0:
        return 0
    if noise_db < 55.0:
        return 1
    if noise_db < 65.0:
        return 2
    return 3


def news2_components(heart_rate, resp_rate, hrv_proxy, temperature_c, noise_db):
    return {
        "hr": news2_heart_rate(heart_rate),
        "rr": news2_resp_rate(resp_rate),
        "temp": news2_temperature(temperature_c),
        "hrv": hrv_component(hrv_proxy),
        "noise": noise_component(noise_db),
    }


def fuse_risk(heart_rate, resp_rate, hrv_proxy, temperature_c, noise_db):
    """Return a fused risk in [0, 1].

    The raw NEWS2-style sum is divided by NEWS2_MAX so allocator weights stay
    on a consistent scale whether the input is simulated or real.
    """
    parts = news2_components(
        heart_rate, resp_rate, hrv_proxy, temperature_c, noise_db
    )
    raw = float(sum(parts.values()))
    return max(0.0, min(1.0, raw / NEWS2_MAX))
