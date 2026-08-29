#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSV logger for risk readings, reassignment events, poses, and ground truth."""

from __future__ import division

import csv
import os
import time

import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import String

from mrta_msgs.msg import (
    GroundTruthPatientArray,
    PatientBeliefArray,
    RiskReading,
    TaskAssignment,
)


def _stamp():
    return time.strftime("%Y%m%d_%H%M%S")


class CsvWriter(object):
    def __init__(self, path, fieldnames):
        self._f = open(path, "w")
        self._w = csv.DictWriter(self._f, fieldnames=fieldnames)
        self._w.writeheader()
        self._f.flush()

    def write(self, row):
        self._w.writerow(row)
        self._f.flush()

    def close(self):
        self._f.close()


class MetricsLogger(object):
    def __init__(self):
        log_dir = rospy.get_param(
            "~log_dir",
            os.path.join(
                rospy.get_param(
                    "/results_dir",
                    os.path.expanduser(
                        "~/mrta_vitalsign/src/mrta_simulation/results/logs"
                    ),
                )
            ),
        )
        os.makedirs(log_dir, exist_ok=True)
        tag = rospy.get_param("~run_tag", "")
        if not tag:
            tag = _stamp()
        mode = rospy.get_param("/allocator_mode", "greedy")
        prefix = os.path.join(log_dir, "%s_%s" % (tag, mode))

        self.risk_csv = CsvWriter(
            prefix + "_risk.csv",
            ["t", "robot_id", "patient_id", "risk_value"],
        )
        self.gt_csv = CsvWriter(
            prefix + "_ground_truth.csv",
            [
                "t",
                "patient_id",
                "true_risk",
                "x",
                "y",
                "heart_rate",
                "resp_rate",
                "hrv_proxy",
                "temperature_c",
                "noise_db",
            ],
        )
        self.belief_csv = CsvWriter(
            prefix + "_belief.csv",
            ["t", "patient_id", "last_known_risk", "last_update_time", "staleness_sec"],
        )
        self.pose_csv = CsvWriter(
            prefix + "_poses.csv",
            ["t", "robot_id", "x", "y"],
        )
        self.assign_csv = CsvWriter(
            prefix + "_assignments.csv",
            ["t", "robot_id", "assigned_patient_id", "allocator_mode"],
        )
        self.event_csv = CsvWriter(
            prefix + "_events.csv",
            ["t", "payload"],
        )
        rospy.loginfo("metrics_logger writing to %s_*", prefix)

        self._last_gt = 0.0
        self._last_pose = {}
        self._last_belief = 0.0

        n_robots = int(rospy.get_param("/num_robots", 3))
        rospy.Subscriber(
            "/patients/ground_truth",
            GroundTruthPatientArray,
            self._on_gt,
            queue_size=1,
        )
        rospy.Subscriber(
            "/patients/belief_state",
            PatientBeliefArray,
            self._on_belief,
            queue_size=1,
        )
        rospy.Subscriber("/metrics/events", String, self._on_event, queue_size=50)
        for i in range(n_robots):
            rospy.Subscriber(
                "/robot_%d/risk_reading" % i,
                RiskReading,
                self._on_risk,
                queue_size=20,
            )
            rospy.Subscriber(
                "/robot_%d/odom" % i,
                Odometry,
                self._on_odom,
                callback_args=i,
                queue_size=1,
            )
            rospy.Subscriber(
                "/robot_%d/assigned_patient" % i,
                TaskAssignment,
                self._on_asg,
                queue_size=5,
            )

        duration = float(rospy.get_param("/experiment_duration", 0.0))
        if duration > 0.0:
            rospy.Timer(rospy.Duration(duration), self._stop, oneshot=True)

    def _on_risk(self, msg):
        self.risk_csv.write(
            {
                "t": rospy.get_time(),
                "robot_id": msg.robot_id,
                "patient_id": msg.patient_id,
                "risk_value": msg.risk_value,
            }
        )

    def _on_gt(self, msg):
        now = rospy.get_time()
        if now - self._last_gt < 0.2:
            return
        self._last_gt = now
        for p in msg.patients:
            self.gt_csv.write(
                {
                    "t": now,
                    "patient_id": p.patient_id,
                    "true_risk": p.true_risk,
                    "x": p.position.x,
                    "y": p.position.y,
                    "heart_rate": p.heart_rate,
                    "resp_rate": p.resp_rate,
                    "hrv_proxy": p.hrv_proxy,
                    "temperature_c": p.temperature_c,
                    "noise_db": p.noise_db,
                }
            )

    def _on_belief(self, msg):
        now = rospy.get_time()
        if now - self._last_belief < 0.4:
            return
        self._last_belief = now
        for p in msg.patients:
            self.belief_csv.write(
                {
                    "t": now,
                    "patient_id": p.patient_id,
                    "last_known_risk": p.last_known_risk,
                    "last_update_time": p.last_update_time,
                    "staleness_sec": p.staleness_sec,
                }
            )

    def _on_odom(self, msg, rid):
        now = rospy.get_time()
        if now - self._last_pose.get(rid, 0.0) < 0.2:
            return
        self._last_pose[rid] = now
        self.pose_csv.write(
            {
                "t": now,
                "robot_id": rid,
                "x": msg.pose.pose.position.x,
                "y": msg.pose.pose.position.y,
            }
        )

    def _on_asg(self, msg):
        self.assign_csv.write(
            {
                "t": rospy.get_time(),
                "robot_id": msg.robot_id,
                "assigned_patient_id": msg.assigned_patient_id,
                "allocator_mode": msg.allocator_mode,
            }
        )

    def _on_event(self, msg):
        self.event_csv.write({"t": rospy.get_time(), "payload": msg.data})

    def _stop(self, _event):
        rospy.loginfo("experiment_duration reached — shutting down")
        rospy.signal_shutdown("experiment complete")

    def close(self):
        for w in (
            self.risk_csv,
            self.gt_csv,
            self.belief_csv,
            self.pose_csv,
            self.assign_csv,
            self.event_csv,
        ):
            w.close()


def main():
    rospy.init_node("metrics_logger_node")
    node = MetricsLogger()
    rospy.on_shutdown(node.close)
    rospy.spin()


if __name__ == "__main__":
    main()
