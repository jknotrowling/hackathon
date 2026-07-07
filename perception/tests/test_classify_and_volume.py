"""Synthetic tests for heap/stack classification and heap volume estimation.
No RealSense hardware required; shapes are generated analytically."""
import numpy as np
import open3d as o3d

from perception.classify import classify_cluster
from perception.volume import compute_volume_heightmap

GROUND_PLANE = (0.0, 0.0, 1.0, 0.0)     # z = 0 ground; height above plane == z


def _pcd(points: np.ndarray) -> o3d.geometry.PointCloud:
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))


def _dome(ax=0.08, ay=0.08, az=0.06, n=6000, seed=0) -> np.ndarray:
    """Surface points on the upper half of an ellipsoid (a curved, non-planar top)."""
    rng = np.random.default_rng(seed)
    theta = np.arccos(rng.uniform(0.0, 1.0, n))     # polar angle from the top, 0..90deg
    phi = rng.uniform(0.0, 2 * np.pi, n)
    x = ax * np.sin(theta) * np.cos(phi)
    y = ay * np.sin(theta) * np.sin(phi)
    z = az * np.cos(theta)
    return np.column_stack([x, y, z])


def _flat_topped_box(w=0.2, d=0.15, h=0.1, n_top=20000, n_side=400, noise=0.002, seed=1) -> np.ndarray:
    """A flat top face (dominant, as a camera sees from above) plus sparse vertical walls."""
    rng = np.random.default_rng(seed)
    tx = rng.uniform(-w / 2, w / 2, n_top)
    ty = rng.uniform(-d / 2, d / 2, n_top)
    tz = np.full(n_top, h) + rng.normal(0.0, noise, n_top)
    top = np.column_stack([tx, ty, tz])

    wall = rng.integers(0, 4, n_side)
    along = rng.uniform(-0.5, 0.5, n_side)
    sz = rng.uniform(0.0, h, n_side)
    sx = np.where(wall == 0, -w / 2, np.where(wall == 1, w / 2, along * w))
    sy = np.where(wall <= 1, along * d, np.where(wall == 2, -d / 2, d / 2))
    side = np.column_stack([sx, sy, sz])
    return np.vstack([top, side])


def _solid_prism(w=0.2, d=0.15, h=0.1, n=60000, seed=2) -> np.ndarray:
    """Points filling a rectangular prism; max height per cell recovers the top face."""
    rng = np.random.default_rng(seed)
    return np.column_stack([rng.uniform(0, w, n), rng.uniform(0, d, n), rng.uniform(0, h, n)])


def _solid_cone(radius=0.1, height=0.1, n=120000, seed=3) -> np.ndarray:
    """Points filling a cone; max height per cell recovers the conical surface."""
    rng = np.random.default_rng(seed)
    xs = rng.uniform(-radius, radius, n)
    ys = rng.uniform(-radius, radius, n)
    r = np.hypot(xs, ys)
    keep = r <= radius
    xs, ys, r = xs[keep], ys[keep], r[keep]
    zs = rng.uniform(0.0, height * (1.0 - r / radius))
    return np.column_stack([xs, ys, zs])


def test_curved_top_is_classified_heap() -> None:
    """A dome (continuously curved top) classifies as a heap."""
    result = classify_cluster(_pcd(_dome()))
    assert result.label == "heap"


def test_flat_topped_box_is_classified_stack() -> None:
    """A flat-topped box (planar top, clustered normals) classifies as a stack."""
    result = classify_cluster(_pcd(_flat_topped_box()))
    assert result.label == "stack"


def test_heightmap_volume_matches_known_prism() -> None:
    """DEM volume of a 0.2 x 0.15 x 0.1 prism is within 15% of the analytical 0.003 m^3."""
    expected = 0.2 * 0.15 * 0.1
    volume = compute_volume_heightmap(_pcd(_solid_prism()), GROUND_PLANE)
    assert abs(volume - expected) / expected < 0.15


def test_heightmap_volume_matches_known_cone() -> None:
    """DEM volume of a cone (R=0.1, H=0.1) is within 15% of the analytical (1/3)*pi*R^2*H."""
    expected = (1.0 / 3.0) * np.pi * 0.1 ** 2 * 0.1
    volume = compute_volume_heightmap(_pcd(_solid_cone()), GROUND_PLANE)
    assert abs(volume - expected) / expected < 0.15
