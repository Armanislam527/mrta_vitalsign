# rPPG Framework User Manual

This document explains where to start, how to run the scripts, the project serial order, and the specification of each module that has been implemented in this workspace.

## 1. Project goal

This repository follows the Week 2 rPPG pipeline and environmental risk fusion guide. The intent is to build a modular remote-PPG pipeline that reads RGB video signals, extracts a pulse signal using classical algorithms, estimates vital signs, and fuses them with environmental noise and temperature readings into a clinically inspired risk score.

## 2. Workspace structure

```text
week2_rppg/
├── README.md
├── USER_MANUAL.md
├── requirements.txt
├── data/
│   ├── ubfc_samples/
│   └── recordings/
├── src/
│   ├── roi_extractor.py
│   ├── chrom_algorithm.py
│   ├── pos_algorithm.py
│   ├── hr_estimator.py
│   ├── rr_estimator.py
│   ├── benchmark_ubfc.py
│   ├── live_capture.py
│   ├── env_sensors.py
│   └── risk_fusion.py
└── tests/
    ├── test_roi_extractor.py
    ├── test_chrom_algorithm.py
    ├── test_pos_algorithm.py
    ├── test_hr_estimator.py
    ├── test_rr_estimator.py
    ├── test_benchmark_ubfc.py
    ├── test_live_capture.py
    ├── test_env_sensors.py
    └── test_risk_fusion.py
```

## 3. Recommended environment

Use Python 3.8 or newer. A webcam is enough for testing the live stream. Hardware sensors such as MAX30102, DHT22/SHT31, and a microphone can be added later.

Install dependencies:

```bash
pip install -r requirements.txt
```

The guide also recommends these additional packages:

```bash
pip install opencv-python numpy scipy matplotlib mediapipe pyserial
```

The first implementation in this workspace uses a compatible OpenCV version:

```bash
pip install opencv-python==4.8.1.78
```

## 4. Serial build order

The build must be maintained strictly in this module order:

1. ROI extraction module
2. CHROM algorithm module
3. POS algorithm module
4. HR estimation module
5. RR estimation module
6. UBFC benchmark module
7. Live capture module
8. Environmental sensors module
9. Risk fusion module

Do not mix modules or jump across the chain. Each module feeds the next stage.

## 5. Module-by-module specification

### Module 1 — ROI extraction

File: src/roi_extractor.py

Purpose:
- Extract a stable foreground face region as the input region of interest.
- Read RGB mean values over the selected ROI and produce R, G, and B arrays.
- Repeat the last known triplet when a frame has no tracked face to keep the signal continuous.

Entry point:

```python
from roi_extractor import ROIExtractor
extractor = ROIExtractor(source=0)
R, G, B, fps = extractor.read_live(source=0)
```

Or for a video file:

```python
R, G, B, fps = extractor.read_video('data/recordings/sample.mp4')
```

Output:
- R_signal
- G_signal
- B_signal
- fps

### Module 2 — CHROM algorithm

File: src/chrom_algorithm.py

Purpose:
- Convert RGB signals into a cleaner pulse signal using the CHROM formula:

```text
Rn = R / mean(R)
Gn = G / mean(G)
Bn = B / mean(B)
Xs = 3*Rn - 2*Gn
Ys = 1.5*Rn + Gn - 1.5*Bn
alpha = std(Xs) / std(Ys)
pulse = Xs - alpha * Ys
```

Entry point:

```python
from chrom_algorithm import compute_chrom
pulse = compute_chrom(R, G, B)
```

### Module 3 — POS algorithm

File: src/pos_algorithm.py

Purpose:
- Generate the primary pulse signal with sliding-window normalization and overlap-add.
- Use the guide’s POS definitions for S1 and S2 and build the pulse waveform.

Entry point:

```python
from pos_algorithm import compute_pos
pulse = compute_pos(R, G, B, fps)
```

Output:
- pulse_signal array same length as the RGB signals.

### Module 4 — HR estimator

File: src/hr_estimator.py

Purpose:
- Bandpass the pulse signal between 0.7 and 4 Hz.
- Use FFT to find the main frequency peak in that range.
- Convert to BPM via peak_hz * 60.

Entry point:

```python
from hr_estimator import estimate_hr_bpm
hr_bpm = estimate_hr_bpm(pulse_signal, fps)
```

For a stream of updates:

```python
from hr_estimator import estimate_hr_series
hr_updates = estimate_hr_series(pulse_signal, fps, window_seconds=10, update_seconds=5)
```

### Module 5 — RR estimator

File: src/rr_estimator.py

Purpose:
- Estimate respiratory rate using the same peak-frequency logic but in the RR band of 0.15–0.5 Hz.
- Use the pulse signal’s low-level modulation as an RR proxy.

Entry point:

```python
from rr_estimator import estimate_rr_bpm
rr_bpm = estimate_rr_bpm(pulse_signal, fps)
```

### Module 6 — UBFC benchmark module

File: src/benchmark_ubfc.py

Purpose:
- Compute MAE between predicted HR values and ground-truth HR values.
- Support per-subject benchmark reports.

Entry point:

```python
from benchmark_ubfc import compute_mae, evaluate_subject, write_benchmark_report
mae = compute_mae(predicted, truth)
row = evaluate_subject(video_path, truth_path, sample_rate=30.0)
write_benchmark_report([row], 'results/benchmark_report.csv')
```

### Module 7 — Live capture module

File: src/live_capture.py

Purpose:
- Capture frames from webcam or a given source.
- Parse an optional serial HR line from a MAX30102/ESP32 device.

Entry point:

```python
from live_capture import LiveCapture, parse_serial_hr
capture = LiveCapture(source=0, serial_port=None)
result = capture.capture(seconds=1.0, max_frames=5)
serial_value = parse_serial_hr(b'HR=72\n')
```

### Module 8 — Environmental sensors module

File: src/env_sensors.py

Purpose:
- Keep the environmental sensor abstraction simple.
- Store temperature and noise as typed sensor readings.
- Estimate dB from microphone sample arrays using RMS.

Entry point:

```python
from env_sensors import SensorReading, read_temperature, read_noise_level, estimate_noise_db
reading = read_temperature(23.0)
noise = read_noise_level(45.0)
noise_db = estimate_noise_db(samples)
```

### Module 9 — Risk fusion

File: src/risk_fusion.py

Purpose:
- Combine HR, RR, temperature, and noise into a fused score.
- Implement the guide’s fixed point table and noise modifier.

Entry point:

```python
from risk_fusion import fused_risk_score
score = fused_risk_score(70, 16, 23, 40)
```

## 6. How to run the scripts

Use the modules in the exact order described above.

### Step A — install

```bash
cd week2_rppg
python3 -m pip install -r requirements.txt
```

### Step B — use ROI extraction

```bash
cd week2_rppg
python3 -c "from src.roi_extractor import ROIExtractor; print('ROI importer ready')"
```

For a real webcam session:

```bash
cd week2_rppg
python3 - <<'PY'
from src.roi_extractor import ROIExtractor
extractor = ROIExtractor(source=0)
R, G, B, fps = extractor.read_live(source=0, max_frames=120)
print(R.shape, G.shape, B.shape, fps)
PY
```

### Step C — run CHROM or POS

```bash
cd week2_rppg
python3 - <<'PY'
import numpy as np
from src.chrom_algorithm import compute_chrom
R = np.ones(10)
G = np.ones(10) * 2
B = np.ones(10) * 3
pulse = compute_chrom(R, G, B)
print(pulse)
PY
```

### Step D — run HR/RR estimation

```bash
cd week2_rppg
python3 - <<'PY'
import numpy as np
from src.hr_estimator import estimate_hr_bpm
from src.rr_estimator import estimate_rr_bpm
pulse = np.sin(np.linspace(0, np.pi, 100))
print(estimate_hr_bpm(pulse, fps=30.0))
print(estimate_rr_bpm(pulse, fps=30.0))
PY
```

### Step E — run benchmark or live capture

```bash
cd week2_rppg
python3 - <<'PY'
from src.benchmark_ubfc import compute_mae
import numpy as np
pred = np.array([70, 75])
truth = np.array([72, 78])
print(compute_mae(pred, truth))
PY
```

### Step F — sample risk fusion

```bash
cd week2_rppg
python3 - <<'PY'
from src.risk_fusion import fused_risk_score
score = fused_risk_score(70, 16, 23, 40)
print(score)
PY
```

## 7. Testing and validation

To run the tests that verify the implemented modules:

```bash
cd week2_rppg
python3 -m pytest tests/test_roi_extractor.py tests/test_chrom_algorithm.py tests/test_pos_algorithm.py tests/test_hr_estimator.py tests/test_rr_estimator.py tests/test_benchmark_ubfc.py tests/test_live_capture.py tests/test_env_sensors.py tests/test_risk_fusion.py
```

## 8. Known limitation

This workspace currently implements the deterministic algorithm skeletons and regression tests. It is not yet a full hardware-integrated pipeline for MAX30102, DHT22/SHT31, or MEMS microphone hardware. These will require real device wiring and serial I/O integration in the next extension phase.

## 9. Serial maintenance checklist

Use the following checklist when building or extending the application:

- [ ] Confirm ROI extraction produces RGB triplets and fps.
- [ ] Confirm CHROM pulse signal is generated.
- [ ] Confirm POS pulse signal is generated.
- [ ] Confirm HR update pipeline computes valid BPM.
- [ ] Confirm RR estimate runs in the correct band.
- [ ] Confirm benchmark MAE and CSV report generation are valid.
- [ ] Confirm live capture parses serial HR lines from sensor device.
- [ ] Confirm environmental readings return stable values.
- [ ] Confirm fused risk score matches the guide’s point table and noise modifier.

## 10. Notes for the developer

This manual keeps the serial order stable. In future iterations, add one module implementation file, one test file for that module, and then update the manual. Do not implement hardware and algorithm functions together in the same edit. Follow the same sequence everywhere.
