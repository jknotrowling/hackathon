"""Depth-based multi-frame alignment from shared markers on a common plane.

The idea, in one sentence: because the RealSense measures depth directly, every
detected marker corner has a real 3D position -- so aligning two frames is just
finding the rigid transform between the 3D corners of the markers they share
(closed-form Kabsch/Umeyama), with no monocular pose ambiguity and no depth
"fanning". All markers are assumed coplanar, which lets us snap corners onto a
single fitted plane to kill per-corner depth noise along the plane normal.

Correspondence is trivial: ArUco always returns a marker's 4 corners in the same
marker-relative order (TL, TR, BR, BL) regardless of viewpoint, so corner i of
marker m in one frame matches corner i of marker m in another.
"""
import numpy as np
import open3d as o3d

DEPTH_WINDOW_PX = 2          # half-size of the pixel window used to sample a robust corner depth
MIN_VALID_DEPTH_M = 0.05     # below this a depth reading is treated as invalid/missing


def _sample_depth(depth_m: np.ndarray, u: float, v: float, window: int = DEPTH_WINDOW_PX) -> float | None:
    """Median of the valid depths in a small window around pixel (u, v); None if all invalid.

    A single corner pixel often lands on a depth hole or a noisy edge; the window
    median is far steadier and cheap.
    """
    h, w = depth_m.shape
    ui, vi = int(round(u)), int(round(v))
    if not (0 <= ui < w and 0 <= vi < h):
        return None
    patch = depth_m[max(0, vi - window):vi + window + 1, max(0, ui - window):ui + window + 1]
    valid = patch[patch > MIN_VALID_DEPTH_M]
    if valid.size == 0:
        return None
    return float(np.median(valid))


def _deproject(u: float, v: float, depth: float, intrinsics_matrix: np.ndarray) -> np.ndarray:
    """Back-project pixel (u, v) at metric depth into the camera frame (X right, Y down, Z forward)."""
    fx, fy = intrinsics_matrix[0, 0], intrinsics_matrix[1, 1]
    cx, cy = intrinsics_matrix[0, 2], intrinsics_matrix[1, 2]
    return np.array([(u - cx) / fx * depth, (v - cy) / fy * depth, depth])


def deproject_corners(
    detections: dict[int, np.ndarray], depth_m: np.ndarray, intrinsics_matrix: np.ndarray
) -> dict[int, np.ndarray]:
    """Turn 2D marker corners into 3D camera-frame corners using the depth map.

    Returns {tag_id: (4, 3)}; a marker is dropped entirely if any of its 4 corners
    has no valid depth (a partial marker would corrupt the rigid fit).
    """
    corners_3d: dict[int, np.ndarray] = {}
    for tag_id, corners_2d in detections.items():
        points = []
        for u, v in corners_2d:
            depth = _sample_depth(depth_m, u, v)
            if depth is None:
                break
            points.append(_deproject(u, v, depth, intrinsics_matrix))
        if len(points) == 4:
            corners_3d[tag_id] = np.array(points)
    return corners_3d


def fit_plane(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares plane through points; returns (centroid, unit_normal)."""
    centroid = points.mean(axis=0)
    _, _, vh = np.linalg.svd(points - centroid)
    normal = vh[-1]
    return centroid, normal / np.linalg.norm(normal)


def snap_to_plane(corners_by_id: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
    """Project every corner onto the single plane fitted to all corners in the frame.

    Removes per-corner depth noise along the plane normal -- the dominant error
    source -- while leaving the well-observed in-plane positions untouched.
    """
    all_points = np.concatenate(list(corners_by_id.values()), axis=0)
    if len(all_points) < 3:
        return corners_by_id
    centroid, normal = fit_plane(all_points)
    snapped: dict[int, np.ndarray] = {}
    for tag_id, corners in corners_by_id.items():
        offsets = (corners - centroid) @ normal
        snapped[tag_id] = corners - np.outer(offsets, normal)
    return snapped


def crop_below_plane(
    pcd: o3d.geometry.PointCloud, centroid: np.ndarray, normal: np.ndarray,
    camera_origin: np.ndarray, margin_m: float,
) -> o3d.geometry.PointCloud:
    """Drop points more than margin_m under the plane (the side facing away from the camera).

    The plane normal is oriented to point toward camera_origin first, so "under" is
    unambiguous: signed height = (p - centroid) . normal, and anything below -margin_m
    is beneath the marker plate (real geometry never lives there, only depth noise).
    """
    normal = normal / np.linalg.norm(normal)
    if np.dot(camera_origin - centroid, normal) < 0:
        normal = -normal

    points = np.asarray(pcd.points)
    if len(points) == 0:
        return pcd
    signed_height = (points - centroid) @ normal
    keep = np.where(signed_height >= -margin_m)[0]
    return pcd.select_by_index(keep)


def umeyama_rigid(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Closed-form rigid transform (rotation + translation, no scale) mapping source onto target.

    source and target are (N, 3) corresponding points. Uses the SVD/Kabsch
    solution with a reflection guard so R is always a proper rotation.
    """
    source_centroid = source.mean(axis=0)
    target_centroid = target.mean(axis=0)
    covariance = (source - source_centroid).T @ (target - target_centroid)
    u, _, vh = np.linalg.svd(covariance)
    d = np.sign(np.linalg.det(vh.T @ u.T))
    correction = np.diag([1.0, 1.0, d])
    rotation = vh.T @ correction @ u.T
    translation = target_centroid - rotation @ source_centroid

    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform
