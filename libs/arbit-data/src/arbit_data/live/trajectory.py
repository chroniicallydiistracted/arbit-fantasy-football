"""Field-space motion with time, position, velocity and independent body heading."""

from bisect import bisect_right
from collections.abc import Sequence
from math import atan2, isfinite, remainder, tau

from arbit_data.live.contracts import LiveModel


class MotionAnchor(LiveModel):
    t: float
    x: float
    z: float
    heading: float | None = None  # radians from +x toward +z
    stopped: bool = False


class MotionKey(LiveModel):
    t: float
    x: float
    z: float
    vx: float
    vz: float
    heading: float


def _tangent(left: float, right: float, before: float, after: float) -> float:
    if left * right <= 0:
        return 0.0
    # A weighted harmonic mean prevents a component from overshooting either adjacent anchor.
    w_left, w_right = 2 * after + before, after + 2 * before
    return (w_left + w_right) / (w_left / left + w_right / right)


def path(anchors: Sequence[MotionAnchor]) -> tuple[MotionKey, ...]:
    """Turn timed position anchors into a continuous piecewise cubic track."""
    if not anchors:
        raise ValueError("a motion track needs an anchor")
    if any(not all(map(isfinite, (a.t, a.x, a.z, a.heading or 0.0))) for a in anchors):
        raise ValueError("motion anchors must be finite")
    spans = [b.t - a.t for a, b in zip(anchors, anchors[1:], strict=False)]
    if any(span <= 0 for span in spans):
        raise ValueError("motion anchor times must increase")
    velocities = [
        ((b.x - a.x) / dt, (b.z - a.z) / dt)
        for a, b, dt in zip(anchors, anchors[1:], spans, strict=False)
    ]
    keys: list[MotionKey] = []
    for i, a in enumerate(anchors):
        vx = vz = 0.0
        if 0 < i < len(anchors) - 1 and not a.stopped:
            vx = _tangent(velocities[i - 1][0], velocities[i][0], spans[i - 1], spans[i])
            vz = _tangent(velocities[i - 1][1], velocities[i][1], spans[i - 1], spans[i])
        heading = a.heading
        if heading is None:
            dx, dz = vx, vz
            if not (dx or dz) and velocities:
                dx, dz = velocities[min(i, len(velocities) - 1)]
            heading = atan2(dz, dx) if dx or dz else keys[-1].heading if keys else 0.0
        keys.append(MotionKey(t=a.t, x=a.x, z=a.z, vx=vx, vz=vz, heading=heading))
    return tuple(keys)


def _component(
    a: float, b: float, va: float, vb: float, u: float, dt: float
) -> tuple[float, float]:
    c1 = dt * va
    c2 = 3 * (b - a) - dt * (2 * va + vb)
    c3 = 2 * (a - b) + dt * (va + vb)
    return a + u * (c1 + u * (c2 + u * c3)), (c1 + u * (2 * c2 + 3 * u * c3)) / dt


def sample(track: Sequence[MotionKey], seconds: float) -> MotionKey:
    """Evaluate the shared cubic and its derivative, holding the end poses outside the track."""
    if seconds <= track[0].t:
        return track[0]
    if seconds >= track[-1].t:
        return track[-1]
    i = bisect_right(track, seconds, key=lambda key: key.t)
    a, b = track[i - 1], track[i]
    dt = b.t - a.t
    u = (seconds - a.t) / dt
    x, vx = _component(a.x, b.x, a.vx, b.vx, u, dt)
    z, vz = _component(a.z, b.z, a.vz, b.vz, u, dt)
    heading = a.heading + remainder(b.heading - a.heading, tau) * (u * u * (3 - 2 * u))
    return MotionKey(t=seconds, x=x, z=z, vx=vx, vz=vz, heading=heading)


def within_speed(track: Sequence[MotionKey], limit: float) -> bool:
    """Conservatively bound the speed of the cubic using its quadratic velocity controls."""
    threshold = limit * limit

    def bounded(
        x: tuple[float, float, float],
        z: tuple[float, float, float],
        depth: int,
    ) -> bool:
        if all(vx * vx + vz * vz <= threshold for vx, vz in zip(x, z, strict=True)):
            return True
        if depth == 0 or any(x[i] * x[i] + z[i] * z[i] > threshold for i in (0, 2)):
            return False
        left_x, right_x = (x[0] + x[1]) / 2, (x[1] + x[2]) / 2
        left_z, right_z = (z[0] + z[1]) / 2, (z[1] + z[2]) / 2
        middle_x, middle_z = (left_x + right_x) / 2, (left_z + right_z) / 2
        return bounded((x[0], left_x, middle_x), (z[0], left_z, middle_z), depth - 1) and bounded(
            (middle_x, right_x, x[2]),
            (middle_z, right_z, z[2]),
            depth - 1,
        )

    for a, b in zip(track, track[1:], strict=False):
        dt = b.t - a.t
        x = (a.vx, 3 * (b.x - a.x) / dt - a.vx - b.vx, b.vx)
        z = (a.vz, 3 * (b.z - a.z) / dt - a.vz - b.vz, b.vz)
        if not bounded(x, z, 5):
            return False
    return True
