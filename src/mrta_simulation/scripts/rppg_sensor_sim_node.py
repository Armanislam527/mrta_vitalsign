#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fake rPPG camera: publishes vitals only when a patient is in range.

Replaced in Week 3 by the real camera + POS/CHROM pipeline. Message type
must stay VitalsReading so downstream nodes do not change.
"""

from __future__ import division

import random

import rospy
from nav_msgs.msg import Odometry

from mrta_msgs.msg import GroundTruthPatientArray, VitalsReading
from mrta_simulation.geometry_utils import nearest_index


class RppgSensorSim(object):
    def __init__(self):
        self.robot_id = int(rospy.get_param("~robot_id", 0))
        self.range = float(rospy.get_param("/sensing_range", 2.0))
        self.hr_std = float(rospy.get_param("/sensor_noise/hr_std", 2.5))
        self.rr_std = float(rospy.get_param("/sensor_noise/rr_std", 0.8))
        self.hrv_std = float(rospy.get_param("/sensor_noise/hrv_std", 0.04))
        seed = int(rospy.get_param("~rng_seed", 11 + self.robot_id))
        self.rng = random.Random(seed)
        self.x = 0.0
        self.y = 0.0
        self.truth = []
        self.pub = rospy.Publisher("vitals_raw", VitalsReading, queue_size=1)
        rospy.Subscriber("odom", Odometry, self._on_odom, queue_size=1)
        rospy.Subscriber(
            "/patients/ground_truth",
            GroundTruthPatientArray,
            self._on_truth,
            queue_size=1,
        )
        rate_hz = float(rospy.get_param("~rate", 5.0))
        self.timer = rospy.Timer(rospy.Duration(1.0 / rate_hz), self._tick)

    def _on_odom(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

    def _on_truth(self, msg):
        self.truth = msg.patients

    def _tick(self, _event):
        if not self.truth:
            return
        pts = [(p.position.x, p.position.y) for p in self.truth]
        idx, _d = nearest_index(self.x, self.y, pts, max_range=self.range)
        if idx < 0:
            return
        p = self.truth[idx]
        out = VitalsReading()
        out.header.stamp = rospy.Time.now()
        out.header.frame_id = "robot_%d/base_link" % self.robot_id
        out.patient_id = p.patient_id
        out.heart_rate = p.heart_rate + self.rng.gauss(0.0, self.hr_std)
        out.resp_rate = p.resp_rate + self.rng.gauss(0.0, self.rr_std)
        out.hrv_proxy = max(
            0.0, min(1.0, p.hrv_proxy + self.rng.gauss(0.0, self.hrv_std))
        )
        self.pub.publish(out)


def main():
    rospy.init_node("rppg_sensor_sim_node")
    RppgSensorSim()
    rospy.spin()


if __name__ == "__main__":
    main()
