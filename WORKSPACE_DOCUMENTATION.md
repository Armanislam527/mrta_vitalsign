# MRTA Vital Sign Monitoring - Complete Workspace Documentation

**Project**: Multi-Robot Task Allocation for Continuous Vital-Sign Monitoring  
**Target Platform**: Ubuntu 20.04 + ROS Noetic  
**RNG Seed**: 7 (for reproducibility)

---

## Table of Contents
1. [Workspace Structure](#workspace-structure)
2. [Message Definitions](#message-definitions)
3. [ROS Parameters](#ros-parameters)
4. [Node Documentation](#node-documentation)
5. [Utility Modules](#utility-modules)
6. [Command Reference](#command-reference)
7. [Topic and Service Overview](#topic-and-service-overview)

---

## Workspace Structure

```
~/mrta_vitalsign/
├── src/
│   ├── mrta_msgs/                    # Custom message package
│   │   ├── CMakeLists.txt
│   │   ├── package.xml
│   │   └── msg/
│   │       ├── CBBABid.msg
│   │       ├── EnvReading.msg
│   │       ├── GroundTruthPatientArray.msg
│   │       ├── GroundTruthPatientState.msg
│   │       ├── PatientBeliefArray.msg
│   │       ├── PatientBeliefState.msg
│   │       ├── RiskReading.msg
│   │       ├── TaskAssignment.msg
│   │       └── VitalsReading.msg
│   │
│   └── mrta_simulation/              # Main simulation package
│       ├── CMakeLists.txt
│       ├── package.xml
│       ├── setup.py
│       ├── README.md
│       │
│       ├── src/mrta_simulation/      # Python module (importable)
│       │   ├── __init__.py
│       │   ├── risk_model.py         # NEWS2 risk fusion
│       │   ├── cbba_core.py          # CBBA algorithm
│       │   └── geometry_utils.py     # Math utilities
│       │
│       ├── scripts/                  # Executable node entry points
│       │   ├── patient_simulator_node.py
│       │   ├── robot_kinematics_sim_node.py
│       │   ├── rppg_sensor_sim_node.py
│       │   ├── env_sensor_sim_node.py
│       │   ├── risk_fusion_node.py
│       │   ├── patient_knowledge_base_node.py
│       │   ├── task_allocator_node.py
│       │   ├── cbba_bidding_node.py
│       │   ├── waypoint_navigator_node.py
│       │   ├── rviz_marker_publisher_node.py
│       │   └── metrics_logger_node.py
│       │
│       ├── launch/
│       │   ├── simulation.launch
│       │   ├── robots.launch.xml
│       │   ├── patients.launch.xml
│       │   └── experiment_batch.launch
│       │
│       ├── config/
│       │   ├── sim_params.yaml
│       │   ├── risk_dynamics.yaml
│       │   └── allocator_params.yaml
│       │
│       ├── rviz/
│       │   └── mrta_sim.rviz
│       │
│       └── results/
│           └── logs/
│
├── build/                            # Catkin build directory
├── devel/                            # Catkin development space
└── ros_noetic_simulation_architecture.md
```

---

## Message Definitions

### 1. **VitalsReading.msg** - Raw vitals from rPPG sensor
```protobuf
Header header
int32 patient_id                      # Patient identifier (0-based)
float32 heart_rate                    # Beats per minute: [45.0, 160.0]
float32 resp_rate                     # Breaths per minute: [8.0, 36.0]
float32 hrv_proxy                     # Stress proxy: [0.0, 1.0]
```

**Subscribers**: 
- `risk_fusion_node` (per robot)

**Publishers**: 
- `rppg_sensor_sim_node` (per robot, namespaced)

**Publish Rate**: 5 Hz (configurable)

**Frequency**: Only published when patient is within sensing range (2.0m default)

---

### 2. **EnvReading.msg** - Environmental sensor data
```protobuf
Header header
int32 patient_id                      # -1 if outside all patient zones
float32 temperature_c                 # Celsius: [22.0, 40.5]
float32 noise_db                      # Decibels: [30.0, 80.0]
```

**Subscribers**: 
- `risk_fusion_node` (per robot)

**Publishers**: 
- `env_sensor_sim_node` (per robot, namespaced)

**Publish Rate**: 2 Hz (configurable)

**Frequency**: Continuous (even when no patient detected)

---

### 3. **RiskReading.msg** - Fused risk score
```protobuf
Header header
int32 robot_id                        # Robot identifier (0-based)
int32 patient_id                      # Patient being observed
float32 risk_value                    # Fused NEWS2 score: [0.0, 1.0]
```

**Subscribers**: 
- `patient_knowledge_base_node` (central)
- `metrics_logger_node` (central)

**Publishers**: 
- `risk_fusion_node` (per robot, namespaced)

**Publish Rate**: Variable (depends on vitals frequency)

---

### 4. **PatientBeliefState.msg** - Single patient belief entry
```protobuf
int32 patient_id                      # Patient identifier (0-based)
float32 last_known_risk               # Latest observed risk: [0.0, 1.0]
float64 last_update_time              # ROS time of last observation
float32 staleness_sec                 # Seconds since last update: [0.0, ∞)
geometry_msgs/Point position          # (x, y, z) patient location in meters
```

**Components**:
- **last_known_risk**: Range [0.0, 1.0], normalized NEWS2-style score
- **staleness_sec**: Grows monotonically when patient unobserved; 0 when freshly observed
- **position**: Static during experiment; typically in workspace bounds [0, 10] meters

---

### 5. **PatientBeliefArray.msg** - Complete belief state
```protobuf
PatientBeliefState[] patients         # Array of patient states (length = num_patients)
```

**Subscribers**: 
- `task_allocator_node` (central)
- `rviz_marker_publisher_node` (visualization)
- `waypoint_navigator_node` (per robot)

**Publishers**: 
- `patient_knowledge_base_node` (central)

**Publish Rate**: 2 Hz (configurable)

---

### 6. **TaskAssignment.msg** - Robot's assigned patient
```protobuf
int32 robot_id                        # Robot identifier (0-based)
int32 assigned_patient_id             # Target patient ID (0-based), or -1 for idle
float64 assignment_time               # ROS time when assignment was made
string allocator_mode                 # "round_robin" | "greedy" | "cbba"
```

**Subscribers**: 
- `waypoint_navigator_node` (per robot, namespaced)

**Publishers**: 
- `task_allocator_node` (centralized mode) or `cbba_bidding_node` (decentralized)

**Publish Rate**: Variable (upon allocation decision)

**Latching**: Yes (retains last message for late subscribers)

---

### 7. **CBBABid.msg** - Decentralized consensus bid
```protobuf
int32 robot_id                        # Bidding robot identifier (0-based)
int32 patient_id                      # Task (patient) ID being bid on (0-based)
float32 bid_value                     # Utility score: [−∞, +∞]
float64 timestamp                     # ROS time of bid
```

**Subscribers**: 
- All `cbba_bidding_node` instances (broadcast topic)

**Publishers**: 
- All `cbba_bidding_node` instances (when allocator_mode == "cbba")

**Publish Rate**: 4 Hz (configurable)

**Active Only When**: `/allocator_mode` parameter is "cbba"

---

### 8. **GroundTruthPatientState.msg** - Simulation ground truth (logger only)
```protobuf
int32 patient_id                      # Patient identifier (0-based)
float32 true_risk                     # Hidden true risk: [0.0, 1.0]
geometry_msgs/Point position          # Patient location: x,y in [0, 10] meters
float32 heart_rate                    # True physiological HR: [45.0, 160.0] bpm
float32 resp_rate                     # True respiratory rate: [8.0, 36.0] breaths/min
float32 hrv_proxy                     # True HRV stress: [0.0, 1.0]
float32 temperature_c                 # True body temp: [35.0, 40.5] Celsius
float32 noise_db                      # True environmental noise: [30.0, 80.0] dB
```

**WARNING**: 
- Published by `patient_simulator_node`
- **MUST NOT** be subscribed to by decision-making nodes (allocator, navigator)
- Only `metrics_logger_node` should subscribe for offline evaluation

**Publish Rate**: 10 Hz (configurable)

---

### 9. **GroundTruthPatientArray.msg** - All ground truth states
```protobuf
GroundTruthPatientState[] patients    # Array of all patient states
```

---

## ROS Parameters

All parameters are loaded from YAML config files and set onto the ROS parameter server.

### Simulation Parameters (`sim_params.yaml`)

| Parameter | Type | Default | Range | Unit | Description |
|-----------|------|---------|-------|------|-------------|
| `num_robots` | int | 3 | [1, 20] | - | Number of mobile robots |
| `num_patients` | int | 5 | [1, 100] | - | Number of stationary patients |
| `world_frame` | string | "map" | - | - | TF frame name for world |
| `rng_seed` | int | 7 | [0, ∞) | - | Random seed for reproducibility |
| `sensing_range` | float | 2.0 | [0.5, 10.0] | m | rPPG camera max range |
| `env_zone_radius` | float | 3.0 | [0.5, 15.0] | m | Environmental sensor zone radius |
| `dwell_time_required` | float | 3.0 | [0.1, 30.0] | s | Duration at patient to count as visit |
| `battery_full` | float | 1.0 | [0, 1] | normalized | Initial battery level |
| `battery_drain_per_mps` | float | 0.004 | [0, 0.1] | 1/m | Battery drain per meter traveled |

### Patient Positions (`patient_positions`)
```yaml
patient_positions:
  - {x: 3.0, y: 1.5, z: 0.0}
  - {x: 6.0, y: 2.0, z: 0.0}
  - {x: 8.5, y: 5.0, z: 0.0}
  - {x: 4.0, y: 6.5, z: 0.0}
  - {x: 1.5, y: 4.5, z: 0.0}
```
**Range**: x ∈ [0, 10], y ∈ [0, 10], z = 0.0 (fixed)

### Robot Start Poses (`robot_start_poses`)
```yaml
robot_start_poses:
  - {x: 0.6, y: 0.6, yaw: 0.0}
  - {x: 0.6, y: 1.8, yaw: 0.0}
  - {x: 0.6, y: 3.0, yaw: 0.0}
```
**Range**: x ∈ [0, 10], y ∈ [0, 10], yaw ∈ [−π, π]

### Sensor Noise (`sensor_noise`)

| Parameter | Type | Default | Range | Unit | Description |
|-----------|------|---------|-------|------|-------------|
| `sensor_noise/hr_std` | float | 2.5 | [0, 10] | bpm | Heart rate Gaussian noise stddev |
| `sensor_noise/rr_std` | float | 0.8 | [0, 5] | breaths/min | Respiration rate noise |
| `sensor_noise/hrv_std` | float | 0.04 | [0, 0.2] | normalized | HRV stress proxy noise |
| `sensor_noise/temp_std` | float | 0.15 | [0, 1.0] | °C | Temperature sensor noise |
| `sensor_noise/noise_std` | float | 1.5 | [0, 10] | dB | Noise sensor uncertainty |

### Navigator Parameters (`navigator`)

| Parameter | Type | Default | Range | Unit | Description |
|-----------|------|---------|-------|------|-------------|
| `navigator/arrive_radius` | float | 0.4 | [0.1, 2.0] | m | Distance to patient to stop |
| `navigator/kp_lin` | float | 0.8 | [0.1, 2.0] | - | Linear velocity proportional gain |
| `navigator/kp_ang` | float | 2.0 | [0.5, 5.0] | - | Angular velocity proportional gain |
| `navigator/v_max` | float | 0.6 | [0.1, 1.5] | m/s | Maximum linear velocity |
| `navigator/w_max` | float | 1.2 | [0.5, 3.0] | rad/s | Maximum angular velocity |

### Risk Dynamics Parameters (`risk_dynamics.yaml`)

| Parameter | Type | Default | Range | Unit | Description |
|-----------|------|---------|-------|------|-------------|
| `risk_dynamics/hr_base` | float | 75.0 | [50, 100] | bpm | Baseline heart rate |
| `risk_dynamics/rr_base` | float | 16.0 | [10, 25] | breaths/min | Baseline respiration rate |
| `risk_dynamics/hrv_base` | float | 0.20 | [0.1, 0.5] | normalized | Baseline HRV |
| `risk_dynamics/temp_base` | float | 36.8 | [36.0, 37.5] | °C | Baseline body temp |
| `risk_dynamics/noise_base` | float | 42.0 | [30, 60] | dB | Baseline ambient noise |
| `risk_dynamics/drift_std` | float | 0.08 | [0, 0.5] | per-step | Gaussian drift rate |
| `risk_dynamics/spike_prob` | float | 0.002 | [0, 0.05] | prob/tick | Probability of risk spike |
| `risk_dynamics/spike_magnitude` | float | 0.45 | [0, 1.0] | factor | Multiplier for spike size |
| `risk_dynamics/spike_duration` | float | 25.0 | [5, 60] | s | How long spike persists |

**Spike Probability Note**: At 10 Hz publish rate, 0.002 probability ≈ 1.2 spikes/minute/patient expected

### Allocator Parameters (`allocator_params.yaml`)

| Parameter | Type | Default | Range | Unit | Description |
|-----------|------|---------|-------|------|-------------|
| `allocator_mode` | string | "greedy" | {"round_robin", "greedy", "cbba"} | - | Allocation algorithm |
| `allocator/w1` | float | 1.00 | [0, 10] | - | Weight for risk component |
| `allocator/w2` | float | 0.60 | [0, 10] | - | Weight for staleness component |
| `allocator/w3` | float | 0.35 | [0, 10] | - | Weight for distance penalty |
| `allocator/w4` | float | 0.10 | [0, 10] | - | Weight for battery penalty |
| `allocator/cooldown_threshold` | float | 0.15 | [0, 1.0] | utility pts | Min utility jump to override cooldown |
| `allocator/cooldown_duration` | float | 8.0 | [1, 60] | s | Reallocation suppression time |
| `allocator/hysteresis` | float | 0.08 | [0, 1.0] | utility pts | Hysteresis to prevent oscillation |
| `allocator/cbba_bundle_size` | int | 1 | [1, 10] | - | Tasks per robot (currently 1) |
| `allocator/cbba_max_iter` | int | 50 | [5, 500] | - | Max CBBA iterations |

### Utility Function Formula

```
U(robot_r, patient_p) = w1 * risk 
                       + w2 * staleness_normalized 
                       - w3 * distance_normalized 
                       - w4 * (1 - battery)

where:
  staleness_normalized = min(1.5, staleness_sec / 60.0)
  distance_normalized = distance / 10.0
```

**Utility Range**: Approximately [−1.5, 2.0] (unbounded but typically in this range)

---

## Node Documentation

### Layer 1: Simulation-Only Nodes (Replaced in Week 3)

#### 1.1 **patient_simulator_node.py**

**Purpose**: Maintains hidden ground-truth physiology and risk per patient

**Node Name**: `patient_simulator_node`

**Parameters Read**:
```yaml
num_patients: int               # Number of patients (default: 5, range: [1, 100])
patient_positions: list         # Static patient coordinates
rng_seed: int                   # Random seed (default: 7)
rate: float                     # Update frequency Hz (default: 10.0, range: [1, 50])
risk_dynamics/*: (see above)    # All dynamics parameters
```

**Subscriptions**: None

**Publications**:
- `/patients/ground_truth` → `GroundTruthPatientArray` @ 10 Hz
- `/metrics/events` → `std_msgs/String` (JSON) @ variable

**Behavior**:
1. Creates `num_patients` patients at positions from `patient_positions`
2. Each patient has hidden state: HR, RR, HRV, Temp, Noise
3. Each tick (dt = 1/rate):
   - Add Gaussian drift to each vital with stddev `drift_std`
   - Clamp vitals to safe ranges (HR: [45, 160], RR: [8, 36], Temp: [35, 40.5], etc.)
   - With probability `spike_prob`, trigger a spike event (add large transient to vitals)
   - Publish ground truth to logger (NOT to allocator)

**Key Functions**:
- `Patient.step(dt, now, params, rng)` → increments hidden state, returns True if spike
- `Patient.true_risk()` → computes fused NEWS2 score from current physiology

**Clamp Ranges**:
```python
hr_clamped = clamp(hr, 45.0, 160.0)          # Beats per minute
rr_clamped = clamp(rr, 8.0, 36.0)            # Breaths per minute
hrv_clamped = clamp(hrv, 0.0, 1.0)           # Normalized proxy
temp_clamped = clamp(temp, 35.0, 40.5)       # Celsius
noise_clamped = clamp(noise, 30.0, 80.0)     # Decibels
```

**Event Log Format** (published to `/metrics/events`):
```json
{"event":"spike","t":1234.5,"patient_id":2}
```

**Initialization**:
```python
Patient.__init__(pid, x, y, params, rng):
  hr = hr_base + U(−4, +4)
  rr = rr_base + U(−1.5, +1.5)    # U = uniform
  hrv = hrv_base + U(−0.05, +0.05)
  temp = temp_base + U(−0.2, +0.2)
  noise = noise_base + U(−2, +2)
```

---

#### 1.2 **robot_kinematics_sim_node.py**

**Purpose**: Simulates 2D differential-drive robot kinematics

**Node Name**: `robot_kinematics_sim_node` (namespaced per robot)

**Parameters Read**:
```yaml
robot_id: int                   # Robot index (0-based, mandatory via ~robot_id)
robot_start_poses: list         # Initial [x, y, yaw] per robot
world_frame: string             # TF root frame (default: "map")
battery_full: float             # Initial battery (default: 1.0, range: [0, 1])
battery_drain_per_mps: float    # Drain coefficient (default: 0.004)
rate: float                     # Update frequency Hz (default: 20.0, range: [5, 100])
```

**Subscriptions**:
- `cmd_vel` ← `geometry_msgs/Twist` (linear.x = v, angular.z = ω)

**Publications**:
- `odom` → `nav_msgs/Odometry` @ update rate
- `battery` → `std_msgs/Float32` @ update rate
- `/tf` → `tf2_msgs/TFMessage` (broadcasts transform) @ update rate

**Kinematic Model**:
```
x_{k+1} = x_k + v * cos(yaw_k) * dt
y_{k+1} = y_k + v * sin(yaw_k) * dt
yaw_{k+1} = yaw_k + ω * dt

battery_{k+1} = max(0, battery_k - drain * (|v| + 0.15 * |ω|) * dt)
```

**Clamping**:
- Battery: `[0.0, 1.0]`

**Transform Tree**:
```
/map (world_frame)
  └─ /robot_i/base_link (position and yaw from odometry)
```

**Initial Pose Fallback**:
If `robot_id` exceeds `robot_start_poses` length, default to (0.5, 0.5 + robot_id, 0.0)

---

#### 1.3 **rppg_sensor_sim_node.py**

**Purpose**: Simulated rPPG (remote photoplethysmography) camera sensor

**Node Name**: `rppg_sensor_sim_node` (namespaced per robot)

**Parameters Read**:
```yaml
robot_id: int                   # Robot index (mandatory via ~robot_id)
sensing_range: float            # Max detection distance (default: 2.0, range: [0.5, 10.0] m)
sensor_noise/hr_std: float      # HR noise stddev (default: 2.5, range: [0, 10] bpm)
sensor_noise/rr_std: float      # RR noise stddev (default: 0.8, range: [0, 5] breaths/min)
sensor_noise/hrv_std: float     # HRV noise stddev (default: 0.04, range: [0, 0.2])
rate: float                     # Update frequency Hz (default: 5.0, range: [0.5, 20])
```

**Subscriptions**:
- `odom` ← `nav_msgs/Odometry` (robot position)
- `/patients/ground_truth` ← `GroundTruthPatientArray` (hidden state)

**Publications**:
- `vitals_raw` → `VitalsReading` @ rate (only when patient in range)

**Behavior**:
1. Read current robot position (x, y) from odometry
2. Find nearest patient within `sensing_range`
3. If found: add Gaussian noise to that patient's true vitals, publish
4. If not found: publish nothing

**Nearest Patient Search**:
```python
distance_to_patient_i = sqrt((x - p_i.x)^2 + (y - p_i.y)^2)
if distance <= sensing_range:
    publish_noisy_reading()
else:
    skip  # No publication
```

**Noise Model**:
```
hr_observed = hr_true + N(0, hr_std)
rr_observed = rr_true + N(0, rr_std)
hrv_observed = clamp(hrv_true + N(0, hrv_std), 0, 1)
```

---

#### 1.4 **env_sensor_sim_node.py**

**Purpose**: Simulated environmental sensors (temperature, noise)

**Node Name**: `env_sensor_sim_node` (namespaced per robot)

**Parameters Read**:
```yaml
robot_id: int                   # Robot index (mandatory via ~robot_id)
env_zone_radius: float          # Zone extent (default: 3.0, range: [0.5, 15] m)
sensor_noise/temp_std: float    # Temperature noise (default: 0.15, range: [0, 1.0] °C)
sensor_noise/noise_std: float   # Noise sensor uncertainty (default: 1.5, range: [0, 10] dB)
rate: float                     # Update frequency Hz (default: 2.0, range: [0.5, 10])
```

**Subscriptions**:
- `odom` ← `nav_msgs/Odometry` (robot position)
- `/patients/ground_truth` ← `GroundTruthPatientArray` (true env values)

**Publications**:
- `env_raw` → `EnvReading` @ rate (continuous, even if no patient detected)

**Behavior**:
1. If no ground truth received: publish default ambient (22°C, 40 dB) with noise
2. Find nearest patient within `env_zone_radius`
3. If found: publish that patient's (temp, noise) + Gaussian noise
4. If not found: publish ambient (22°C, 40 dB) + noise

**Default Ambient**:
```
temperature_c = 22.0 + N(0, temp_std)
noise_db = 40.0 + N(0, noise_std)
patient_id = -1
```

---

### Layer 2: Decision-Making Nodes (Identical in Real Hardware)

#### 2.1 **risk_fusion_node.py**

**Purpose**: Fuses vitals and environment into NEWS2-style risk score

**Node Name**: `risk_fusion_node` (namespaced per robot)

**Parameters Read**:
```yaml
robot_id: int                   # Robot index (mandatory via ~robot_id)
```

**Subscriptions**:
- `vitals_raw` ← `VitalsReading` (per-robot, high priority)
- `env_raw` ← `EnvReading` (per-robot, cached)

**Publications**:
- `risk_reading` → `RiskReading` @ variable (only when vitals arrive)

**Behavior**:
1. Wait for a vitals reading (blocks until first vitals)
2. Use most recent env reading (or default if none received)
3. Call `fuse_risk(hr, rr, hrv, temp, noise)` → fused score ∈ [0, 1]
4. Publish RiskReading with robot_id, patient_id, risk_value

**Default Environment** (if no env reading):
```
temp = 36.8 °C
noise = 42.0 dB
```

**Fuse Risk Algorithm** (see `risk_model.py`):
- NEWS2 components: HR bands, RR bands, Temp bands → {0,1,2,3} each
- HRV proxy: [0, 0.25) → 0; [0.25, 0.5) → 1; etc.
- Noise: [30, 45) → 0; [45, 55) → 1; etc.
- Sum all components, normalize by max (12.0) to get [0, 1]

---

#### 2.2 **patient_knowledge_base_node.py**

**Purpose**: Maintains the single source of truth for the allocator's belief state

**Node Name**: `patient_knowledge_base_node` (central, no namespace)

**Parameters Read**:
```yaml
num_robots: int                 # Number of risk_reading subscribers (default: 3, range: [1, 20])
num_patients: int               # Number of belief states to maintain (default: 5, range: [1, 100])
patient_positions: list         # Static positions (one per patient)
rate: float                     # Publish frequency Hz (default: 2.0, range: [0.5, 10])
```

**Subscriptions**:
- `/robot_i/risk_reading` ← `RiskReading` (from each robot i ∈ [0, num_robots))

**Publications**:
- `/patients/belief_state` → `PatientBeliefArray` @ rate

**Behavior**:
1. Maintain a belief state per patient: (last_known_risk, last_update_time, staleness)
2. For each incoming risk reading:
   - Update that patient's last_known_risk
   - Set last_update_time to current time
   - Reset staleness_sec to 0
3. At publish frequency:
   - For each patient:
     - If ever observed: staleness = now - last_update_time
     - If never observed: staleness = now - node_start_time
   - Publish PatientBeliefArray with all states

**Staleness Behavior**:
```
if patient_ever_observed:
    staleness = now - last_update_time    (grows from 0)
else:
    staleness = now - node_start_time     (grows from node start)
```

**Use Case**: The allocator reads this topic (NOT ground truth) to make decisions

---

#### 2.3 **task_allocator_node.py**

**Purpose**: Centralized task allocation using round-robin, greedy, or greedy heuristic

**Node Name**: `task_allocator_node` (central, no namespace)

**Parameters Read**:
```yaml
num_robots: int                 # Number of robots (default: 3, range: [1, 20])
allocator_mode: string          # "round_robin" | "greedy" | "cbba"
allocator/w1: float             # Risk weight (default: 1.00, range: [0, 10])
allocator/w2: float             # Staleness weight (default: 0.60, range: [0, 10])
allocator/w3: float             # Distance penalty (default: 0.35, range: [0, 10])
allocator/w4: float             # Battery penalty (default: 0.10, range: [0, 10])
allocator/cooldown_threshold: float  # Min utility jump (default: 0.15, range: [0, 1.0])
allocator/cooldown_duration: float   # Suppression time (default: 8.0, range: [1, 60] s)
allocator/hysteresis: float     # Oscillation prevention (default: 0.08, range: [0, 1.0])
rate: float                     # Decision frequency Hz (default: 2.0, range: [0.5, 10])
```

**Subscriptions**:
- `/patients/belief_state` ← `PatientBeliefArray` (one per decision tick)
- `/robot_i/odom` ← `nav_msgs/Odometry` (per robot, for position)
- `/robot_i/battery` ← `std_msgs/Float32` (per robot, normalized [0, 1])

**Publications**:
- `/robot_i/assigned_patient` → `TaskAssignment` (per robot, latched)
- `/metrics/events` → `std_msgs/String` (JSON on reassignment)

**Allocation Modes**:

**Mode 1: round_robin**
```
for each robot r in [0, num_robots):
    p = (rr_tick + r) % num_patients
    propose patient p to robot r
    apply cooldown check; if blocked, keep old assignment
    publish assignment
rr_tick += 1
```
- Simple, predictable; no optimization

**Mode 2: greedy** (default)
```
1. For each (robot, patient) pair, compute utility matrix
2. Sort all pairs by utility (descending)
3. Greedily select highest-utility pairs that don't share robot/patient
4. Apply cooldown check per robot
5. Publish assignments
```
- Locally optimal; can perform well with good weights

**Mode 3: cbba** (decentralized)
```
Task_allocator_node does NOT participate in CBBA mode.
Instead, each cbba_bidding_node runs decentralized consensus.
This allocator idles when allocator_mode == "cbba".
```

**Cooldown Logic**:
```python
if now - assign_time < cooldown_duration:
    # Still in cooldown
    if new_utility - old_utility < cooldown_threshold:
        # Not a big enough improvement; block the change
        return True
    else:
        # Large spike; allow override
        return False
else:
    # Out of cooldown; allow reassignment with hysteresis
    if new_pid != old_pid and new_utility < old_utility + hysteresis:
        return True
    else:
        return False
```

**Event Format** (on reassignment):
```json
{
  "event": "reassignment",
  "t": 1234.56,
  "robot_id": 0,
  "assigned_patient_id": 2,
  "allocator_mode": "greedy"
}
```

---

#### 2.4 **cbba_bidding_node.py**

**Purpose**: Decentralized task allocation using Consensus-Based Bundle Algorithm

**Node Name**: `cbba_bidding_node` (namespaced per robot when active)

**Parameters Read**:
```yaml
robot_id: int                   # Robot index (mandatory via ~robot_id)
num_patients: int               # Task count (default: 5, range: [1, 100])
allocator/w1: float             # Risk weight (default: 1.00)
allocator/w2: float             # Staleness weight (default: 0.60)
allocator/w3: float             # Distance penalty (default: 0.35)
allocator/w4: float             # Battery penalty (default: 0.10)
allocator/cbba_bundle_size: int # Tasks per robot (currently 1, range: [1, 10])
allocator/cooldown_duration: float  # Reallocation suppression (default: 8.0 s)
allocator_mode: string          # Must be "cbba" to run (checked each tick)
rate: float                     # Bidding frequency Hz (default: 4.0, range: [1, 20])
```

**Subscriptions**:
- `/patients/belief_state` ← `PatientBeliefArray`
- `odom` ← `nav_msgs/Odometry` (robot position)
- `battery` ← `std_msgs/Float32` (robot battery level)
- `/cbba/bid_broadcast` ← `CBBABid` (broadcast from all robots)

**Publications**:
- `assigned_patient` → `TaskAssignment` (per robot, latched)
- `/cbba/bid_broadcast` → `CBBABid` (broadcast to all)
- `/metrics/events` → `std_msgs/String` (JSON on reassignment)

**CBBA Algorithm** (per tick):
1. **Phase 1 - Bundle Building**: Compute utility score for each patient (task)
   ```
   score[j] = assignment_utility(risk, staleness, distance, battery, w1-w4)
   ```
   Greedily add the highest-scoring patient not yet in bundle (up to bundle_size = 1)

2. **Phase 2 - Bid Broadcasting**: Publish current bid for each task in bundle
   ```
   CBBABid(robot_id=self, patient_id=j, bid_value=score[j], timestamp=now)
   ```

3. **Phase 3 - Remote Bid Processing**: Apply incoming bids from other robots
   ```
   if remote_bid_value > local_winning_bid:
       transfer task ownership to remote robot
       remove task from local bundle if held
   else if tie (same bid value):
       lower robot_id wins (deterministic)
   ```

4. **Phase 4 - Assignment Publication**: Publish assigned task (bundle[0] if any)

**Conflict Resolution**:
- Highest bid wins
- Ties broken by lower robot_id (deterministic, avoids deadlock)
- A robot can only hold tasks it's currently winning

**Key Classes** (in `cbba_core.py`):
```python
class CBBAAgent:
  bundle[]                # Tasks this robot claims
  winning_bids[]          # Bid values for each task
  winning_agents[]        # Which robot currently wins each task

  def build_bundle(scores)      # Phase 1: add best uncontested task
  def apply_remote_bid(...)     # Phase 3: process incoming bid
  def assigned_task()           # Get primary task (bundle[0])
```

---

#### 2.5 **waypoint_navigator_node.py**

**Purpose**: Proportional go-to-goal controller toward assigned patient

**Node Name**: `waypoint_navigator_node` (namespaced per robot)

**Parameters Read**:
```yaml
robot_id: int                   # Robot index (mandatory via ~robot_id)
navigator/arrive_radius: float  # Stop distance (default: 0.4, range: [0.1, 2.0] m)
navigator/kp_lin: float         # Linear gain (default: 0.8, range: [0.1, 2.0])
navigator/kp_ang: float         # Angular gain (default: 2.0, range: [0.5, 5.0])
navigator/v_max: float          # Max velocity (default: 0.6, range: [0.1, 1.5] m/s)
navigator/w_max: float          # Max angular velocity (default: 1.2, range: [0.5, 3.0] rad/s)
dwell_time_required: float      # Dwell at patient (default: 3.0, range: [0.1, 30] s)
rate: float                     # Control frequency Hz (default: 20.0, range: [5, 100])
```

**Subscriptions**:
- `assigned_patient` ← `TaskAssignment` (target patient ID)
- `/patients/belief_state` ← `PatientBeliefArray` (patient positions)
- `odom` ← `nav_msgs/Odometry` (current pose)

**Publications**:
- `cmd_vel` → `geometry_msgs/Twist` (velocity commands)
- `/metrics/events` → `std_msgs/String` (JSON on visit completion)

**Controller Logic**:
```python
if assigned_patient < 0:
    publish zero velocity
    return

target_pos = belief[assigned_patient].position
dx = target.x - robot.x
dy = target.y - robot.y
distance = sqrt(dx^2 + dy^2)

if distance <= arrive_radius:
    # At target
    if dwell_t0 is None:
        dwell_t0 = now
    if (now - dwell_t0) >= dwell_time_required:
        published "visit" event
        visited = True
    publish zero velocity
else:
    # Moving toward target
    heading = atan2(dy, dx)
    heading_error = wrap_angle(heading - robot.yaw)
    
    # Don't move forward if badly misaligned
    if |heading_error| > π/2:
        v = 0
    else:
        scale = min(1.0, distance / slow_radius)  # slow_radius = 1.0
        v = kp_lin * distance * scale * cos(heading_error)
        v = clamp(v, -v_max, v_max)
    
    omega = clamp(kp_ang * heading_error, -w_max, w_max)
    
    publish (v, omega)
    reset dwell timer
```

**Visit Event** (published when dwell time expires):
```json
{
  "event": "visit",
  "t": 1234.56,
  "robot_id": 0,
  "patient_id": 2
}
```

**Slow Radius**: 1.0 m (reduces velocity when > 1.0 m away to allow smoother approach)

---

### Layer 3: Support Nodes

#### 3.1 **rviz_marker_publisher_node.py**

**Purpose**: Visualizes robots and patients in RViz, color-coded by risk

**Node Name**: `rviz_marker_publisher_node` (central, no namespace)

**Parameters Read**:
```yaml
num_robots: int                 # Number of robot markers (default: 3)
world_frame: string             # TF frame for markers (default: "map")
```

**Subscriptions**:
- `/patients/belief_state` ← `PatientBeliefArray` (risk values, staleness)
- `/robot_i/odom` ← `nav_msgs/Odometry` (per robot position/orientation)
- `/robot_i/assigned_patient` ← `TaskAssignment` (per robot target)

**Publications**:
- `/visualization_marker_array` → `visualization_msgs/MarkerArray` @ 10 Hz

**Marker Types**:
1. **Patients**: Cylinders at (x, y), color gradient:
   - Green (risk → 0)
   - Yellow (risk → 0.5)
   - Red (risk → 1)
   - More transparent if staleness > 15 seconds

2. **Patient Labels**: Text "P{id} r={risk:.2f} s={staleness:.0f}s" above each patient

3. **Robots**: Blue arrows at robot position, pointing in heading direction

4. **Assignment Lines**: Line strips from each robot to assigned patient

**Color Mapping**:
```python
def _risk_color(risk, stale=False):
    r = clamp(risk, 0, 1)
    color_r = r
    color_g = 1.0 - 0.7 * r
    color_b = 0.15 * (1.0 - r)
    alpha = 0.45 if stale else 0.95
    return (color_r, color_g, color_b, alpha)
```

---

#### 3.2 **metrics_logger_node.py**

**Purpose**: Logs all events to CSV for offline analysis

**Node Name**: `metrics_logger_node` (central, no namespace)

**Parameters Read**:
```yaml
log_dir: string                 # CSV output directory
                                # Default: ~/mrta_vitalsign/src/mrta_simulation/results/logs
run_tag: string                 # Experiment label (default: timestamp YYYYMMDD_HHMMSS)
allocator_mode: string          # (read once, incorporated in filenames)
results_dir: string             # Alternative results root
experiment_duration: float      # Auto-stop experiment after N seconds (default: 0 = never)
num_robots: int                 # Number of robot subscribers
```

**Subscriptions**:
- `/patients/ground_truth` ← `GroundTruthPatientArray` (truth every 100ms)
- `/patients/belief_state` ← `PatientBeliefArray` (belief state every 500ms)
- `/metrics/events` ← `std_msgs/String` (variable rate)
- `/robot_i/risk_reading` ← `RiskReading` (per robot, variable)
- `/robot_i/odom` ← `nav_msgs/Odometry` (per robot)
- `/robot_i/assigned_patient` ← `TaskAssignment` (per robot)

**CSV Files Generated** (prefix `{run_tag}_{allocator_mode}`):

| File | Columns | Purpose |
|------|---------|---------|
| `_risk.csv` | t, robot_id, patient_id, risk_value | All risk observations |
| `_ground_truth.csv` | t, patient_id, true_risk, x, y, heart_rate, resp_rate, hrv_proxy, temperature_c, noise_db | Hidden state (eval only) |
| `_belief.csv` | t, patient_id, last_known_risk, last_update_time, staleness_sec | Allocator's view |
| `_poses.csv` | t, robot_id, x, y | Robot trajectories |
| `_assignments.csv` | t, robot_id, assigned_patient_id, allocator_mode | Task allocations |
| `_events.csv` | t, payload | JSON spike/reassign/visit events |

**Throttling**:
- Ground truth: max once per 100ms
- Belief state: max once per 500ms
- Other topics: every message (with deduplication for repeated beliefs)

**Auto-Stop**:
If `experiment_duration > 0`, node publishes signal after N seconds and exits

---

## Utility Modules

### 4.1 **risk_model.py** - NEWS2 Scoring

**Functions**:

```python
def fuse_risk(heart_rate, resp_rate, hrv_proxy, temperature_c, noise_db) -> float
```
Returns fused risk ∈ [0, 1]

**Algorithm**:
1. Compute NEWS2 components for HR, RR, Temp (each in {0,1,2,3})
2. Compute HRV component from proxy: [0, 0.25)→0, [0.25,0.5)→1, etc.
3. Compute noise component: [30,45)→0, [45,55)→1, etc.
4. Sum all components; normalize by NEWS2_MAX (12.0)

**Component Scores**:

**Heart Rate (bpm)**:
| Range | Score |
|-------|-------|
| [0, 41) | 3 |
| [41, 51) | 1 |
| [51, 91) | 0 |
| [91, 111) | 1 |
| [111, 131) | 2 |
| [131, ∞) | 3 |

**Respiration Rate (breaths/min)**:
| Range | Score |
|-------|-------|
| [0, 9) | 3 |
| [9, 12) | 1 |
| [12, 21) | 0 |
| [21, 25) | 2 |
| [25, ∞) | 3 |

**Temperature (°C)**:
| Range | Score |
|-------|-------|
| [0, 35.1) | 3 |
| [35.1, 36.1) | 1 |
| [36.1, 38.1) | 0 |
| [38.1, 39.1) | 1 |
| [39.1, ∞) | 2 |

**HRV Proxy (normalized [0, 1])**:
| Range | Score |
|-------|-------|
| [0, 0.25) | 0 |
| [0.25, 0.5) | 1 |
| [0.5, 0.75) | 2 |
| [0.75, 1.0] | 3 |

**Environmental Noise (dB)**:
| Range | Score |
|-------|-------|
| [30, 45) | 0 |
| [45, 55) | 1 |
| [55, 65) | 2 |
| [65, ∞) | 3 |

**Output Range**: [0, 1] after normalization

---

### 4.2 **cbba_core.py** - CBBA Algorithm

**Class**: `CBBAAgent(agent_id, n_tasks, bundle_size=1)`

**Attributes**:
```python
bundle: list              # Task IDs this agent currently holds (length ≤ bundle_size)
winning_bids[j]: float    # Best known bid for task j
winning_agents[j]: int    # Agent ID holding task j
```

**Methods**:

```python
def build_bundle(scores: list[float]) -> bool
```
Phase 1: Greedily add tasks to bundle
- `scores[j]` = local utility for task j
- Add highest-utility task not in bundle if score > current winning bid
- Returns True if bundle changed

```python
def apply_remote_bid(other_id: int, task_id: int, bid_value: float) -> bool
```
Phase 2: Process incoming bid, update conflicts
- If remote bid strictly higher: transfer ownership, remove from local bundle if held
- If tie: lower robot_id wins (deterministic)
- Returns True if this agent lost a task

```python
def assigned_task() -> int
```
Returns bundle[0] if bundle non-empty, else -1 (idle)

**Centralized Solver**:
```python
def solve_cbba(score_matrix: list[list[float]], bundle_size=1, max_iter=50) -> list[int]
```
- Input: score_matrix[agent_id][task_id] = utility
- Output: assigned_task_id per agent (-1 if idle)
- Runs max_iter consensus rounds

**Convergence**: Guaranteed within max_iter if bundle_size small (proof via [Choi et al. 2009])

---

### 4.3 **geometry_utils.py** - Math Helpers

**Distance**:
```python
def dist2d(ax, ay, bx, by) -> float
```
Euclidean distance: √((bx−ax)² + (by−ay)²)

**Angle Wrapping**:
```python
def wrap_angle(angle) -> float
```
Wraps to (−π, π]

**Quaternion Conversions**:
```python
def yaw_from_quaternion(x, y, z, w) -> float
```
Extracts yaw from unit quaternion

```python
def quaternion_from_yaw(yaw) -> tuple(x, y, z, w)
```
Builds unit quaternion with given yaw (roll=pitch=0)

**Nearest Neighbor**:
```python
def nearest_index(ax, ay, points: list[tuple], max_range=None) -> (int, float)
```
Returns (index, distance) of closest point, or (-1, inf) if none within max_range

**Go-To-Goal Controller**:
```python
def go_to_goal(x, y, yaw, gx, gy, kp_lin=0.8, kp_ang=2.0,
               v_max=0.6, w_max=1.2, arrive_radius=0.35, slow_radius=1.0) -> (v, omega, arrived)
```
Proportional control toward goal:
- Returns (linear_velocity, angular_velocity, at_goal_flag)
- Slows approach within slow_radius
- Stops at arrive_radius

**Utility Function**:
```python
def assignment_utility(risk, staleness_sec, distance, battery_frac,
                       w1, w2, w3, w4,
                       staleness_norm=60.0, distance_norm=10.0) -> float
```
Computes per-(robot, patient) utility for allocation:
```
U = w1 * risk 
  + w2 * min(1.5, staleness_sec/60) 
  - w3 * (distance/10) 
  - w4 * (1 - battery)
```

**Range**: Approximately [−1.5, 2.0]

---

## Command Reference

### ROS Launch Commands

#### Launch Entire Simulation
```bash
roslaunch mrta_simulation simulation.launch \
  num_robots:=3 \
  num_patients:=5 \
  allocator_mode:=greedy
```

**Arguments**:
- `num_robots` (int, default: 3, range: 1–20)
- `num_patients` (int, default: 5, range: 1–100)
- `allocator_mode` (string, default: "greedy", options: "round_robin", "greedy", "cbba")

---

#### Launch Robots Only
```bash
roslaunch mrta_simulation robots.launch.xml \
  num_robots:=3 \
  robot_spawn_rate:=0.5
```

**Arguments**:
- `num_robots` (int)
- `robot_spawn_rate` (float, Hz for sequential spawning)

---

#### Run Batch Experiments
```bash
roslaunch mrta_simulation experiment_batch.launch \
  num_robots_min:=2 \
  num_robots_max:=5 \
  num_patients:=5 \
  modes:="greedy cbba" \
  runs_per_config:=3 \
  experiment_duration:=300.0 \
  run_tag:="week1_baseline"
```

**Arguments**:
- `num_robots_min` (int, default: 2)
- `num_robots_max` (int, default: 5)
- `num_patients` (int, default: 5)
- `modes` (string, space-separated, default: "greedy")
- `runs_per_config` (int, default: 1)
- `experiment_duration` (float, seconds, default: 600)
- `run_tag` (string, default: timestamp)

---

### ROS Node Commands (Manual)

#### Start Single Patient Simulator
```bash
rosrun mrta_simulation patient_simulator_node.py
```

**Parameter Overrides**:
```bash
rosrun mrta_simulation patient_simulator_node.py _rate:=20.0
```

---

#### Start Robot Kinematics
```bash
rosrun mrta_simulation robot_kinematics_sim_node.py _robot_id:=0
```

**Required Parameters** (via param server or direct):
- `~robot_id` (int): Robot index

**Optional**:
- `~rate` (float, default: 20.0)

---

#### Start rPPG Sensor (per robot)
```bash
rosrun mrta_simulation rppg_sensor_sim_node.py _robot_id:=0
```

---

#### Start Risk Fusion (per robot)
```bash
rosrun mrta_simulation risk_fusion_node.py _robot_id:=0
```

---

#### Start Knowledge Base
```bash
rosrun mrta_simulation patient_knowledge_base_node.py
```

---

#### Start Allocator
```bash
rosrun mrta_simulation task_allocator_node.py
```

---

#### Start CBBA Bidder (per robot, only if allocator_mode=cbba)
```bash
rosrun mrta_simulation cbba_bidding_node.py _robot_id:=0
```

---

#### Start Navigator (per robot)
```bash
rosrun mrta_simulation waypoint_navigator_node.py _robot_id:=0
```

---

#### Start Metrics Logger
```bash
rosrun mrta_simulation metrics_logger_node.py \
  _log_dir:=/tmp/mrta_logs \
  _run_tag:=experiment_001
```

---

#### Start RViz Visualization
```bash
rosrun rviz rviz -d src/mrta_simulation/rviz/mrta_sim.rviz
```

---

### ROS Parameter Commands

#### Load Parameters from YAML
```bash
rosparam load src/mrta_simulation/config/sim_params.yaml
rosparam load src/mrta_simulation/config/risk_dynamics.yaml
rosparam load src/mrta_simulation/config/allocator_params.yaml
```

#### Set Single Parameter
```bash
rosparam set /allocator_mode greedy
rosparam set /num_robots 5
rosparam set /allocator/w1 1.5
```

#### Get Parameter Value
```bash
rosparam get /allocator_mode
rosparam get /num_robots
rosparam get /allocator
```

#### List All Parameters
```bash
rosparam list
```

---

### ROS Topic Commands

#### Echo Topic
```bash
rostopic echo /patients/ground_truth
rostopic echo /patients/belief_state
rostopic echo /robot_0/risk_reading
rostopic echo /robot_0/assigned_patient
```

#### Publish to Topic (manual testing)
```bash
rostopic pub /robot_0/cmd_vel geometry_msgs/Twist "{linear: {x: 0.5, y: 0, z: 0}, angular: {x: 0, y: 0, z: 0.2}}"
```

#### Topic Info
```bash
rostopic info /patients/belief_state
rostopic hz /patients/belief_state
rostopic bw /patients/belief_state
```

---

### ROS Message Commands

#### Show Message Definition
```bash
rosmsg show mrta_msgs/RiskReading
rosmsg show mrta_msgs/PatientBeliefArray
rosmsg show mrta_msgs/TaskAssignment
```

#### List All Custom Messages
```bash
rosmsg list | grep mrta_msgs
```

---

### Build Commands

#### Build Workspace
```bash
cd ~/mrta_vitalsign
catkin_make
```

#### Build Single Package
```bash
catkin_make --pkg mrta_msgs
catkin_make --pkg mrta_simulation
```

#### Clean Build
```bash
catkin_make clean
catkin_make
```

#### Verbose Build
```bash
catkin_make -DCMAKE_BUILD_TYPE=Debug -v
```

---

### Python Module Import (for testing)

```python
import rospy
from mrta_simulation.risk_model import fuse_risk, news2_components
from mrta_simulation.geometry_utils import go_to_goal, dist2d, assignment_utility
from mrta_simulation.cbba_core import CBBAAgent, solve_cbba

# Test risk fusion
risk = fuse_risk(hr=110, rr=20, hrv=0.3, temp=37.5, noise=50)
# Output: ~0.417 (2 high HR + 0 RR + 0 temp + 1 HRV + 1 noise = 4 / 12 = 0.333)

# Test utility
u = assignment_utility(risk=0.5, staleness_sec=30, distance=2.0, battery_frac=0.8,
                       w1=1.0, w2=0.6, w3=0.35, w4=0.1)
# Output: 0.5*1.0 + 0.5*0.6 - 0.2*0.35 - 0.2*0.1 = 0.698

# Test CBBA
scores = [[0.8, 0.3, 0.5], [0.2, 0.9, 0.4], [0.6, 0.4, 0.7]]  # 3 agents, 3 tasks
result = solve_cbba(scores, bundle_size=1, max_iter=50)
# Output: assignment per agent (e.g., [0, 1, 2])
```

---

## Topic and Service Overview

### Complete Topic List

| Topic | Type | Dir | Freq (Hz) | Publisher | Subscribers | Description |
|-------|------|-----|-----------|-----------|-------------|-------------|
| `/patients/ground_truth` | GroundTruthPatientArray | Pub | 10 | patient_simulator | logger only | Hidden state |
| `/patients/belief_state` | PatientBeliefArray | Pub | 2 | patient_knowledge_base | allocator, navigator, rviz | Allocator's view |
| `/robot_i/odom` | nav_msgs/Odometry | Pub | 20 | kinematics_sim | navigator, allocator, rviz | Robot pose |
| `/robot_i/battery` | std_msgs/Float32 | Pub | 20 | kinematics_sim | allocator, cbba | Battery [0, 1] |
| `/robot_i/cmd_vel` | geometry_msgs/Twist | Pub | 20 | navigator | kinematics_sim | Velocity commands |
| `/robot_i/vitals_raw` | VitalsReading | Pub | 5 | rppg_sensor_sim | risk_fusion | Raw sensor data |
| `/robot_i/env_raw` | EnvReading | Pub | 2 | env_sensor_sim | risk_fusion | Env sensor data |
| `/robot_i/risk_reading` | RiskReading | Pub | 5 | risk_fusion | knowledge_base, logger | Fused risk |
| `/robot_i/assigned_patient` | TaskAssignment | Pub | 2 | allocator/cbba | navigator | Task assignment |
| `/cbba/bid_broadcast` | CBBABid | Pub | 4 | cbba_bidder (all) | cbba_bidder (all) | CBBA consensus |
| `/metrics/events` | std_msgs/String | Pub | var | all | logger | JSON events |
| `/tf` | tf2_msgs/TFMessage | Pub | 20 | kinematics_sim | tf | Transform tree |
| `/visualization_marker_array` | visualization_msgs/MarkerArray | Pub | 10 | rviz_marker | RViz | Markers |

### Service Calls
- None; all communication via topics and parameters

### Namespacing Scheme
```
/robot_i/*              # Per-robot topics (i ∈ [0, num_robots))
/patients/*             # Global patient-related topics
/cbba/*                 # Decentralized algorithm topics
/metrics/*              # Logging topics
/                       # Global parameters
```

---

## Configuration Value Ranges Summary

| Parameter | Min | Default | Max | Unit | Notes |
|-----------|-----|---------|-----|------|-------|
| num_robots | 1 | 3 | 20 | - | Per experiment |
| num_patients | 1 | 5 | 100 | - | Static |
| sensing_range | 0.5 | 2.0 | 10.0 | m | rPPG range |
| env_zone_radius | 0.5 | 3.0 | 15.0 | m | Env sensor zone |
| dwell_time_required | 0.1 | 3.0 | 30.0 | s | Visit threshold |
| battery_drain_per_mps | 0 | 0.004 | 0.1 | 1/m | Depletion rate |
| drift_std | 0 | 0.08 | 0.5 | per-step | Physiology drift |
| spike_prob | 0 | 0.002 | 0.05 | prob/tick | Risk spike likelihood |
| spike_magnitude | 0 | 0.45 | 1.0 | factor | Spike size multiplier |
| spike_duration | 5 | 25.0 | 60 | s | Spike persistence |
| allocator_mode | - | "greedy" | - | - | round_robin/greedy/cbba |
| w1 (risk) | 0 | 1.00 | 10 | - | Utility weight |
| w2 (staleness) | 0 | 0.60 | 10 | - | Utility weight |
| w3 (distance) | 0 | 0.35 | 10 | - | Utility weight |
| w4 (battery) | 0 | 0.10 | 10 | - | Utility weight |
| cooldown_threshold | 0 | 0.15 | 1.0 | utility | Min improvement |
| cooldown_duration | 1 | 8.0 | 60 | s | Realloc suppression |
| hysteresis | 0 | 0.08 | 1.0 | utility | Oscillation prevention |
| v_max | 0.1 | 0.6 | 1.5 | m/s | Max linear velocity |
| w_max | 0.5 | 1.2 | 3.0 | rad/s | Max angular velocity |
| kp_lin | 0.1 | 0.8 | 2.0 | - | Linear control gain |
| kp_ang | 0.5 | 2.0 | 5.0 | - | Angular control gain |
| arrive_radius | 0.1 | 0.4 | 2.0 | m | Goal distance |
| hr_std | 0 | 2.5 | 10 | bpm | HR sensor noise |
| rr_std | 0 | 0.8 | 5 | breaths/min | RR sensor noise |
| hrv_std | 0 | 0.04 | 0.2 | - | HRV sensor noise |
| temp_std | 0 | 0.15 | 1.0 | °C | Temp sensor noise |
| noise_std | 0 | 1.5 | 10 | dB | Noise sensor uncertainty |

---

## Typical Workflow for Running an Experiment

### Step 1: Build Workspace
```bash
cd ~/mrta_vitalsign
catkin_make
source devel/setup.bash
```

### Step 2: Configure Parameters
```bash
# Edit config files or set via launch args
rosparam load src/mrta_simulation/config/sim_params.yaml
rosparam load src/mrta_simulation/config/risk_dynamics.yaml
rosparam load src/mrta_simulation/config/allocator_params.yaml
```

### Step 3: Start Simulation
```bash
# All-in-one with defaults
roslaunch mrta_simulation simulation.launch

# Or custom configuration
roslaunch mrta_simulation simulation.launch \
  num_robots:=5 \
  num_patients:=8 \
  allocator_mode:=cbba
```

### Step 4: Monitor (in separate terminal)
```bash
# Watch belief state updates
rostopic echo /patients/belief_state

# Or open RViz
rviz -d src/mrta_simulation/rviz/mrta_sim.rviz
```

### Step 5: Run Experiments (batch)
```bash
roslaunch mrta_simulation experiment_batch.launch \
  runs_per_config:=5 \
  experiment_duration:=600.0 \
  run_tag:=week1_eval
```

### Step 6: Analyze Results
```bash
# CSV files generated in results/logs/{run_tag}_*
python3 << 'EOF'
import pandas as pd
import glob

csvs = glob.glob('src/mrta_simulation/results/logs/week1_eval*_risk.csv')
for csv in csvs:
    df = pd.read_csv(csv)
    print(df.describe())
EOF
```

---

## Notes and Caveats

1. **Ground Truth Never Seen by Allocator**: The `/patients/ground_truth` topic is published for the logger and sensor sim nodes only. The allocator subscribes to `/patients/belief_state` (which is based on observations).

2. **CBBA Node Suppression**: When `allocator_mode != "cbba"`, the `cbba_bidding_node` idles and does not publish assignments. The `task_allocator_node` handles all allocation.

3. **RNG Seed**: Set via `rng_seed` parameter (default 7) for reproducibility. Each node uses a different seed offset for independent randomness.

4. **Cooldown Logic**: Cooldown suppresses rapid reassignments for the first `cooldown_duration` seconds. Large utility jumps (≥ `cooldown_threshold`) override the cooldown. Hysteresis adds friction to prevent oscillation.

5. **Staleness Grows Unbounded**: For never-observed patients, staleness equals time since node start (motivating initial coverage). For observed patients, staleness is time since last update.

6. **Battery Drain**: Proportional to speed (linear velocity + rotational loss), not distance. A stationary robot does not drain battery.

7. **Message Retention**: `assigned_patient` messages are latched (persistent), so late subscribers see the last assignment immediately.

8. **Experiment Duration**: If `experiment_duration > 0`, the logger triggers a shutdown signal after N seconds.

---

## Appendix: Quick Reference

### File Locations
- **Config**: `src/mrta_simulation/config/`
- **Scripts**: `src/mrta_simulation/scripts/`
- **Utilities**: `src/mrta_simulation/src/mrta_simulation/`
- **Messages**: `src/mrta_msgs/msg/`
- **Launch**: `src/mrta_simulation/launch/`
- **Results**: `src/mrta_simulation/results/logs/`
- **RViz**: `src/mrta_simulation/rviz/mrta_sim.rviz`

### Key Classes & Functions
- **PatientSimulator**: Generates ground truth
- **RobotKinematics**: 2D diff-drive sim
- **RiskFusion**: NEWS2 scoring
- **KnowledgeBase**: Belief state maintenance
- **TaskAllocator**: Centralized allocation (round_robin, greedy)
- **CbbaBidder**: Decentralized CBBA
- **WaypointNavigator**: Go-to-goal control
- **news2_components()**: Compute risk factors
- **fuse_risk()**: Combined risk score
- **assignment_utility()**: Allocation heuristic
- **go_to_goal()**: Proportional control
- **CBBAAgent**: CBBA algorithm core

### Environment Variables (optional)
```bash
export ROS_PACKAGE_PATH=~/mrta_vitalsign/src:$ROS_PACKAGE_PATH
export ROS_LOG_DIR=/tmp/mrta_logs
```

---

**End of Documentation**
