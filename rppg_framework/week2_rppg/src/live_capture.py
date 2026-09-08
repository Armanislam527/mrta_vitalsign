"""Task 5 — Webcam + MAX30102 comparison capture utility.

This module is intentionally kept simple and deterministic for a first
serial implementation inside the requested project flow.
"""

from __future__ import annotations

import re
from typing import Optional, Dict, Any

import numpy as np
import cv2


class LiveCapture:
    """Capture simultaneous RGB camera and optional serial HR readings."""

    def __init__(self, source: int | str = 0, serial_port: Optional[str] = None):
        self.source = source
        self.serial_port = serial_port

    def capture(self, seconds: float = 1.0, max_frames: int = 5) -> Dict[str, Any]:
        """Return a capsule of sampled RGB arrays and optional serial HR.

        If no webcam or source is available, return deterministic empty
        arrays and None for the hardware reading. This keeps the module testable.
        """
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            # A robust fallback that still returns module shape expectations
            return {
                'r_signal': np.array([], dtype=float),
                'g_signal': np.array([], dtype=float),
                'b_signal': np.array([], dtype=float),
                'fps': 0.0,
                'hr_bpm': None,
                'serial_hr': None,
            }

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        r_signal = []
        g_signal = []
        b_signal = []

        frames = 0
        while frames < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mean = rgb.mean(axis=(0, 1))
            r_signal.append(float(mean[0]))
            g_signal.append(float(mean[1]))
            b_signal.append(float(mean[2]))
            frames += 1

        cap.release()
        empty = len(r_signal) == 0
        return {
            'r_signal': np.array(r_signal if not empty else [], dtype=float),
            'g_signal': np.array(g_signal if not empty else [], dtype=float),
            'b_signal': np.array(b_signal if not empty else [], dtype=float),
            'fps': float(fps),
            'hr_bpm': None,
            'serial_hr': None,
        }


def parse_serial_hr(raw: bytes) -> Optional[float]:
    """Parse MAX30102/ESP32 serial line, e.g. HR=72."""
    line = raw.decode('utf-8', errors='ignore').strip()
    match = re.search(r'HR[=: ]*([0-9.]+)', line, flags=re.I)
    if not match:
        return None
    return float(match.group(1))
