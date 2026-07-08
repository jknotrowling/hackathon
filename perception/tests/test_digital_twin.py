"""Tests for digital-twin unit reconstruction and placement. No hardware or model needed."""
import numpy as np
import open3d as o3d

from perception.arithmetic import UNIT_DIMS_M
from perception.digital_twin import place_units, reconstruct_units


def _pcd(points: np.ndarray) -> o3d.geometry.PointCloud:
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))


def _box_surface(cx, cy, z0, length, width, height, yaw_rad=0.0, n=800, seed=0) -> np.ndarray:
    """Points on the top surface + sides of a box, like a depth camera sees a unit."""
    rng = np.random.default_rng(seed)
    n_top = int(n * 0.7)
    top = np.column_stack([
        rng.uniform(-length / 2, length / 2, n_top),
        rng.uniform(-width / 2, width / 2, n_top),
        np.full(n_top, z0 + height),
    ])
    n_side = n - n_top
    side_sign = rng.choice([-1.0, 1.0], n_side)
    sides = np.column_stack([
        rng.uniform(-length / 2, length / 2, n_side),
        side_sign * width / 2,
        rng.uniform(z0 + height * 0.3, z0 + height, n_side),
    ])
    pts = np.vstack([top, sides])
    c, s = np.cos(yaw_rad), np.sin(yaw_rad)
    rotated = pts.copy()
    rotated[:, 0] = pts[:, 0] * c - pts[:, 1] * s
    rotated[:, 1] = pts[:, 0] * s + pts[:, 1] * c
    rotated[:, 0] += cx
    rotated[:, 1] += cy
    return rotated


def test_reconstruct_bridge_stack() -> None:
    """An I-beam bridging two parallel supports yields 3 units on the right layers."""
    L, W, H = UNIT_DIMS_M["i_beam"]
    # two supports running along +Y at x=0 and x=0.1, one bridge along +X on top, centred
    support1 = _box_surface(0.00, 0.0, 0.0, L, W, H, yaw_rad=np.pi / 2, seed=1)
    support2 = _box_surface(0.10, 0.0, 0.0, L, W, H, yaw_rad=np.pi / 2, seed=2)
    bridge = _box_surface(0.05, 0.0, H, L, W, H, yaw_rad=0.0, seed=3)
    cloud = _pcd(np.vstack([support1, support2, bridge]))

    instances = reconstruct_units(cloud, "i_beam", np.eye(4))
    assert len(instances) == 3

    zs = sorted(inst.position_xyz[2] for inst in instances)
    assert abs(zs[0] - H / 2) < 0.005 and abs(zs[1] - H / 2) < 0.005    # two supports on layer 0
    assert abs(zs[2] - 1.5 * H) < 0.005                                 # bridge on layer 1

    top = max(instances, key=lambda inst: inst.position_xyz[2])
    assert abs(top.position_xyz[0] - 0.05) < 0.01                       # bridge centred between supports
    assert min(abs(top.yaw_deg % 180), 180 - abs(top.yaw_deg % 180)) < 15          # bridge along +X
    for inst in instances:
        if inst is not top:
            assert abs((inst.yaw_deg % 180) - 90) < 15                  # supports along +Y


def test_reconstruct_row_of_bricks_counts_by_geometry() -> None:
    """A touching row of 3 bricks on one layer comes back as 3 units in a line."""
    L, W, H = UNIT_DIMS_M["brick"]
    row = np.vstack([_box_surface(i * L, 0.0, 0.0, L, W, H, seed=10 + i, n=600) for i in range(3)])
    instances = reconstruct_units(_pcd(row), "brick", np.eye(4))
    assert len(instances) == 3
    xs = sorted(inst.position_xyz[0] for inst in instances)
    assert abs((xs[1] - xs[0]) - L) < 0.01 and abs((xs[2] - xs[1]) - L) < 0.01


def test_reconstruct_separate_groups_get_their_own_yaw() -> None:
    """Two physically separate units at different angles each keep their own orientation."""
    L, W, H = UNIT_DIMS_M["i_beam"]
    beam_x = _box_surface(0.0, 0.0, 0.0, L, W, H, yaw_rad=0.0, seed=20)
    beam_diag = _box_surface(0.0, 0.25, 0.0, L, W, H, yaw_rad=np.deg2rad(45), seed=21)
    instances = reconstruct_units(_pcd(np.vstack([beam_x, beam_diag])), "i_beam", np.eye(4))
    assert len(instances) == 2
    yaws = sorted(min(inst.yaw_deg % 180, 180 - inst.yaw_deg % 180) for inst in instances)
    assert yaws[0] < 15                     # the axis-aligned beam
    assert abs(yaws[1] - 45) < 15           # the diagonal beam


def test_reconstruct_rejects_unknown_shape() -> None:
    """Unknown shape reconstructs nothing instead of crashing."""
    assert reconstruct_units(_pcd(np.zeros((50, 3))), "gravel", np.eye(4)) == []


def test_place_units_fallback_returns_requested_count() -> None:
    """The grid fallback still places exactly the requested number of units."""
    rng = np.random.default_rng(0)
    pts = np.column_stack([
        rng.uniform(0.0, 0.16, 800),
        rng.uniform(0.0, 0.04, 800),
        rng.uniform(0.0, 0.02, 800),
    ])
    instances = place_units(_pcd(pts), "brick", 4, np.eye(4))
    assert len(instances) == 4
    assert all(inst.shape == "brick" for inst in instances)


def test_place_units_handles_unknown_shape_or_zero_count() -> None:
    """Unknown shape or non-positive count places nothing instead of crashing."""
    pts = np.zeros((10, 3))
    assert place_units(_pcd(pts), "gravel", 3, np.eye(4)) == []
    assert place_units(_pcd(pts), "brick", 0, np.eye(4)) == []
