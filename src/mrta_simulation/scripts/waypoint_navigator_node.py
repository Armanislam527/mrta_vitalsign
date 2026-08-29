#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proportional go-to-goal controller toward the assigned patient's position."""

from __future__ import division

import json

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import String

from mrta_msgs.msg import PatientBeliefArray, TaskAssignment
from mrta_simulation.geometry_utils import go_to_goal, yaw_from_quaternion


class WaypointNavigator(object):
    def __init__(self):
        self.robot_id = int(rospy.get_param("~robot_id", 0))
        self.arrive = float(rospy.get_param("/navigator/arrive_radius", 0.4))
        self.dwell = float(rospy.get_param("/dwell_time_required", 3.0))
        self.kp_lin = float(rospy.get_param("/navigator/kp_lin", 0.8))
        self.kp_ang = float(rospy.get_param("/navigator/kp_ang", 2.0))
        self.v_max = float(rospy.get_param("/navigator/v_max", 0.6))
        self.w_max = float(rospy.get_param("/navigator/w_max", 1.2))
        self.target = -1
        self.belief = {}
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.dwell_t0 = None
        self.visited = False
        self.pub = rospy.Publisher("cmd_vel", Twist, queue_size=1)
        self.event_pub = rospy.Publisher("/metrics/events", String, queue_size=10)
        rospy.Subscriber("assigned_patient", TaskAssignment, self._on_asg, queue_size=1)
        rospy.Subscriber(
            "/patients/belief_state", PatientBeliefArray, self._on_belief, queue_size=1
        )
        rospy.Subscriber("odom", Odometry, self._on_odom, queue_size=1)
        rate_hz = float(rospy.get_param("~rate", 20.0))
        self.timer = rospy.Timer(rospy.Duration(1.0 / rate_hz), self._tick)

    def _on_asg(self, msg):
        if msg.assigned_patient_id != self.target:
            self.target = msg.assigned_patient_id
            self.dwell_t0 = None
            self.visited = False

    def _on_belief(self, msg):
        self.belief = {p.patient_id: p for p in msg.patients}

    def _on_odom(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        self.yaw = yaw_from_quaternion(q.x, q.y, q.z, q.w)

    def _tick(self, _event):
        cmd = Twist()
        p = self.belief.get(self.target)
        if p is None or self.target < 0:
            self.pub.publish(cmd)
            return
        v, w, arrived = go_to_goal(
            self.x,
            self.y,
            self.yaw,
            p.position.x,
            p.position.y,
            kp_lin=self.kp_lin,
            kp_ang=self.kp_ang,
            v_max=self.v_max,
            w_max=self.w_max,
            arrive_radius=self.arrive,
        )
        now = rospy.get_time()
        if arrived:
            if self.dwell_t0 is None:
                self.dwell_t0 = now
            if not self.visited and (now - self.dwell_t0) >= self.dwell:
                self.visited = True
                payload = {
                    "event": "visit",
                    "t": now,
                    "robot_id": self.robot_id,
                    "patient_id": self.target,
                }
                self.event_pub.publish(String(data=json.dumps(payload)))
            v, w = 0.0, 0.0
        else:
            self.dwell_t0 = None
        cmd.linear.x = v
        cmd.angular.z = w
        self.pub.publish(cmd)


def main():
    rospy.init_node("waypoint_navigator_node")
    WaypointNavigator()
    rospy.spin()


if __name__ == "__main__":
    main()
