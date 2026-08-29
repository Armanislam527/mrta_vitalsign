cmake_minimum_required(VERSION 3.0.2)
project(mrta_simulation)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  nav_msgs
  tf2_ros
  visualization_msgs
  mrta_msgs
)

catkin_python_setup()

catkin_package(
  CATKIN_DEPENDS
    rospy
    std_msgs
    geometry_msgs
    nav_msgs
    tf2_ros
    visualization_msgs
    mrta_msgs
)

catkin_install_python(PROGRAMS
  scripts/patient_simulator_node.py
  scripts/robot_kinematics_sim_node.py
  scripts/rppg_sensor_sim_node.py
  scripts/env_sensor_sim_node.py
  scripts/risk_fusion_node.py
  scripts/patient_knowledge_base_node.py
  scripts/task_allocator_node.py
  scripts/cbba_bidding_node.py
  scripts/waypoint_navigator_node.py
  scripts/rviz_marker_publisher_node.py
  scripts/metrics_logger_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch config rviz
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
