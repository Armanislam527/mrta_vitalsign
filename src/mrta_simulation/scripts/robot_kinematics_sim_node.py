#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2D differential-drive kinematic integrator (no physics engine)."""

from __future__ import division

import math

import rospy
import tf2_ros
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32

from mrta_simulation.geometry_utils import quaternion_from_yaw


class RobotKinematics(object):
    def __init__(self):
        self.robot_id = int(rospy.get_param("~robot_id", 0))
        starts = rospy.get_param("/robot_start_poses", [])
        if self.robot_id < len(starts):
            s = starts[self.robot_id]
            self.x = float(s.get("x", 0.5))
            self.y = float(s.get("y", 0.5 + self.robot_id))
            self.yaw = float(s.get("yaw", 0.0))
        else:
            self.x = 0.5
            self.y = 0.5 + self.robot_id
            self.yaw = 0.0
        self.v = 0.0
        self.w = 0.0
        self.battery = float(rospy.get_param("/battery_full", 1.0))
        self.drain = float(rospy.get_param("/battery_drain_per_mps", 0.004))
        self.world_frame = rospy.get_param("/world_frame", "map")
        self.base_frame = "robot_%d/base_link" % self.robot_id
        self.odom_frame = "robot_%d/odom" % self.robot_id

        self.pub_odom = rospy.Publisher("odom", Odometry, queue_size=1)
        self.pub_batt = rospy.Publisher("battery", Float32, queue_size=1)
        self.br = tf2_ros.TransformBroadcaster()
        rospy.Subscriber("cmd_vel", Twist, self._on_cmd, queue_size=1)

        rate_hz = float(rospy.get_param("~rate", 20.0))
        self.dt = 1.0 / rate_hz
        self.timer = rospy.Timer(rospy.Duration(self.dt), self._tick)

    def _on_cmd(self, msg):
        self.v = msg.linear.x
        self.w = msg.angular.z

    def _tick(self, _event):
        dt = self.dt
        self.x += self.v * math.cos(self.yaw) * dt
        self.y += self.v * math.sin(self.yaw) * dt
        self.yaw += self.w * dt
        self.battery = max(
            0.0,
            self.battery - self.drain * (abs(self.v) + 0.15 * abs(self.w)) * dt,
        )

        now = rospy.Time.now()
        qx, qy, qz, qw = quaternion_from_yaw(self.yaw)

        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = self.world_frame
        odom.child_frame_id = self.base_frame
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.x = qx
        odom.pose.pose.orientation.y = qy
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = self.v
        odom.twist.twist.angular.z = self.w
        self.pub_odom.publish(odom)
        self.pub_batt.publish(Float32(data=self.battery))

        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = self.world_frame
        t.child_frame_id = self.base_frame
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.x = qx
        t.transform.rotation.y = qy
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw
        self.br.sendTransform(t)


def main():
    rospy.init_node("robot_kinematics_sim_node")
    RobotKinematics()
    rospy.spin()


if __name__ == "__main__":
    main()
