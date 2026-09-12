import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from benchmark_ubfc import compute_mae, evaluate_subject, discover_ubfc_subjects


def test_compute_mae_returns_expected_value():
    pred = np.array([60.0, 75.0, 80.0])
    truth = np.array([65.0, 70.0, 85.0])

    mae = compute_mae(pred, truth)

    assert np.isfinite(mae)
    assert mae == 5.0


def test_discover_ubfc_subjects_discovers_dataset_folders_and_subject_directories(tmp_path):
    dataset_root = tmp_path / 'DATASET_2'
    subject = dataset_root / 'subject1'
    subject.mkdir(parents=True)
    (subject / 'ground_truth.txt').write_text('1\n70\n0\n')
    (subject / 'vid.avi').write_bytes(b'video')

    rows = discover_ubfc_subjects(str(dataset_root), sample_rate=30.0)

    assert len(rows) == 1
    assert rows[0]['subject_id'] == 'subject1'
    assert rows[0]['video_path'].endswith('vid.avi')
    assert rows[0]['ground_truth_path'].endswith('ground_truth.txt')

    single_subject_rows = discover_ubfc_subjects(str(subject), sample_rate=30.0)
    assert len(single_subject_rows) == 1
    assert single_subject_rows[0]['subject_id'] == 'subject1'


def test_evaluate_subject_report_path_handles_missing_inputs():
    # Accept a missing input path in a controlled way for a unit test
    # and ensure the helper returns a structured empty fallback.
    report = evaluate_subject(None, None, sample_rate=30.0)

    assert report['estimated_hr_bpm'] is None
    assert report['ground_truth_hr_bpm'] is None
    assert report['mae_bpm'] is None
