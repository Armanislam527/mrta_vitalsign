"""Distance, heading, sensing-range, and go-to-goal helpers (no rospy)."""

from __future__ import division

import math


def dist2d(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def wrap_angle(angle):
    """Wrap an angle in radians to (-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle <= -math.pi:
        angle += 2.0 * math.pi
    return angle


def yaw_from_quaternion(x, y, z, w):
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def quaternion_from_yaw(yaw):
    return (0.0, 0.0, math.sin(yaw * 0.5), math.cos(yaw * 0.5))


def in_range(ax, ay, bx, by, sensing_range):
    return dist2d(ax, ay, bx, by) <= sensing_range


def nearest_index(ax, ay, points, max_range=None):
    """Return (index, distance) of the nearest (x, y) point, or (-1, inf)."""
    best_i = -1
    best_d = float("inf")
    for i, p in enumerate(points):
        d = dist2d(ax, ay, p[0], p[1])
        if d < best_d:
            best_d = d
            best_i = i
    if max_range is not None and best_d > max_range:
        return -1, best_d
    return best_i, best_d


def go_to_goal(x, y, yaw, gx, gy, kp_lin=0.8, kp_ang=2.0,
               v_max=0.6, w_max=1.2, arrive_radius=0.35, slow_radius=1.0):
    """Proportional go-to-goal. Returns (v, omega, arrived)."""
    dx = gx - x
    dy = gy - y
    dist = math.hypot(dx, dy)
    if dist <= arrive_radius:
        return 0.0, 0.0, True

    heading = math.atan2(dy, dx)
    err = wrap_angle(heading - yaw)
    # Don't drive forward while badly misaligned.
    if abs(err) > math.pi / 2.0:
        v = 0.0
    else:
        scale = min(1.0, dist / slow_radius)
        v = kp_lin * dist * scale * math.cos(err)
        v = max(-v_max, min(v_max, v))

    omega = max(-w_max, min(w_max, kp_ang * err))
    return v, omega, False


def assignment_utility(risk, staleness_sec, distance, battery_frac,
                       w1, w2, w3, w4,
                       staleness_norm=60.0, distance_norm=10.0):
    """Per-(robot, patient) utility used by greedy and CBBA.

    U = w1*risk + w2*staleness_n - w3*distance_n - w4*(1-battery)
    """
    s_n = min(1.5, staleness_sec / max(1e-3, staleness_norm))
    d_n = distance / max(1e-3, distance_norm)
    b = max(0.0, min(1.0, battery_frac))
    return w1 * risk + w2 * s_n - w3 * d_n - w4 * (1.0 - b)
