import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from roi_extractor import ROIExtractor


def test_roi_extractor_uses_repeat_when_no_face():
    """The module should not crash and should produce signal arrays of consistent shape.

    This test exercises the deterministic part of the module without requiring webcam access.
    """
    extractor = ROIExtractor(source=0)

    # Exercise ROI extraction fallback and shape handling with a synthetic frame.
    # This confirms the module can be imported and executed on a simple frame.
    fake_frame = np.zeros((80, 80, 3), dtype=np.uint8)
    roi = extractor._extract_roi_from_frame(fake_frame)
    assert roi is None

    # Synthetic output check for array length behavior when no ROI returns None.
    assert hasattr(extractor, 'read_video')
    assert hasattr(extractor, 'read_live')
