"""Synthetic tests for per-blob volume estimation. No RealSense hardware required."""
import numpy as np
import open3d as o3d

from perception.volume import compute_volume_heightmap

GROUND_PLANE = (0.0, 0.0, 1.0, 0.0)     # z = 0 ground; height above plane == z


def _pcd(points: np.ndarray) -> o3d.geometry.PointCloud:
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))


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
