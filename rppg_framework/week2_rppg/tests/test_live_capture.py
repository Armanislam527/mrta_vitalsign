import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from live_capture import LiveCapture, parse_serial_hr


def test_parse_serial_hr_handles_plain_text():
    value = parse_serial_hr(b'HR=72\n')
    assert value == 72.0


def test_live_capture_reports_empty_capture_without_source():
    capture = LiveCapture(source=0, serial_port=None)
    result = capture.capture(seconds=1, max_frames=5)

    assert result['hr_bpm'] is None
    assert result['serial_hr'] is None
    assert isinstance(result['r_signal'], np.ndarray)
    assert isinstance(result['g_signal'], np.ndarray)
    assert isinstance(result['b_signal'], np.ndarray)
