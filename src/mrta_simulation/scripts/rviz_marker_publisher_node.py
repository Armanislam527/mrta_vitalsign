#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RViz coverage-map preview: robots and patients color-coded by risk."""

from __future__ import division

import math

import rospy
from geometry_msgs.msg import Point
from nav_msgs.msg import Odometry
from visualization_msgs.msg import Marker, MarkerArray

from mrta_msgs.msg import PatientBeliefArray, TaskAssignment


def _risk_color(risk, stale=False):
    """Green (low) -> yellow -> red (high). Stale patients are more transparent."""
    r = max(0.0, min(1.0, risk))
    color_r = r
    color_g = 1.0 - 0.7 * r
    color_b = 0.15 * (1.0 - r)
    a = 0.45 if stale else 0.95
    return color_r, color_g, color_b, a


class MarkerPublisher(object):
    def __init__(self):
        self.n_robots = int(rospy.get_param("/num_robots", 3))
        self.world = rospy.get_param("/world_frame", "map")
        self.belief = []
        self.pose = [(0.0, 0.0, 0.0)] * self.n_robots
        self.assignment = [-1] * self.n_robots
        self.pub = rospy.Publisher(
            "/visualization_marker_array", MarkerArray, queue_size=1
        )
        rospy.Subscriber(
            "/patients/belief_state", PatientBeliefArray, self._on_belief, queue_size=1
        )
        for i in range(self.n_robots):
            rospy.Subscriber(
                "/robot_%d/odom" % i, Odometry, self._on_odom, callback_args=i, queue_size=1
            )
            rospy.Subscriber(
                "/robot_%d/assigned_patient" % i,
                TaskAssignment,
                self._on_asg,
                callback_args=i,
                queue_size=1,
            )
        self.timer = rospy.Timer(rospy.Duration(0.1), self._tick)

    def _on_belief(self, msg):
        self.belief = msg.patients

    def _on_odom(self, msg, rid):
        q = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        )
        self.pose[rid] = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def _on_asg(self, msg, rid):
        self.assignment[rid] = msg.assigned_patient_id

    def _tick(self, _event):
        now = rospy.Time.now()
        arr = MarkerArray()
        # Clear leftover ids if patient count shrinks.
        clear = Marker()
        clear.action = Marker.DELETEALL
        arr.markers.append(clear)

        for p in self.belief:
            stale = p.staleness_sec > 15.0
            cr, cg, cb, ca = _risk_color(p.last_known_risk, stale)
            m = Marker()
            m.header.stamp = now
            m.header.frame_id = self.world
            m.ns = "patients"
            m.id = p.patient_id
            m.type = Marker.CYLINDER
            m.action = Marker.ADD
            m.pose.position.x = p.position.x
            m.pose.position.y = p.position.y
            m.pose.position.z = 0.4
            m.pose.orientation.w = 1.0
            m.scale.x = 0.5
            m.scale.y = 0.5
            m.scale.z = 0.8
            m.color.r, m.color.g, m.color.b, m.color.a = cr, cg, cb, ca
            arr.markers.append(m)

            t = Marker()
            t.header.stamp = now
            t.header.frame_id = self.world
            t.ns = "patient_labels"
            t.id = p.patient_id
            t.type = Marker.TEXT_VIEW_FACING
            t.action = Marker.ADD
            t.pose.position.x = p.position.x
            t.pose.position.y = p.position.y
            t.pose.position.z = 1.05
            t.pose.orientation.w = 1.0
            t.scale.z = 0.22
            t.color.r = t.color.g = t.color.b = 1.0
            t.color.a = 1.0
            t.text = "P%d r=%.2f s=%.0fs" % (
                p.patient_id, p.last_known_risk, p.staleness_sec
            )
            arr.markers.append(t)

        for i in range(self.n_robots):
            x, y, yaw = self.pose[i]
            m = Marker()
            m.header.stamp = now
            m.header.frame_id = self.world
            m.ns = "robots"
            m.id = i
            m.type = Marker.ARROW
            m.action = Marker.ADD
            m.pose.position.x = x
            m.pose.position.y = y
            m.pose.position.z = 0.15
            m.pose.orientation.z = math.sin(yaw * 0.5)
            m.pose.orientation.w = math.cos(yaw * 0.5)
            m.scale.x = 0.55
            m.scale.y = 0.12
            m.scale.z = 0.12
            m.color.r = 0.1
            m.color.g = 0.45
            m.color.b = 1.0
            m.color.a = 1.0
            arr.markers.append(m)

            pid = self.assignment[i]
            if pid >= 0:
                target = None
                for p in self.belief:
                    if p.patient_id == pid:
                        target = p
                        break
                if target is not None:
                    line = Marker()
                    line.header.stamp = now
                    line.header.frame_id = self.world
                    line.ns = "assignments"
                    line.id = i
                    line.type = Marker.LINE_STRIP
                    line.action = Marker.ADD
                    line.scale.x = 0.04
                    line.color.r = 1.0
                    line.color.g = 0.85
                    line.color.b = 0.1
                    line.color.a = 0.8
                    line.pose.orientation.w = 1.0
                    line.points = [
                        Point(x=x, y=y, z=0.2),
                        Point(x=target.position.x, y=target.position.y, z=0.2),
                    ]
                    arr.markers.append(line)
        self.pub.publish(arr)


def main():
    rospy.init_node("rviz_marker_publisher_node")
    MarkerPublisher()
    rospy.spin()


if __name__ == "__main__":
    main()
