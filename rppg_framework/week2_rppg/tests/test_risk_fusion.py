import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from risk_fusion import fused_risk_score


def test_fused_risk_score_resting_and_concerning_cases():
    resting = fused_risk_score(70, 16, 23, 40)
    concerning = fused_risk_score(135, 26, 31, 80)

    assert resting < concerning
    assert resting >= 0
    assert concerning >= 6
