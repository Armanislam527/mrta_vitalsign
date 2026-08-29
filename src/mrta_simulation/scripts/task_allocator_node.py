#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized allocator: round_robin or greedy.

When allocator_mode:=cbba this node does not publish assignments; the
per-robot cbba_bidding_node owns that topic.
"""

from __future__ import division

import json

import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32, String

from mrta_msgs.msg import PatientBeliefArray, TaskAssignment
from mrta_simulation.geometry_utils import assignment_utility, dist2d


class TaskAllocator(object):
    def __init__(self):
        self.n_robots = int(rospy.get_param("/num_robots", 3))
        self.mode = rospy.get_param("/allocator_mode", "greedy")
        self.w1 = float(rospy.get_param("/allocator/w1", 1.0))
        self.w2 = float(rospy.get_param("/allocator/w2", 0.6))
        self.w3 = float(rospy.get_param("/allocator/w3", 0.35))
        self.w4 = float(rospy.get_param("/allocator/w4", 0.1))
        self.cooldown_threshold = float(
            rospy.get_param("/allocator/cooldown_threshold", 0.15)
        )
        self.cooldown_duration = float(
            rospy.get_param("/allocator/cooldown_duration", 8.0)
        )
        self.hysteresis = float(rospy.get_param("/allocator/hysteresis", 0.08))
        self.belief = []
        self.pose = [(0.0, 0.0)] * self.n_robots
        self.battery = [1.0] * self.n_robots
        self.assignment = [-1] * self.n_robots
        self.assign_time = [0.0] * self.n_robots
        self.rr_tick = 0
        
        self.pubs = [
            rospy.Publisher(
                "/robot_%d/assigned_patient" % i, TaskAssignment, queue_size=1, latch=True
            )
            for i in range(self.n_robots)
        ]
        self.event_pub = rospy.Publisher("/metrics/events", String, queue_size=20)
        rospy.Subscriber(
            "/patients/belief_state", PatientBeliefArray, self._on_belief, queue_size=1
        )
        for i in range(self.n_robots):
            rospy.Subscriber(
                "/robot_%d/odom" % i, Odometry, self._on_odom, callback_args=i, queue_size=1
            )
            rospy.Subscriber(
                "/robot_%d/battery" % i,
                Float32,
                self._on_batt,
                callback_args=i,
                queue_size=1,
            )
        rate_hz = float(rospy.get_param("~rate", 2.0))
        self.timer = rospy.Timer(rospy.Duration(1.0 / rate_hz), self._tick)

    def _on_belief(self, msg):
        self.belief = msg.patients

    def _on_odom(self, msg, robot_id):
        self.pose[robot_id] = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def _on_batt(self, msg, robot_id):
        self.battery[robot_id] = msg.data

    def _utility(self, r, p):
        rx, ry = self.pose[r]
        d = dist2d(rx, ry, p.position.x, p.position.y)
        return assignment_utility(
            p.last_known_risk,
            p.staleness_sec,
            d,
            self.battery[r],
            self.w1,
            self.w2,
            self.w3,
            self.w4,
        )

    def _cooldown_blocks(self, robot_id, new_pid, new_util, old_util):
        now = rospy.get_time()
        if self.assignment[robot_id] < 0:
            return False
        if now - self.assign_time[robot_id] < self.cooldown_duration:
            if new_util - old_util < self.cooldown_threshold:
                return True
        if new_pid != self.assignment[robot_id] and new_util < old_util + self.hysteresis:
            return True
        return False

    def _publish(self, robot_id, pid):
        now = rospy.get_time()
        changed = pid != self.assignment[robot_id]
        self.assignment[robot_id] = pid
        if changed:
            self.assign_time[robot_id] = now
        msg = TaskAssignment()
        msg.robot_id = robot_id
        msg.assigned_patient_id = pid
        msg.assignment_time = now
        msg.allocator_mode = self.mode
        self.pubs[robot_id].publish(msg)
        if changed:
            payload = {
                "event": "reassignment",
                "t": now,
                "robot_id": robot_id,
                "assigned_patient_id": pid,
                "allocator_mode": self.mode,
            }
            self.event_pub.publish(String(data=json.dumps(payload)))

    def _get_occupied_patients(self):
        """Returns a set of patient IDs that are currently assigned to any robot.
        This acts as a temporary lock to prevent clustering."""
        valid_pids = {p.patient_id for p in self.belief}
        return {pid for pid in self.assignment if pid >= 0 and pid in valid_pids}

    def _round_robin(self):
        n_p = len(self.belief)
        if n_p == 0:
            return
            
        occupied = self._get_occupied_patients()
        chosen = {}
        used_p = set()
        
        # 1. Secure current assignments (temporary lock)
        for r in range(self.n_robots):
            old_pid = self.assignment[r]
            if old_pid >= 0:
                chosen[r] = old_pid
                used_p.add(old_pid)
                
        # 2. Assign remaining robots to unoccupied patients
        for r in range(self.n_robots):
            if r in chosen:
                continue
            
            assigned = False
            for i in range(n_p):
                pid = (self.rr_tick + r + i) % n_p
                if pid in used_p:
                    continue  # Skip patients already being monitored/approached
                
                old = self.assignment[r]
                old_u = self._utility(r, self.belief[old]) if 0 <= old < n_p else -1e9
                new_u = self._utility(r, self.belief[pid])
                
                if self._cooldown_blocks(r, pid, new_u, old_u):
                    break  # Keep old assignment if blocked by cooldown
                    
                chosen[r] = pid
                used_p.add(pid)
                assigned = True
                break
                
            if not assigned and self.assignment[r] >= 0:
                chosen[r] = self.assignment[r]

        self.rr_tick += 1
        
        for r in range(self.n_robots):
            pid = chosen.get(r, -1)
            self._publish(r, pid)

    def _greedy(self):
        n_p = len(self.belief)
        if n_p == 0:
            return
            
        occupied = self._get_occupied_patients()
        
        used_r = set()
        used_p = set()
        chosen = {}
        
        # Build utility pairs, explicitly blocking other robots from bidding on occupied patients
        pairs = []
        for r in range(self.n_robots):
            for p in self.belief:
                pid = p.patient_id
                # CRITICAL FIX: If patient is occupied by ANOTHER robot, this robot cannot bid for it
                if pid in occupied and self.assignment[r] != pid:
                    continue
                pairs.append((self._utility(r, p), r, pid))
                
        pairs.sort(reverse=True)
        
        for u, r, pid in pairs:
            if r in used_r or pid in used_p:
                continue
                
            old = self.assignment[r]
            old_u = self._utility(r, self.belief[old]) if 0 <= old < n_p else -1e9
            
            # If robot is keeping its current occupied patient, bypass cooldown/hysteresis
            if old == pid:
                chosen[r] = pid
                used_r.add(r)
                used_p.add(pid)
                continue
                
            if self._cooldown_blocks(r, pid, u, old_u):
                continue
                
            chosen[r] = pid
            used_r.add(r)
            used_p.add(pid)
            
        # Publish assignments
        for r in range(self.n_robots):
            pid = chosen.get(r, self.assignment[r])
            self._publish(r, pid)

    def _tick(self, _event):
        self.mode = rospy.get_param("/allocator_mode", self.mode)
        if self.mode == "cbba":
            return
        if not self.belief:
            return
            
        if self.mode == "round_robin":
            self._round_robin()
        else:
            self._greedy()


def main():
    rospy.init_node("task_allocator_node")
    TaskAllocator()
    rospy.loginfo("task_allocator_node mode=%s", rospy.get_param("/allocator_mode", "greedy"))
    rospy.spin()


if __name__ == "__main__":
    main()