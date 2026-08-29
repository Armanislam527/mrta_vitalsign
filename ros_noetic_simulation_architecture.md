# ROS Noetic Simulation — Full Architecture
## Multi-Robot Task Allocation for Continuous Vital-Sign Monitoring
### Target: Ubuntu 20.04 + ROS Noetic

---

## 1. Design principle: separate "sim world" from "real pipeline"

The single most important architectural decision: **nodes that fake the physical world are cleanly separable from nodes that make decisions.** The decision-making nodes (risk fusion, knowledge base, allocator, navigator) are the exact same code you'll run on real hardware in Week 3 — only the sensor input nodes get swapped from simulated to real. Keep this boundary strict from day one; it's what makes your Week-1 simulation results still valid evidence in your final paper.

```
[ SIMULATION-ONLY LAYER ]        [ REAL-OR-SIM LAYER — unchanged when you go to hardware ]
patient_simulator_node    -->    risk_fusion_node --> knowledge_base --> allocator --> navigator
robot_kinematics_sim_node --/         ^
rppg_sensor_sim_node      -----------/
env_sensor_sim_node       -----------/
```

---

## 2. Full node list

### A. World/simulation nodes (replaced by real sensors in Week 3)

**`patient_simulator_node`** (one instance, manages all patients)
- Maintains hidden ground-truth state per patient: true heart rate, true respiratory rate, true risk value, position (static).
- Evolves each patient's risk with slow random drift plus randomly-scheduled spikes (to create scenarios where reallocation is actually needed).
- Publishes ground truth for the logger only — **the allocator never sees this topic**. This is what makes the "staleness" problem in Section 4 real: robots only know what they last observed.

**`robot_kinematics_sim_node`** (one instance per robot, namespaced `/robot_i/`)
- Simple 2D differential-drive kinematic model (no physics engine needed for Week 1).
- Subscribes to velocity commands, integrates them into a pose, publishes odometry, broadcasts the TF frame.

**`rppg_sensor_sim_node`** (per robot)
- Checks whether a patient is within the robot's simulated camera range.
- If yes: reads that patient's true HR/RR from `patient_simulator_node`'s ground truth, adds Gaussian sensor noise, publishes a fake vitals reading. If no patient in range, publishes nothing (this "silence when nothing to see" behavior is what a real camera-based rPPG node would also do).
- **This node is deleted and replaced by your real rPPG pipeline in Week 3** — the message format it publishes must match exactly so nothing downstream changes.

**`env_sensor_sim_node`** (per robot)
- Publishes simulated room temperature/noise readings for whichever patient zone the robot currently occupies, with sensor noise added.

### B. Decision-making nodes (identical code, sim or real hardware)

**`risk_fusion_node`** (per robot)
- Subscribes to that robot's vitals + environment readings.
- Computes the NEWS2-inspired fused risk score.
- Publishes a `RiskReading` message only when a valid vitals reading exists (i.e., robot is actually observing a patient).

**`patient_knowledge_base_node`** (one central instance)
- The single most important node for your MRTA formulation: this is where "partial observability" lives.
- Subscribes to every robot's `risk_reading` topic.
- Maintains, per patient: last known risk value, timestamp of last update, and a computed staleness (time since last visit).
- Publishes the full belief-state array at a fixed rate (e.g., 2 Hz). **This — not the ground truth — is what the allocator uses.**

**`task_allocator_node`** (one central instance, OR one per robot for the decentralized version)
- Reads the belief-state array + current robot poses/battery.
- Mode selectable via ROS param: `round_robin`, `greedy`, or `cbba` (your novel contribution).
- Computes a per-(robot, patient) utility score, applies the cooldown/hysteresis check, and publishes a target patient assignment per robot.

**`cbba_bidding_node`** (per robot — only active when `allocator_mode:=cbba`)
- Implements decentralized consensus: each robot computes its own bid for each patient task, broadcasts it, listens to others' bids, and locally resolves conflicts using the standard CBBA bundle/conflict-resolution rules.
- This is the actual novel algorithmic contribution — keep it in its own node so you can benchmark it in isolation against the centralized baseline allocator.

**`waypoint_navigator_node`** (per robot)
- Subscribes to its assigned patient's known position.
- Runs a simple proportional go-to-goal controller, publishes velocity commands.

### C. Support nodes

**`rviz_marker_publisher_node`** — draws robots and patients in RViz, color-coded by current risk level (this is your live "coverage map" preview, and doubles as the prototype for your Week 4 dashboard).

**`metrics_logger_node`** — subscribes to everything, writes timestamped CSV rows for: risk readings, reassignment events, robot positions, ground truth (for offline accuracy scoring). This is what generates your Week 5/6 evaluation plots.

---

## 3. Message definitions (custom `.msg` files)

Package: `mrta_msgs`

```
VitalsReading.msg
------------------
Header header
int32 patient_id
float32 heart_rate      # bpm
float32 resp_rate       # breaths/min
float32 hrv_proxy       # unitless stress proxy

EnvReading.msg
------------------
Header header
int32 patient_id
float32 temperature_c
float32 noise_db

RiskReading.msg
------------------
Header header
int32 robot_id
int32 patient_id
float32 risk_value      # fused NEWS2-style score

PatientBeliefState.msg
------------------
int32 patient_id
float32 last_known_risk
float64 last_update_time
float32 staleness_sec
geometry_msgs/Point position

PatientBeliefArray.msg
------------------
PatientBeliefState[] patients

TaskAssignment.msg
------------------
int32 robot_id
int32 assigned_patient_id
float64 assignment_time
string allocator_mode    # "round_robin" | "greedy" | "cbba"

CBBABid.msg
------------------
int32 robot_id
int32 patient_id
float32 bid_value
float64 timestamp

GroundTruthPatientState.msg   (sim-only, logger use only)
------------------
int32 patient_id
float32 true_risk
geometry_msgs/Point position

GroundTruthPatientArray.msg
------------------
GroundTruthPatientState[] patients
```

---

## 4. Full topic table

| Topic | Type | Publisher | Subscriber(s) | Notes |
|---|---|---|---|---|
| `/robot_i/cmd_vel` | `geometry_msgs/Twist` | `waypoint_navigator_node` | `robot_kinematics_sim_node` | per-robot velocity command |
| `/robot_i/odom` | `nav_msgs/Odometry` | `robot_kinematics_sim_node` | `waypoint_navigator_node`, `rviz_marker_publisher_node` | simulated pose feedback |
| `/robot_i/vitals_raw` | `mrta_msgs/VitalsReading` | `rppg_sensor_sim_node` | `risk_fusion_node` | only published when a patient is in range |
| `/robot_i/env_raw` | `mrta_msgs/EnvReading` | `env_sensor_sim_node` | `risk_fusion_node` | continuous |
| `/robot_i/risk_reading` | `mrta_msgs/RiskReading` | `risk_fusion_node` | `patient_knowledge_base_node`, `metrics_logger_node` | one fused value per observation |
| `/patients/ground_truth` | `mrta_msgs/GroundTruthPatientArray` | `patient_simulator_node` | `metrics_logger_node` **only** | never read by allocator — this is the whole point |
| `/patients/belief_state` | `mrta_msgs/PatientBeliefArray` | `patient_knowledge_base_node` | `task_allocator_node`, `rviz_marker_publisher_node` | what the allocator actually sees |
| `/cbba/bid_broadcast` | `mrta_msgs/CBBABid` | `cbba_bidding_node` (all robots) | `cbba_bidding_node` (all robots) | shared bus for decentralized consensus |
| `/robot_i/assigned_patient` | `mrta_msgs/TaskAssignment` | `task_allocator_node` or `cbba_bidding_node` | `waypoint_navigator_node` | per-robot current target |
| `/metrics/events` | `std_msgs/String` (JSON payload) | all decision nodes | `metrics_logger_node` | reassignment/spike/visit events |
| `/tf` | `tf2_msgs/TFMessage` | `robot_kinematics_sim_node` | RViz, navigator | standard transform tree |
| `/visualization_marker_array` | `visualization_msgs/MarkerArray` | `rviz_marker_publisher_node` | RViz | robots + patients colored by risk |

**Parameters** (loaded from YAML, not topics): `num_robots`, `num_patients`, `patient_positions`, `sensing_range`, `dwell_time_required`, risk-dynamics drift/spike settings, utility weights `w1..w4`, `cooldown_threshold`, `cooldown_duration`, `allocator_mode`.

---

## 5. Working methodology — build and test order

Don't build this top-down; build it bottom-up so every layer is independently testable with plain `rostopic pub`/`echo` before the next layer depends on it.

1. **Workspace + message package first.** Create the catkin workspace, build `mrta_msgs` alone, confirm `rosmsg show mrta_msgs/RiskReading` works before writing any node.
2. **`patient_simulator_node` standalone.** Run it alone, `rostopic echo /patients/ground_truth`, confirm risk values drift and spike as configured.
3. **`robot_kinematics_sim_node` standalone.** Drive it manually with `teleop_twist_keyboard`, confirm `/robot_0/odom` and TF look correct in RViz.
4. **Sensor sim nodes.** Manually drive a robot near a simulated patient position, confirm `vitals_raw`/`env_raw` only appear within sensing range.
5. **`risk_fusion_node`.** Confirm fused values look sane against known inputs (sanity-check with `rostopic pub` fake vitals).
6. **`patient_knowledge_base_node`.** Publish fake risk readings manually via `rostopic pub`, confirm belief state updates and staleness increases correctly when nothing is published for a patient.
7. **Close the loop with the simplest allocator first.** Implement `round_robin` and `greedy` modes before CBBA — this proves the full pipeline (allocator → assignment → navigator → cmd_vel → odom → back to sensing) actually closes, with a much simpler algorithm to debug.
8. **`waypoint_navigator_node`.** Simple proportional controller; verify a robot actually drives to and stops near an assigned patient.
9. **RViz visualization.** Get markers rendering color-coded by risk — this becomes your Week 4 dashboard's data source too.
10. **`cbba_bidding_node` + cooldown logic.** The hardest, most novel part — build and debug this last, once you trust everything else in the loop.
11. **`metrics_logger_node` + batch experiment launch files.** Run scripted experiments varying `num_robots`/`num_patients`, export CSVs.
12. **Offline analysis.** Pull CSVs into pandas/matplotlib outside ROS entirely for your Week 5/6 comparison plots.

---

## 6. File tree

```
~/catkin_ws/
└── src/
    ├── mrta_msgs/
    │   ├── CMakeLists.txt
    │   ├── package.xml
    │   └── msg/
    │       ├── VitalsReading.msg
    │       ├── EnvReading.msg
    │       ├── RiskReading.msg
    │       ├── PatientBeliefState.msg
    │       ├── PatientBeliefArray.msg
    │       ├── TaskAssignment.msg
    │       ├── CBBABid.msg
    │       ├── GroundTruthPatientState.msg
    │       └── GroundTruthPatientArray.msg
    │
    └── mrta_simulation/
        ├── CMakeLists.txt
        ├── package.xml
        ├── setup.py                        # needed for catkin_python_setup()
        ├── README.md
        │
        ├── src/
        │   └── mrta_simulation/            # importable python module (utils, shared logic)
        │       ├── __init__.py
        │       ├── risk_model.py           # NEWS2-style fusion math (shared, sim + real)
        │       ├── cbba_core.py            # bundle/conflict-resolution logic, importable + unit-testable
        │       └── geometry_utils.py       # distance/range checks, go-to-goal math
        │
        ├── scripts/                        # executable rospy node entry points
        │   ├── patient_simulator_node.py
        │   ├── robot_kinematics_sim_node.py
        │   ├── rppg_sensor_sim_node.py
        │   ├── env_sensor_sim_node.py
        │   ├── risk_fusion_node.py
        │   ├── patient_knowledge_base_node.py
        │   ├── task_allocator_node.py
        │   ├── cbba_bidding_node.py
        │   ├── waypoint_navigator_node.py
        │   ├── rviz_marker_publisher_node.py
        │   └── metrics_logger_node.py
        │
        ├── launch/
        │   ├── simulation.launch           # top-level: includes robots + patients + rviz
        │   ├── robots.launch.xml           # spawns N robot namespaces via xacro-style arg loop
        │   ├── patients.launch.xml
        │   └── experiment_batch.launch     # parametrized for scripted multi-run experiments
        │
        ├── config/
        │   ├── sim_params.yaml             # num_robots, num_patients, patient_positions
        │   ├── risk_dynamics.yaml          # drift rate, spike probability/magnitude
        │   └── allocator_params.yaml       # mode, utility weights, cooldown settings
        │
        ├── rviz/
        │   └── mrta_sim.rviz
        │
        └── results/                        # gitignored — CSV logs + generated plots
            ├── logs/
            └── plots/
```

**Two-package split (`mrta_msgs` + `mrta_simulation`)** follows standard ROS1 convention and avoids circular build dependencies — any future package (including your real-hardware package in Week 3) can depend on `mrta_msgs` without depending on the simulation code.

---

## 7. What changes in Week 3 (hardware) — nothing else does

When you move to real robots, you delete/replace exactly these three files and nothing downstream:
- `patient_simulator_node.py` → not needed (real patients, no ground truth to fake)
- `rppg_sensor_sim_node.py` → replaced by your real camera + POS/CHROM pipeline node, publishing the same `VitalsReading` message
- `env_sensor_sim_node.py` → replaced by real DHT22/SHT31 + mic driver nodes, publishing the same `EnvReading` message

`risk_fusion_node`, `patient_knowledge_base_node`, `task_allocator_node`, `cbba_bidding_node`, and `waypoint_navigator_node` run completely unchanged. This is the concrete evidence, in your final paper, that your Week 1 simulation results transfer to real hardware — the decision-making stack was never touched.
