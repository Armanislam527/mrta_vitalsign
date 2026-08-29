#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decentralized CBBA bidder. Active only when allocator_mode:=cbba."""

from __future__ import division

import json

import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32, String

from mrta_msgs.msg import CBBABid, PatientBeliefArray, TaskAssignment
from mrta_simulation.cbba_core import CBBAAgent
from mrta_simulation.geometry_utils import assignment_utility, dist2d


class CbbaBidder(object):
    def __init__(self):
        self.robot_id = int(rospy.get_param("~robot_id", 0))
        self.n_patients = int(rospy.get_param("/num_patients", 5))
        bundle_size = int(rospy.get_param("/allocator/cbba_bundle_size", 1))
        self.agent = CBBAAgent(self.robot_id, self.n_patients, bundle_size)
        self.w1 = float(rospy.get_param("/allocator/w1", 1.0))
        self.w2 = float(rospy.get_param("/allocator/w2", 0.6))
        self.w3 = float(rospy.get_param("/allocator/w3", 0.35))
        self.w4 = float(rospy.get_param("/allocator/w4", 0.1))
        self.cooldown_duration = float(
            rospy.get_param("/allocator/cooldown_duration", 8.0)
        )
        self.belief = []
        self.x = 0.0
        self.y = 0.0
        self.battery = 1.0
        self.last_assign = -1
        self.last_assign_time = 0.0
        self.pub_bid = rospy.Publisher("/cbba/bid_broadcast", CBBABid, queue_size=20)
        self.pub_asg = rospy.Publisher(
            "assigned_patient", TaskAssignment, queue_size=1, latch=True
        )
        self.event_pub = rospy.Publisher("/metrics/events", String, queue_size=20)
        rospy.Subscriber(
            "/patients/belief_state", PatientBeliefArray, self._on_belief, queue_size=1
        )
        rospy.Subscriber("odom", Odometry, self._on_odom, queue_size=1)
        rospy.Subscriber("battery", Float32, self._on_batt, queue_size=1)
        rospy.Subscriber(
            "/cbba/bid_broadcast", CBBABid, self._on_bid, queue_size=50
        )
        rate_hz = float(rospy.get_param("~rate", 4.0))
        self.timer = rospy.Timer(rospy.Duration(1.0 / rate_hz), self._tick)

    def _on_belief(self, msg):
        self.belief = msg.patients
        self.agent.reset_if_size_changed(len(self.belief))

    def _on_odom(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

    def _on_batt(self, msg):
        self.battery = msg.data

    def _scores(self):
        scores = []
        for p in self.belief:
            d = dist2d(self.x, self.y, p.position.x, p.position.y)
            scores.append(
                assignment_utility(
                    p.last_known_risk,
                    p.staleness_sec,
                    d,
                    self.battery,
                    self.w1,
                    self.w2,
                    self.w3,
                    self.w4,
                )
            )
        return scores

    def _on_bid(self, msg):
        if rospy.get_param("/allocator_mode", "greedy") != "cbba":
            return
        if msg.robot_id == self.robot_id:
            return
        self.agent.apply_remote_bid(msg.robot_id, msg.patient_id, msg.bid_value)

    def _publish_assignment(self, pid):
        now = rospy.get_time()
        if pid == self.last_assign and now - self.last_assign_time < 0.5:
            return
        changed = pid != self.last_assign
        if (
            not changed
            and now - self.last_assign_time < self.cooldown_duration
        ):
            pass
        msg = TaskAssignment()
        msg.robot_id = self.robot_id
        msg.assigned_patient_id = pid
        msg.assignment_time = now
        msg.allocator_mode = "cbba"
        self.pub_asg.publish(msg)
        if changed:
            self.last_assign = pid
            self.last_assign_time = now
            payload = {
                "event": "reassignment",
                "t": now,
                "robot_id": self.robot_id,
                "assigned_patient_id": pid,
                "allocator_mode": "cbba",
            }
            self.event_pub.publish(String(data=json.dumps(payload)))

    def _tick(self, _event):
        if rospy.get_param("/allocator_mode", "greedy") != "cbba":
            return
        if not self.belief:
            return
        scores = self._scores()
        self.agent.build_bundle(scores)
        now = rospy.get_time()
        for j in self.agent.bundle:
            bid = CBBABid()
            bid.robot_id = self.robot_id
            bid.patient_id = j
            bid.bid_value = self.agent.winning_bids[j]
            bid.timestamp = now
            self.pub_bid.publish(bid)
        self._publish_assignment(self.agent.assigned_task())


def main():
    rospy.init_node("cbba_bidding_node")
    CbbaBidder()
    rospy.spin()


if __name__ == "__main__":
    main()
