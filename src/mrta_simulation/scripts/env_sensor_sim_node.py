#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fake environmental sensors for the patient zone the robot currently occupies.

Replaced in Week 3 by real DHT22/SHT31 + microphone drivers. Message type
must stay EnvReading.
"""

from __future__ import division

import random

import rospy
from nav_msgs.msg import Odometry

from mrta_msgs.msg import EnvReading, GroundTruthPatientArray
from mrta_simulation.geometry_utils import nearest_index


class EnvSensorSim(object):
    def __init__(self):
        self.robot_id = int(rospy.get_param("~robot_id", 0))
        self.zone = float(rospy.get_param("/env_zone_radius", 3.0))
        self.temp_std = float(rospy.get_param("/sensor_noise/temp_std", 0.15))
        self.noise_std = float(rospy.get_param("/sensor_noise/noise_std", 1.5))
        self.rng = random.Random(23 + self.robot_id)
        self.x = 0.0
        self.y = 0.0
        self.truth = []
        self.pub = rospy.Publisher("env_raw", EnvReading, queue_size=1)
        rospy.Subscriber("odom", Odometry, self._on_odom, queue_size=1)
        rospy.Subscriber(
            "/patients/ground_truth",
            GroundTruthPatientArray,
            self._on_truth,
            queue_size=1,
        )
        rate_hz = float(rospy.get_param("~rate", 2.0))
        self.timer = rospy.Timer(rospy.Duration(1.0 / rate_hz), self._tick)

    def _on_odom(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

    def _on_truth(self, msg):
        self.truth = msg.patients

    def _tick(self, _event):
        out = EnvReading()
        out.header.stamp = rospy.Time.now()
        out.header.frame_id = "robot_%d/base_link" % self.robot_id
        if not self.truth:
            out.patient_id = -1
            out.temperature_c = 22.0 + self.rng.gauss(0.0, self.temp_std)
            out.noise_db = 40.0 + self.rng.gauss(0.0, self.noise_std)
            self.pub.publish(out)
            return
        pts = [(p.position.x, p.position.y) for p in self.truth]
        idx, _d = nearest_index(self.x, self.y, pts, max_range=self.zone)
        if idx < 0:
            out.patient_id = -1
            out.temperature_c = 22.0 + self.rng.gauss(0.0, self.temp_std)
            out.noise_db = 40.0 + self.rng.gauss(0.0, self.noise_std)
        else:
            p = self.truth[idx]
            out.patient_id = p.patient_id
            out.temperature_c = p.temperature_c + self.rng.gauss(0.0, self.temp_std)
            out.noise_db = p.noise_db + self.rng.gauss(0.0, self.noise_std)
        self.pub.publish(out)


def main():
    rospy.init_node("env_sensor_sim_node")
    EnvSensorSim()
    rospy.spin()


if __name__ == "__main__":
    main()
