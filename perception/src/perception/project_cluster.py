"""Project blob clusters back into the captured camera frames to get 2D crops.

A "captured frame" is (color_bgr, cam_to_world, intrinsics_matrix): the color image,
the 4x4 pose mapping that camera's coordinates into the world frame (i.e. the camera's
pose in the world), and its 3x3 pinhole intrinsics. Projecting a cluster's AABB into
a frame yields the pixel bounding box the blob occupies there; the projected area is a
simple proxy for how well that view sees the blob.
"""
import numpy as np
import open3d as o3d

Frame = tuple[np.ndarray, np.ndarray, np.ndarray]           # (color_bgr, cam_to_world 4x4, K 3x3)
BBox = tuple[int, int, int, int]                            # (x1, y1, x2, y2)


def project_cluster_to_frame(cluster_pcd: o3d.geometry.PointCloud, frame: Frame) -> BBox | None:
    """Project a cluster's AABB into a frame; return its clipped pixel bbox, or None if not visible."""
    color_bgr, cam_to_world, intrinsics_matrix = frame
    corners = np.asarray(cluster_pcd.get_axis_aligned_bounding_box().get_box_points())   # (8, 3) world

    world_to_cam = np.linalg.inv(cam_to_world)
    in_cam = corners @ world_to_cam[:3, :3].T + world_to_cam[:3, 3]
    in_front = in_cam[:, 2] > 1e-6
    if not np.any(in_front):
        return None
    in_cam = in_cam[in_front]

    fx, fy = intrinsics_matrix[0, 0], intrinsics_matrix[1, 1]
    cx, cy = intrinsics_matrix[0, 2], intrinsics_matrix[1, 2]
    u = fx * in_cam[:, 0] / in_cam[:, 2] + cx
    v = fy * in_cam[:, 1] / in_cam[:, 2] + cy

    img_h, img_w = color_bgr.shape[:2]
    x1 = max(0, int(np.floor(u.min())))
    y1 = max(0, int(np.floor(v.min())))
    x2 = min(img_w, int(np.ceil(u.max())))
    y2 = min(img_h, int(np.ceil(v.max())))
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    return (x1, y1, x2, y2)


def crop_to_bbox(color_bgr: np.ndarray, bbox: BBox) -> np.ndarray:
    """Return the sub-image of color_bgr inside bbox (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = bbox
    return color_bgr[y1:y2, x1:x2]


def rank_frames_for_cluster(
    cluster_pcd: o3d.geometry.PointCloud, captured_frames: list[Frame]
) -> list[tuple[np.ndarray, BBox, float]]:
    """Rank every frame that sees the cluster by projected pixel area (largest first).

    Returns all valid projections as (color_bgr, bbox, score) with score = bbox area;
    no filtering beyond visibility.
    """
    ranked: list[tuple[np.ndarray, BBox, float]] = []
    for frame in captured_frames:
        bbox = project_cluster_to_frame(cluster_pcd, frame)
        if bbox is None:
            continue
        area = float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        ranked.append((frame[0], bbox, area))
    ranked.sort(key=lambda item: item[2], reverse=True)
    return ranked


def pick_best_frame_for_cluster(
    cluster_pcd: o3d.geometry.PointCloud, captured_frames: list[Frame]
) -> tuple[np.ndarray, BBox] | None:
    """The single best view of a cluster (largest projected area), or None if unseen."""
    ranked = rank_frames_for_cluster(cluster_pcd, captured_frames)
    if not ranked:
        return None
    color_bgr, bbox, _score = ranked[0]
    return (color_bgr, bbox)
