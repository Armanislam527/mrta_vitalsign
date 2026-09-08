import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from benchmark_ubfc import compute_mae, evaluate_subject


def test_compute_mae_returns_expected_value():
    pred = np.array([60.0, 75.0, 80.0])
    truth = np.array([65.0, 70.0, 85.0])

    mae = compute_mae(pred, truth)

    assert np.isfinite(mae)
    assert mae == 5.0


def test_evaluate_subject_report_path_handles_missing_inputs():
    # Accept a missing input path in a controlled way for a unit test
    # and ensure the helper returns a structured empty fallback.
    report = evaluate_subject(None, None, sample_rate=30.0)

    assert report['estimated_hr_bpm'] is None
    assert report['ground_truth_hr_bpm'] is None
    assert report['mae_bpm'] is None
