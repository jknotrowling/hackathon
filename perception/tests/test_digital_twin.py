"""Tests for digital-twin unit placement. No hardware or model needed."""
import numpy as np
import open3d as o3d

from perception.arithmetic import UNIT_DIMS_M
from perception.digital_twin import place_units


def _pcd(points: np.ndarray) -> o3d.geometry.PointCloud:
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))


def test_place_units_returns_requested_count_within_footprint() -> None:
    """N units are placed, all inside the blob footprint, at plausible heights."""
    rng = np.random.default_rng(0)
    # a footprint ~0.16 x 0.04 m, one brick-height tall, at tabletop origin (world == anchor)
    pts = np.column_stack([
        rng.uniform(0.0, 0.16, 800),
        rng.uniform(0.0, 0.04, 800),
        rng.uniform(0.0, 0.02, 800),
    ])
    instances = place_units(_pcd(pts), "brick", 4, np.eye(4))

    assert len(instances) == 4
    assert all(inst.shape == "brick" for inst in instances)
    _major, _minor, height = UNIT_DIMS_M["brick"]
    for inst in instances:
        x, y, z = inst.position_xyz
        assert -0.02 <= x <= 0.18 and -0.02 <= y <= 0.06     # within the footprint (+ half a cell)
        assert 0.0 < z <= 0.03                               # sitting on the table, one layer up


def test_place_units_orients_to_the_major_axis() -> None:
    """A long, thin blob along a diagonal yields a yaw near that diagonal."""
    t = np.linspace(0, 0.3, 500)
    pts = np.column_stack([t, t, np.full_like(t, 0.02)])     # 45-degree line
    instances = place_units(_pcd(pts), "i_beam", 2, np.eye(4))
    assert len(instances) == 2
    yaw = instances[0].yaw_deg % 180
    assert abs(yaw - 45) < 15


def test_place_units_handles_unknown_shape_or_zero_count() -> None:
    """Unknown shape or non-positive count places nothing instead of crashing."""
    pts = np.zeros((10, 3))
    assert place_units(_pcd(pts), "gravel", 3, np.eye(4)) == []
    assert place_units(_pcd(pts), "brick", 0, np.eye(4)) == []
