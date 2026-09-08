# Week 2 Build Guide — rPPG Pipeline & Environmental Risk Fusion
## Multi-Robot Task Allocation for Continuous Vital-Sign Monitoring


## 0. Prerequisites

```bash
pip install opencv-python numpy scipy matplotlib mediapipe pyserial
```

- Python 3.8+
- A webcam (built-in laptop cam is fine for initial testing)
- MAX30102 pulse-oximeter module + ESP32/Arduino (for ground-truth validation, Task 5)
- DHT22 or SHT31 temperature sensor + a MEMS microphone module (for Task 6)

---

## 1. Directory structure for this module

```
week2_rppg/
├── data/
│   ├── ubfc_samples/          # downloaded benchmark videos go here
│   └── recordings/            # your own webcam test recordings
├── src/
│   ├── roi_extractor.py       # Task 2
│   ├── pos_algorithm.py       # Task 3
│   ├── chrom_algorithm.py     # Task 3 (fallback/comparison)
│   ├── hr_estimator.py        # Task 4
│   ├── rr_estimator.py        # Task 4 (extension)
│   ├── benchmark_ubfc.py      # Task 5
│   ├── live_capture.py        # Task 5 (webcam + MAX30102 comparison)
│   ├── env_sensors.py         # Task 6
│   └── risk_fusion.py         # Task 7
├── results/
│   ├── benchmark_report.csv
│   └── plots/
└── README.md
```

---

## 2. Task 2 — Face ROI extraction pipeline

**Objective:** For every frame of a video (or live webcam feed), produce a single average (R, G, B) triplet from a stable skin region.

**Procedure:**
1. Use `mediapipe.solutions.face_mesh` (preferred — gives precise landmark points) or `cv2.CascadeClassifier('haarcascade_frontalface_default.xml')` (simpler fallback) to locate the face each frame.
2. Define the ROI as the forehead: a rectangle roughly between the eyebrows and the hairline, spanning the middle 40% of face width. If using mediapipe face mesh, use landmark indices around points 10, 109, 338, 151 to bound this region precisely.
3. For each frame, crop this ROI and compute `mean(R)`, `mean(G)`, `mean(B)` across all pixels in the crop.
4. Append these three values to three running lists: `R_signal`, `G_signal`, `B_signal`.
5. Handle frame drops: if no face is detected in a frame, repeat the previous frame's values (don't leave gaps — downstream filtering assumes a continuous, evenly-sampled signal).

**Input:** video file path or `0` for live webcam.
**Output:** three numpy arrays `R_signal, G_signal, B_signal`, each of length = number of frames, plus the video's frame rate (fps).

**Acceptance test:** Run on a 10-second clip of your own face. Plot `G_signal` over time — you should visually see a faint periodic ripple (roughly matching your pulse) once you zoom into a few seconds, even though it looks like noise at full scale.

---

## 3. Task 3 — Implement POS and CHROM algorithms

**Objective:** Convert the raw (R, G, B) signals into a single 1D "pulse signal" where the heartbeat is the dominant periodic component.

**Build CHROM first** (simpler, single-pass, good for confirming the pipeline works end-to-end):

```
Given R_signal, G_signal, B_signal over a window:
  Rn = R_signal / mean(R_signal)
  Gn = G_signal / mean(G_signal)
  Bn = B_signal / mean(B_signal)

  Xs = 3*Rn - 2*Gn
  Ys = 1.5*Rn + Gn - 1.5*Bn

  alpha = std(Xs) / std(Ys)
  pulse_signal = Xs - alpha * Ys
```

**Then implement POS** (more motion-robust, this is your primary/citable method):

```
Process in sliding windows of length L = round(1.6 * fps) frames, stepping 1 frame at a time:
  For each window:
    C = stack([R_window, G_window, B_window])         # shape 3 x L
    Cn = C / mean(C, axis=1, keepdims=True)             # temporal normalization

    S1 = Cn[1] - Cn[2]                                  # G - B
    S2 = -2*Cn[0] + Cn[1] + Cn[2]                       # -2R + G + B

    alpha = std(S1) / std(S2)
    h_window = S1 + alpha * S2

    h_window = h_window - mean(h_window)                # de-mean before overlap-add

  Overlap-add all h_window segments into one continuous pulse_signal
  of the same length as the original video (standard overlap-add:
  add each window's contribution into the corresponding time indices
  of an all-zero output array).
```

**Reference implementation to check yourself against:** the `pyVHR` framework (see References, §8) implements both POS and CHROM correctly — if your numbers diverge wildly from its output on the same video, debug against it line-by-line rather than guessing.

**Input:** `R_signal, G_signal, B_signal, fps`
**Output:** `pulse_signal` (1D array, same length as input signals)

**Acceptance test:** Plot `pulse_signal` for a 10-second still-face clip — it should look visibly more periodic/cleaner than the raw `G_signal` from Task 2.

---

## 4. Task 4 — Turn the pulse signal into HR (and RR) numbers

**Heart rate:**
1. Bandpass filter `pulse_signal` between 0.7–4 Hz (42–240 bpm) using `scipy.signal.butter` + `filtfilt`.
2. Run `scipy.fft.rfft` on the filtered signal.
3. Find the frequency bin with the maximum magnitude within the 0.7–4 Hz range.
4. `HR_bpm = peak_frequency_hz * 60`.
5. For a continuous stream, repeat this every N seconds (e.g., every 5 seconds) using the most recent 10-second window of `pulse_signal`, so you get an updating HR estimate rather than a single number.

**Respiratory rate (secondary signal, lower accuracy — flag this in your paper):**
1. Bandpass filter the same `pulse_signal` between 0.15–0.5 Hz (9–30 breaths/min) instead — breathing shows up as a slow amplitude/frequency modulation of the pulse signal.
2. Apply the same FFT peak-finding approach in this band.
3. Validate this one manually: count your own breaths by hand for 30 seconds while recording, and compare.

**Input:** `pulse_signal, fps`
**Output:** `HR_bpm` (float, updating every N seconds), `RR_bpm` (float)

**Acceptance test:** On yourself, at rest, `HR_bpm` should land in a plausible 60–90 range and stay roughly stable across consecutive 5-second updates (not jumping by 30+ bpm between windows).

---

## 5. Task 5 — Validate against ground truth

**Step A — Public dataset benchmark (do this before trusting your own camera):**
1. Download a handful of subjects from **UBFC-rPPG** (request access via the official page — see References §8) or **PURE**.
2. Each subject folder includes a ground-truth HR/PPG file alongside the video.
3. Run Tasks 2–4 on each video, compare your estimated HR against the ground-truth file.
4. Compute **Mean Absolute Error (MAE)** in bpm across all tested subjects — this is your first citable accuracy number for the paper.
5. Log per-subject results to `results/benchmark_report.csv`.

**Step B — Live validation against your own MAX30102:**
1. Wire the MAX30102 to an ESP32/Arduino; use its standard library to stream raw HR readings over serial.
2. In `live_capture.py`, open the serial port (`pyserial`) alongside the webcam feed.
3. Run your rPPG pipeline live, and every 5 seconds, log both your rPPG-estimated HR and the MAX30102's simultaneous reading side by side.
4. Compute the same MAE metric for your own hardware setup — this is your real hardware validation number.

**Acceptance test:** You have two MAE numbers (benchmark dataset, own hardware) written down and saved to CSV — both are needed for your Results section later.

---

## 6. Task 6 — Environmental sensors

**Objective:** Read ambient temperature and noise level alongside the vitals pipeline.

**Procedure:**
1. Wire DHT22 (or SHT31) to your ESP32/Raspberry Pi; read temperature in °C at a fixed interval (e.g., every 2 seconds).
2. Wire a MEMS microphone module (e.g., a simple analog sound sensor or an INMP441 I2S mic); compute an approximate dB level from the raw amplitude readings (a simple RMS-based approximation is fine — you don't need calibrated SPL accuracy for this project, but state that limitation explicitly in your paper).
3. Publish/log both values on the same timestamp basis as your HR/RR estimates so they can be fused in Task 7.

**Input:** sensor hardware readings
**Output:** `temperature_c` (float), `noise_db` (float), updating every ~2 seconds

**Acceptance test:** Values change sensibly when you test them — temperature rises slightly if you breathe near the sensor, noise level jumps if you clap or talk near the mic.

---

## 7. Task 7 — Fused risk score (NEWS2-inspired, no ML)

**Objective:** Combine HR, RR, temperature, and noise into one risk number using a fixed, explainable point system — deliberately not a trained model, so it's easy to defend to reviewers.

**Point table (adapt thresholds after seeing your own baseline readings):**

| Signal | 0 pts | 1 pt | 2 pts | 3 pts |
|---|---|---|---|---|
| Heart rate (bpm) | 61–90 | 51–60 or 91–110 | 111–130 | ≤50 or ≥131 |
| Respiratory rate (breaths/min) | 12–20 | 9–11 or 21–24 | — | ≤8 or ≥25 |
| Room temperature (°C) | 20–26 | 18–19 or 27–29 | — | ≤17 or ≥30 |

```
clinical_risk = HR_points + RR_points + Temp_points   # 0–9 range

# Noise is context, not a vital sign — keep it as a small separate modifier,
# not mixed into the clinical score itself:
noise_modifier = 0 if noise_db < 55 else (1 if noise_db < 70 else 2)

fused_risk_score = clinical_risk + 0.3 * noise_modifier
```

Keep the weights (`0.3` above, and the point-table thresholds) as named constants in your code — you'll likely tune them once you see real data, and your paper should report whatever final values you settle on.

**Input:** `HR_bpm, RR_bpm, temperature_c, noise_db`
**Output:** `fused_risk_score` (float)

**Acceptance test:** Simulate a "resting" case (HR≈70, RR≈16, temp≈23, quiet) → score near 0. Simulate a "concerning" case (HR≈135, RR≈26, temp≈31, loud) → score should clearly jump to the higher end of the range.

---

## 8. References

**Algorithms:**
- Wang, W., den Brinker, A.C., Stuijk, S., de Haan, G. (2017). *Algorithmic Principles of Remote PPG.* IEEE Trans. Biomedical Engineering. — the POS algorithm, primary method.
- de Haan, G., Jeanne, V. (2013). *Robust Pulse Rate From Chrominance-Based rPPG.* — the CHROM algorithm.

**Reference code (check your implementation against these, don't blindly copy):**
- `pyVHR` — https://github.com/phuselab/pyVHR — Python framework implementing POS, CHROM, and 7 other rPPG methods, with built-in dataset loaders for UBFC-rPPG and PURE. Good for cross-checking your own numbers.
- `rPPG-Toolbox` — https://github.com/ubicomplab/rPPG-Toolbox — University of Washington toolbox, supports both classical (POS, CHROM, ICA) and deep-learning rPPG methods plus standardized dataset loading.

**Datasets:**
- UBFC-rPPG official page (request access): https://sites.google.com/view/ybenezeth/ubfcrppg
- PURE dataset — described in Stricker, Müller, Gross (2014), *Non-contact Video-based Pulse Rate Measurement on a Mobile Service Robot*, Ro-Man 2014.

**Risk scoring basis:**
- NEWS2 (National Early Warning Score 2) — Royal College of Physicians (UK). Search "NEWS2 Royal College of Physicians" for the official scoring documentation; your point table above is a simplified adaptation for two non-contact channels.

---

## 9. Week 2 deliverables checklist

- ☐ Working ROI extraction on live webcam and on a sample video
- ☐ Both CHROM and POS implemented, POS as primary
- ☐ HR estimation updating live, plausible values at rest
- ☐ RR estimation, validated once against manual breath counting
- ☐ Benchmark MAE computed on UBFC-rPPG or PURE (saved to CSV)
- ☐ Live MAE computed against your own MAX30102 (saved to CSV)
- ☐ Temperature + noise sensors reading live values
- ☐ Fused risk score function implemented and sanity-tested on two extreme cases
- ☐ Short written log: what broke, how you fixed it (feeds your final report's methodology section)
