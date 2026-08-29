#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central belief state: last known risk, timestamp, and staleness per patient.

This is where partial observability lives. The allocator reads this topic,
never ground truth.
"""

from __future__ import division

import rospy
from geometry_msgs.msg import Point

from mrta_msgs.msg import (
    PatientBeliefArray,
    PatientBeliefState,
    RiskReading,
)


class KnowledgeBase(object):
    def __init__(self):
        n = int(rospy.get_param("/num_patients", 5))
        positions = rospy.get_param("/patient_positions", [])
        self.states = []
        for i in range(n):
            s = PatientBeliefState()
            s.patient_id = i
            s.last_known_risk = 0.0
            s.last_update_time = 0.0
            s.staleness_sec = 0.0
            if i < len(positions):
                p = positions[i]
                s.position = Point(
                    x=float(p["x"]), y=float(p["y"]), z=float(p.get("z", 0.0))
                )
            else:
                s.position = Point(x=2.0 + i * 2.0, y=3.0, z=0.0)
            self.states.append(s)
        self.seen = [False] * n
        self.pub = rospy.Publisher(
            "/patients/belief_state", PatientBeliefArray, queue_size=1
        )
        n_robots = int(rospy.get_param("/num_robots", 3))
        for i in range(n_robots):
            rospy.Subscriber(
                "/robot_%d/risk_reading" % i,
                RiskReading,
                self._on_risk,
                queue_size=10,
            )
        rate_hz = float(rospy.get_param("~rate", 2.0))
        self.timer = rospy.Timer(rospy.Duration(1.0 / rate_hz), self._tick)

    def _on_risk(self, msg):
        pid = int(msg.patient_id)
        if pid < 0 or pid >= len(self.states):
            return
        s = self.states[pid]
        s.last_known_risk = float(msg.risk_value)
        s.last_update_time = rospy.get_time()
        s.staleness_sec = 0.0
        self.seen[pid] = True

    def _tick(self, _event):
        now = rospy.get_time()
        out = PatientBeliefArray()
        for i, s in enumerate(self.states):
            if self.seen[i] and s.last_update_time > 0.0:
                s.staleness_sec = max(0.0, now - s.last_update_time)
            else:
                # Never observed: staleness grows from node start so the
                # allocator is incentivized to get an initial reading.
                s.staleness_sec = now
            out.patients.append(s)
        self.pub.publish(out)


def main():
    rospy.init_node("patient_knowledge_base_node")
    KnowledgeBase()
    rospy.spin()


if __name__ == "__main__":
    main()
