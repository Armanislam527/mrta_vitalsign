"""Live rPPG demo pipeline.

This script runs the already-implemented serial pipeline in a single entry
point:
    1. ROI signal extraction from a live webcam
    2. POS pulse signal generation
    3. HR estimation from the FFT peak in the HR band

It also offers an optional microphone-noise sample estimate, but it will not
fail if a microphone backend is not available in the current environment.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.roi_extractor import ROIExtractor
from src.pos_algorithm import compute_pos
from src.hr_estimator import estimate_hr_bpm
from src.env_sensors import estimate_noise_db


try:
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None


DEFAULT_CAMERA = 0
DEFAULT_SECONDS = 10
DEFAULT_FRAMES = 300


def estimate_microphone_noise(seconds: float = 1.0,
                              sample_rate: int = 44100,
                              channel_count: int = 1) -> Optional[float]:
    """Return an approximate RMS-based dB reading from a live microphone if sounddevice is installed.

    If the package is unavailable or the device cannot be opened, return None.
    """
    if sd is None:
        return None

    try:
        samples = sd.rec(int(sample_rate * seconds), samplerate=sample_rate,
                         channels=channel_count, dtype='float32')
        sd.wait()
        if samples.size == 0:
            return None
        return estimate_noise_db(samples.reshape(-1))
    except Exception:
        return None


def run_demo(camera_source: int = DEFAULT_CAMERA,
             duration_seconds: int = DEFAULT_SECONDS,
             sample_rate: float = 30.0,
             use_microphone: bool = False) -> Dict[str, Any]:
    """Run a live camera-based rPPG estimation workflow and return diagnostics.

    The returned dictionary contains the same basic data flow requested by the
    project documentation and remains deterministic for test or CLI use.
    """
    # Step 1: collect RGB signal arrays from ROI extraction
    extractor = ROIExtractor(source=camera_source)
    r_signal, g_signal, b_signal, fps = extractor.read_live(
        source=camera_source,
        max_frames=int(duration_seconds * sample_rate),
    )

    if len(r_signal) == 0:
        raise RuntimeError("No frames were captured from the selected camera.")

    # Step 2: estimate pulse signal using POS (primary algorithm in guide)
    pulse_signal = compute_pos(r_signal, g_signal, b_signal, fps)

    # Step 3: estimate HR frequency with FFT in the requested HR band
    hr_bpm = estimate_hr_bpm(pulse_signal, fps)

    # Optional environment signal: microphone-derived dB estimate if available
    noise_db = None
    if use_microphone:
        noise_db = estimate_microphone_noise(seconds=1.0)

    output = {
        'r_signal': r_signal,
        'g_signal': g_signal,
        'b_signal': b_signal,
        'pulse_signal': pulse_signal,
        'fps': fps,
        'hr_bpm': float(hr_bpm),
        'noise_db': noise_db,
    }
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run a live rPPG HR estimation demo.')
    parser.add_argument('--camera', type=int, default=DEFAULT_CAMERA,
                        help='Webcam source index, default 0.')
    parser.add_argument('--seconds', type=int, default=DEFAULT_SECONDS,
                        help='Capture duration in seconds, default 10.')
    parser.add_argument('--fps', type=float, default=30.0,
                        help='Assumed camera frame rate used by the sampling path.')
    parser.add_argument('--microphone', action='store_true',
                        help='Try to estimate a noise level using a connected microphone.')
    parser.add_argument('--save-results', default='results/live_demo_hr.csv',
                        help='CSV path for storing the HR estimate in the project results directory.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_path = Path(__file__).resolve().parents[1]
    results_dir = base_path / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)

    result = run_demo(
        camera_source=args.camera,
        duration_seconds=args.seconds,
        sample_rate=args.fps,
        use_microphone=args.microphone,
    )

    # Save a deterministic HR estimate report
    output_path = Path(args.save_results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w') as handle:
        handle.write('module,metric,value\n')
        handle.write(f'roi,frames,{len(result["r_signal"])}\n')
        handle.write(f'pos,pulse_length,{len(result["pulse_signal"])}\n')
        handle.write(f'hr_estimator,hr_bpm,{result["hr_bpm"]:.3f}\n')
        if result['noise_db'] is not None:
            handle.write(f'env_sensors,noise_db,{result["noise_db"]:.3f}\n')
        else:
            handle.write('env_sensors,noise_db,not_available\n')

    print('Estimated HR:', f'{result["hr_bpm"]:.2f} bpm')
    if result['noise_db'] is not None:
        print('Estimated noise:', f'{result["noise_db"]:.2f} dB')
    else:
        print('Estimated noise: not available (microphone package or device missing)')

    print('Result CSV written to:', output_path)


if __name__ == '__main__':
    main()
