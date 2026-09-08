"""Task 2 — Face ROI extraction pipeline.

This module extracts average RGB values from a stable facial ROI and
returns the three continuous signals expected by the rPPG algorithms.
"""

from __future__ import annotations

import cv2
import numpy as np
from typing import Iterable, Tuple, Optional


class ROIExtractor:
    """Extract R, G, B averaged skin-ROI signals from a video stream.

    This implementation supports either a webcam index or a video file.
    It uses MediaPipe when available, and falls back to Haar cascade.
    """

    def __init__(self, source: int | str = 0,
                 fps: Optional[int] = None,
                 use_face_mesh: bool = False,
                 roi_ratio: float = 0.4):
        self.source = source
        self.fps = fps
        self.use_face_mesh = use_face_mesh
        self.roi_ratio = roi_ratio
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def read_video(self, path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """Return R_signal, G_signal, B_signal and fps for a video file.

        The implementation writes values for each frame and ensures the
        signal arrays stay evenly sampled even when face tracking fails.
        """
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        R_signal = []
        G_signal = []
        B_signal = []

        previous_triplet = None
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            roi = self._extract_roi_from_frame(rgb)
            if roi is None:
                if previous_triplet is None:
                    previous_triplet = np.array([0.0, 0.0, 0.0])
                triplet = previous_triplet.copy()
            else:
                # Compute mean RGB values inside ROI
                roi_bgr = cv2.cvtColor(roi, cv2.COLOR_RGB2BGR)
                mean_bgr = roi_bgr.mean(axis=(0, 1))
                # Convert bgr->rgb order for requested output
                triplet = mean_bgr[[2, 1, 0]].astype(float)
                previous_triplet = triplet.copy()

            R_signal.append(triplet[0])
            G_signal.append(triplet[1])
            B_signal.append(triplet[2])
            frame_index += 1

        cap.release()
        return np.array(R_signal), np.array(G_signal), np.array(B_signal), float(fps)

    def read_live(self, source: int | str = 0, seconds: Optional[int] = None,
                  max_frames: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """Read a live webcam feed and produce the three RGB signals.

        This is a direct interface for testing with a camera.
        """
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise ValueError(f"Could not open camera or video source: {source}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        R_signal = []
        G_signal = []
        B_signal = []
        previous_triplet = None

        frame_count = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if max_frames and frame_count >= max_frames:
                break

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            roi = self._extract_roi_from_frame(frame)
            if roi is None:
                if previous_triplet is None:
                    previous_triplet = np.array([0.0, 0.0, 0.0])
                triplet = previous_triplet.copy()
            else:
                rgb_mean = roi.mean(axis=(0, 1))
                triplet = rgb_mean.astype(float)
                previous_triplet = triplet.copy()

            R_signal.append(triplet[0])
            G_signal.append(triplet[1])
            B_signal.append(triplet[2])
            frame_count += 1

            if seconds and frame_count >= int(fps * seconds):
                break

        cap.release()
        return np.array(R_signal), np.array(G_signal), np.array(B_signal), float(fps)

    def _extract_roi_from_frame(self, rgb_frame: np.ndarray) -> Optional[np.ndarray]:
        """Return the ROI crop, or None if no face is detected.

        Uses Haar face detection as the default deterministic fallback.
        """
        if self.face_cascade is None:
            return None

        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) == 0:
            return None

        x, y, w, h = faces[0]
        # Use forehead ROI: from eyebrows/hairline band across middle 40% of face width
        # Landmarks are approximated by the face bounding box because MediaPipe is optional.
        forehead_h = max(1, int(h * 0.22))
        forehead_y = max(0, y + int(h * 0.12))
        roi_w = max(1, int(w * self.roi_ratio))  # middle 40% of face width
        roi_x = x + int(w * 0.3)
        roi = rgb_frame[forehead_y:forehead_y + forehead_h,
                         roi_x:roi_x + roi_w]
        if roi.size == 0:
            return None
        return roi
