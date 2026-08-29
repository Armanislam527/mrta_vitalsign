# MRTA vital-sign monitoring simulation (ROS Noetic)

Catkin workspace for multi-robot task allocation with continuous vital-sign monitoring. Decision-making nodes (`risk_fusion`, `patient_knowledge_base`, `task_allocator`, `cbba_bidding`, `waypoint_navigator`) are the same code that will run on hardware in Week 3. Only the simulation-layer nodes are replaced.

## Build

```bash
cd ~/mrta_vitalsign
source /opt/ros/noetic/setup.bash
catkin_make
source devel/setup.bash
```

Confirm messages:

```bash
rosmsg show mrta_msgs/RiskReading
```

## Run the full simulation

```bash
source devel/setup.bash
roslaunch mrta_simulation simulation.launch
```

Allocator modes:

```bash
roslaunch mrta_simulation simulation.launch allocator_mode:=round_robin
roslaunch mrta_simulation simulation.launch allocator_mode:=greedy
roslaunch mrta_simulation simulation.launch allocator_mode:=cbba
```

Headless timed experiment (CSV logs under `results/logs/`):

```bash
roslaunch mrta_simulation experiment_batch.launch \
  allocator_mode:=cbba num_robots:=3 num_patients:=5 duration:=120 run_tag:=cbba_n3p5
```

## Standalone checks (architecture §5)

Patient risk drift/spikes:

```bash
roslaunch mrta_simulation patients.launch.xml
rostopic echo /patients/ground_truth
```

Drive one robot by hand (after launching kinematics in namespace `robot_0`):

```bash
rosrun teleop_twist_keyboard teleop_twist_keyboard.py cmd_vel:=/robot_0/cmd_vel
```

## Packages

| Package | Role |
|---|---|
| `mrta_msgs` | Custom messages (vitals, risk, belief, assignment, CBBA bids, ground truth) |
| `mrta_simulation` | Sim world nodes + decision stack + RViz + CSV logger |

The allocator **never** subscribes to `/patients/ground_truth`. It only sees `/patients/belief_state`.
