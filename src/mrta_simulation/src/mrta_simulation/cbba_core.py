"""Consensus-Based Bundle Algorithm core (Choi, Brunet, How 2009).

Importable and unit-testable without ROS. The ROS node is a thin wrapper
that exchanges CBBABid messages and calls these functions.

This implementation supports a bundle length of 1 (one patient per robot at
a time), which matches the rest of the pipeline: the navigator consumes a
single assigned_patient_id. The scoring function is the per-task utility
matrix supplied by the caller.
"""

from __future__ import division


class CBBAAgent(object):
    def __init__(self, agent_id, n_tasks, bundle_size=1):
        self.agent_id = int(agent_id)
        self.n_tasks = int(n_tasks)
        self.bundle_size = int(bundle_size)
        self.bundle = []
        self.winning_bids = [-1.0] * n_tasks
        self.winning_agents = [-1] * n_tasks

    def reset_if_size_changed(self, n_tasks):
        if n_tasks != self.n_tasks:
            self.n_tasks = n_tasks
            self.bundle = []
            self.winning_bids = [-1.0] * n_tasks
            self.winning_agents = [-1] * n_tasks

    def build_bundle(self, scores):
        """Phase 1: greedily add the locally-winning task to the bundle.

        scores: sequence of length n_tasks (utility of this agent for each task).
        Returns True if the bundle changed.
        """
        changed = False
        while len(self.bundle) < self.bundle_size:
            best_j = -1
            best_s = float("-inf")
            for j, s in enumerate(scores):
                if j in self.bundle:
                    continue
                if s > self.winning_bids[j] and s > best_s:
                    best_s = s
                    best_j = j
            if best_j < 0:
                break
            self.bundle.append(best_j)
            self.winning_bids[best_j] = best_s
            self.winning_agents[best_j] = self.agent_id
            changed = True
        return changed

    def apply_remote_bid(self, other_id, task_id, bid_value):
        """Phase 2: conflict resolution for a single incoming bid.

        Returns True if this agent's bundle lost a task.
        """
        if task_id < 0 or task_id >= self.n_tasks:
            return False
        lost = False
        y_i = self.winning_bids[task_id]
        z_i = self.winning_agents[task_id]

        if other_id == self.agent_id:
            return False

        # Standard CBBA-style update for the receiver (simplified Table 1):
        # remote agent claims task j with a strictly higher bid.
        if bid_value > y_i + 1e-9:
            self.winning_bids[task_id] = bid_value
            self.winning_agents[task_id] = other_id
            if task_id in self.bundle:
                self.bundle = [t for t in self.bundle if t != task_id]
                lost = True
        elif abs(bid_value - y_i) <= 1e-9:
            # Tie-break: lower agent id wins (deterministic consensus).
            winner = other_id if other_id < z_i or z_i < 0 else z_i
            self.winning_agents[task_id] = winner
            if winner != self.agent_id and task_id in self.bundle:
                self.bundle = [t for t in self.bundle if t != task_id]
                lost = True
        else:
            # Remote bid is worse. If we thought they held it, they released.
            if z_i == other_id:
                if self.agent_id in [self.winning_agents[task_id]]:
                    pass
                # Leave our own better bid in place; if we don't hold it,
                # clear so we can re-bid next round.
                if task_id not in self.bundle:
                    self.winning_bids[task_id] = -1.0
                    self.winning_agents[task_id] = -1

        return lost

    def assigned_task(self):
        if not self.bundle:
            return -1
        return self.bundle[0]


def solve_cbba(score_matrix, bundle_size=1, max_iter=50):
    """Centralized consensus loop used for tests and as a greedy-CBBA oracle.

    score_matrix: list of list, [agent][task] -> utility
    Returns list of assigned task ids per agent (-1 if idle).
    """
    n_agents = len(score_matrix)
    n_tasks = len(score_matrix[0]) if n_agents else 0
    agents = [CBBAAgent(i, n_tasks, bundle_size) for i in range(n_agents)]

    for _ in range(max_iter):
        any_change = False
        for a in agents:
            if a.build_bundle(score_matrix[a.agent_id]):
                any_change = True
        # Broadcast every agent's current winning bids to every other agent.
        for src in agents:
            for j in range(n_tasks):
                if src.winning_agents[j] != src.agent_id:
                    continue
                for dst in agents:
                    if dst.agent_id == src.agent_id:
                        continue
                    if dst.apply_remote_bid(
                        src.agent_id, j, src.winning_bids[j]
                    ):
                        any_change = True
        if not any_change:
            break

    return [a.assigned_task() for a in agents]
