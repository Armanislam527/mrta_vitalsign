#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fuse vitals + environment into a NEWS2-inspired risk reading.

Publishes RiskReading only when a valid vitals observation exists.
Identical node runs on real hardware in Week 3.
"""

from __future__ import division

import rospy

from mrta_msgs.msg import EnvReading, RiskReading, VitalsReading
from mrta_simulation.risk_model import fuse_risk


class RiskFusion(object):
    def __init__(self):
        self.robot_id = int(rospy.get_param("~robot_id", 0))
        self.last_env = None
        self.pub = rospy.Publisher("risk_reading", RiskReading, queue_size=5)
        rospy.Subscriber("vitals_raw", VitalsReading, self._on_vitals, queue_size=5)
        rospy.Subscriber("env_raw", EnvReading, self._on_env, queue_size=5)

    def _on_env(self, msg):
        self.last_env = msg

    def _on_vitals(self, msg):
        temp = 36.8
        noise = 42.0
        if self.last_env is not None:
            if (
                self.last_env.patient_id < 0
                or self.last_env.patient_id == msg.patient_id
            ):
                temp = self.last_env.temperature_c
                noise = self.last_env.noise_db
        risk = fuse_risk(
            msg.heart_rate, msg.resp_rate, msg.hrv_proxy, temp, noise
        )
        out = RiskReading()
        out.header.stamp = rospy.Time.now()
        out.header.frame_id = msg.header.frame_id
        out.robot_id = self.robot_id
        out.patient_id = msg.patient_id
        out.risk_value = risk
        self.pub.publish(out)


def main():
    rospy.init_node("risk_fusion_node")
    RiskFusion()
    rospy.spin()


if __name__ == "__main__":
    main()
