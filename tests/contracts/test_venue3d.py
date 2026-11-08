"""Synthetic geometry regressions; private venue references are never CI inputs."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/sprites"))
import venue3d as V  # noqa: E402


def test_adjacent_tapered_sections_keep_shared_level_rails():
    mesh = V.Mesh()
    # A venue's straight upper tier, narrowing toward its back: adjacent sections must meet
    # exactly even though their depths differ. No radial per-section height normalization.
    V.seating_section(mesh, [[0, 12, 10], [10, 12, 10]], [[2, 22, 30], [10, 22, 30]], 1, 5)
    V.seating_section(mesh, [[10, 12, 10], [20, 12, 10]], [[10, 22, 30], [18, 22, 30]], 2, 5)
    a, b = np.concatenate(mesh.vertices[:2]), np.concatenate(mesh.vertices[2:])
    assert {tuple(p) for p in a if p[0] == 10} == {(10, 12, 10), (10, 22, 30)}
    assert {tuple(p) for p in b if p[0] == 10} == {(10, 12, 10), (10, 22, 30)}
    assert set(a[:, 1]) == {12, 22}
    assert set(b[:, 1]) == {12, 22}
    # The back row retains each section's own width, keeping the staircase on its edge.
    for attrs in mesh.attributes:
        for s, r in attrs:
            assert s in (0, 10) and r in (0, 20)


@pytest.mark.parametrize(
    "back", [[[0, 22, 10], [10, 22, 10]], [[0, float("nan"), 30], [10, 22, 30]]]
)
def test_degenerate_or_nonfinite_seating_is_rejected(back):
    with pytest.raises(ValueError):
        V.seating_section(V.Mesh(), [[0, 12, 10], [10, 12, 10]], back, 1, 5)


def test_tunnel_entrances_stay_dark_in_day_and_night():
    mesh = V.Mesh()
    mesh.quad((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0), V.TUNNEL, 42)
    view = V.View(
        np.array([0, 0, -5.0]),
        np.array([0, 0, 1.0]),
        np.array([1.0, 0, 0]),
        np.array([0, 1.0, 0]),
        64,
        64,
        64,
    )
    g = V.rasterize(mesh, view, (0, 64))
    look = {"seat": (80, 80, 140), "concrete": (205, 205, 200)}
    mask = g.material == V.TUNNEL
    assert mask.sum() > 500
    for night in (False, True):
        pixels = np.asarray(V.shade(g, look, night=night, seed=12))[mask]
        assert pixels.max() < 30  # Entrances must never inherit a lit suite window.
        assert len(np.unique(pixels, axis=0)) == 1


def test_crossed_seating_rails_are_rejected_before_adding_triangles():
    mesh = V.Mesh()
    with pytest.raises(ValueError, match="cross|convex"):
        V.seating_section(mesh, [[0, 12, 10], [10, 12, 10]], [[10, 22, 30], [0, 22, 30]], 1, 5)
    assert not mesh.vertices
