#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulated ward: hidden ground-truth physiology and risk per patient.

Publishes /patients/ground_truth for the logger and the sensor sim nodes.
The allocator must never subscribe to this topic.
"""

from __future__ import division

import random

import rospy
from geometry_msgs.msg import Point
from std_msgs.msg import String

from mrta_msgs.msg import GroundTruthPatientArray, GroundTruthPatientState
from mrta_simulation.risk_model import fuse_risk


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Patient(object):
    def __init__(self, pid, x, y, params, rng):
        self.id = pid
        self.x = float(x)
        self.y = float(y)
        self.hr = float(params["hr_base"]) + rng.uniform(-4.0, 4.0)
        self.rr = float(params["rr_base"]) + rng.uniform(-1.5, 1.5)
        self.hrv = float(params["hrv_base"]) + rng.uniform(-0.05, 0.05)
        self.temp = float(params["temp_base"]) + rng.uniform(-0.2, 0.2)
        self.noise = float(params["noise_base"]) + rng.uniform(-2.0, 2.0)
        self.spike_until = 0.0
        self.spike_hr = 0.0
        self.spike_rr = 0.0
        self.spike_hrv = 0.0

    def step(self, dt, now, params, rng):
        drift = float(params["drift_std"])
        self.hr += rng.gauss(0.0, drift * 8.0) * dt
        self.rr += rng.gauss(0.0, drift * 2.0) * dt
        self.hrv += rng.gauss(0.0, drift * 0.4) * dt
        self.temp += rng.gauss(0.0, drift * 0.15) * dt
        self.noise += rng.gauss(0.0, drift * 4.0) * dt

        self.hr = _clamp(self.hr, 45.0, 160.0)
        self.rr = _clamp(self.rr, 8.0, 36.0)
        self.hrv = _clamp(self.hrv, 0.0, 1.0)
        self.temp = _clamp(self.temp, 35.0, 40.5)
        self.noise = _clamp(self.noise, 30.0, 80.0)

        if now >= self.spike_until and rng.random() < float(params["spike_prob"]):
            mag = float(params["spike_magnitude"])
            self.spike_until = now + float(params["spike_duration"])
            self.spike_hr = 25.0 + mag * 40.0
            self.spike_rr = 6.0 + mag * 8.0
            self.spike_hrv = 0.25 + mag * 0.4
            return True
        if now >= self.spike_until:
            self.spike_hr = self.spike_rr = self.spike_hrv = 0.0
        return False

    def observed_physiology(self):
        hr = self.hr + self.spike_hr
        rr = self.rr + self.spike_rr
        hrv = _clamp(self.hrv + self.spike_hrv, 0.0, 1.0)
        return hr, rr, hrv, self.temp, self.noise

    def true_risk(self):
        hr, rr, hrv, temp, noise = self.observed_physiology()
        return fuse_risk(hr, rr, hrv, temp, noise)


class PatientSimulator(object):
    def __init__(self):
        seed = int(rospy.get_param("~rng_seed", rospy.get_param("/rng_seed", 7)))
        self.rng = random.Random(seed)
        n = int(rospy.get_param("/num_patients", 5))
        positions = rospy.get_param("/patient_positions", [])
        if len(positions) < n:
            positions = list(positions) + [
                {"x": 2.0 + i * 2.0, "y": 3.0 + (i % 2) * 2.0, "z": 0.0}
                for i in range(len(positions), n)
            ]
        dyn = {
            "hr_base": rospy.get_param("/risk_dynamics/hr_base", 75.0),
            "rr_base": rospy.get_param("/risk_dynamics/rr_base", 16.0),
            "hrv_base": rospy.get_param("/risk_dynamics/hrv_base", 0.2),
            "temp_base": rospy.get_param("/risk_dynamics/temp_base", 36.8),
            "noise_base": rospy.get_param("/risk_dynamics/noise_base", 42.0),
            "drift_std": rospy.get_param("/risk_dynamics/drift_std", 0.08),
            "spike_prob": rospy.get_param("/risk_dynamics/spike_prob", 0.002),
            "spike_magnitude": rospy.get_param("/risk_dynamics/spike_magnitude", 0.45),
            "spike_duration": rospy.get_param("/risk_dynamics/spike_duration", 25.0),
        }
        self.patients = []
        for i in range(n):
            p = positions[i]
            self.patients.append(Patient(i, p["x"], p["y"], dyn, self.rng))
        self.dyn = dyn
        self.pub = rospy.Publisher(
            "/patients/ground_truth", GroundTruthPatientArray, queue_size=1
        )
        self.event_pub = rospy.Publisher("/metrics/events", String, queue_size=20)
        rate_hz = float(rospy.get_param("~rate", 10.0))
        self.dt = 1.0 / rate_hz
        self.timer = rospy.Timer(rospy.Duration(self.dt), self._tick)

    def _tick(self, _event):
        now = rospy.get_time()
        msg = GroundTruthPatientArray()
        for p in self.patients:
            spiked = p.step(self.dt, now, self.dyn, self.rng)
            if spiked:
                self.event_pub.publish(String(
                    data='{"event":"spike","t":%f,"patient_id":%d}' % (now, p.id)
                ))
            hr, rr, hrv, temp, noise = p.observed_physiology()
            s = GroundTruthPatientState()
            s.patient_id = p.id
            s.true_risk = p.true_risk()
            s.position = Point(x=p.x, y=p.y, z=0.0)
            s.heart_rate = hr
            s.resp_rate = rr
            s.hrv_proxy = hrv
            s.temperature_c = temp
            s.noise_db = noise
            msg.patients.append(s)
        self.pub.publish(msg)


def main():
    rospy.init_node("patient_simulator_node")
    PatientSimulator()
    rospy.loginfo("patient_simulator_node running with %d patients",
                  int(rospy.get_param("/num_patients", 5)))
    rospy.spin()


if __name__ == "__main__":
    main()
