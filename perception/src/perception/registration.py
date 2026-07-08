"""Merge multi-view frames by a global alignment of the shared marker corners.

Every frame measures the 3D positions of the marker corners it sees (via depth).
We solve for one rigid pose per frame plus one canonical world position per marker
corner, so that every frame's measured corners agree in the world frame -- a small
generalized-Procrustes / bundle problem solved by alternating iterations:

    1. fix world corners, fit each frame's pose to them (closed-form Umeyama);
    2. fix poses, re-estimate each world corner as the robust (median) average of
       all frames' transformed measurements of it;
    3. enforce the "all markers are coplanar" assumption by snapping the world
       corners back onto their common plane.

This distributes error across all frames instead of letting it accumulate down a
chain, and -- crucially for a near-planar marker scene -- the markers pin all six
DOF, which dense ICP cannot (it slides along the dominant plane). No ICP is used.
"""
from collections import defaultdict

import numpy as np
import open3d as o3d

from perception.alignment import crop_below_plane, fit_plane, snap_to_plane, umeyama_rigid

UNDER_PLANE_MARGIN_M = 0.005     # drop points more than 5mm beneath the marker plane (depth noise below the plate)
OUTPUT_VOXEL_M = 0.001           # final merge resolution; ~camera native spacing at working range, keeps texture crisp
GLOBAL_ITERATIONS = 25           # alternating pose/corner refinement passes (cheap; converges well before this)


def _fit_pose(observed: dict[int, np.ndarray], world: dict[int, np.ndarray]) -> tuple[np.ndarray | None, int]:
    """Closed-form rigid pose mapping this frame's corners into the world, or (None, 0) if no overlap."""
    shared = [tag for tag in observed if tag in world]
    if not shared:
        return None, 0
    source = np.concatenate([observed[tag] for tag in shared], axis=0)
    target = np.concatenate([world[tag] for tag in shared], axis=0)
    return umeyama_rigid(source, target), len(shared)


def _apply(transform: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Apply a 4x4 rigid transform to (N,3) points."""
    return corners @ transform[:3, :3].T + transform[:3, 3]


def global_marker_alignment(
    per_frame_corners: list[dict[int, np.ndarray] | None], iterations: int = GLOBAL_ITERATIONS
) -> tuple[list[np.ndarray | None], dict[int, np.ndarray]]:
    """Jointly solve every frame's pose and the canonical world marker corners.

    Returns (transforms, world_corners): transforms[i] maps frame i's camera into
    the world (or None if the frame shares no markers with any placed frame).
    """
    counts = [len(c) if c else 0 for c in per_frame_corners]
    seed = int(np.argmax(counts))
    world = snap_to_plane({tag: corners.copy() for tag, corners in per_frame_corners[seed].items()})
    transforms: list[np.ndarray | None] = [None] * len(per_frame_corners)

    for _ in range(iterations):
        for i, corners in enumerate(per_frame_corners):
            if corners:
                pose, _ = _fit_pose(corners, world)
                if pose is not None:
                    transforms[i] = pose

        accumulated: dict[int, list[np.ndarray]] = defaultdict(list)
        for i, corners in enumerate(per_frame_corners):
            if not corners or transforms[i] is None:
                continue
            for tag, c in corners.items():
                accumulated[tag].append(_apply(transforms[i], c))

        # Median over frames is robust to the occasional corner whose depth landed
        # on a hole or a background pixel near an object edge.
        world = {tag: np.median(np.stack(v), axis=0) for tag, v in accumulated.items()}
        world = snap_to_plane(world)

    return transforms, world


def anchor_frame(world_corners: dict[int, np.ndarray]) -> tuple[int, np.ndarray]:
    """Build a coordinate frame on the anchor marker (smallest tag id).

    Origin at the marker's top-left corner, X along its top edge (TL->TR), Y down its
    left edge (TL->BL), Z the plane normal. Returns (anchor_id, T_world_from_anchor),
    the 4x4 mapping anchor-frame coordinates into the world frame.
    """
    anchor_id = min(world_corners)
    corners = world_corners[anchor_id]           # (4,3): TL, TR, BR, BL
    origin = corners[0]
    x_axis = corners[1] - corners[0]
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_hint = corners[3] - corners[0]
    z_axis = np.cross(x_axis, y_hint)
    z_axis = z_axis / np.linalg.norm(z_axis)
    y_axis = np.cross(z_axis, x_axis)            # re-orthogonalize so the frame is exactly orthonormal

    transform = np.eye(4)
    transform[:3, :3] = np.column_stack([x_axis, y_axis, z_axis])
    transform[:3, 3] = origin
    return anchor_id, transform


def _corner_residual_mm(observed: dict[int, np.ndarray], transform: np.ndarray, world: dict[int, np.ndarray]) -> float:
    """RMS distance (mm) between a frame's transformed corners and the world corners."""
    errors = [
        np.linalg.norm(_apply(transform, c) - world[tag], axis=1)
        for tag, c in observed.items() if tag in world
    ]
    if not errors:
        return 0.0
    flat = np.concatenate(errors)
    return float(np.sqrt((flat ** 2).mean()) * 1000)


def align_and_merge(
    frames: list[tuple[o3d.geometry.PointCloud, dict[int, np.ndarray]]], output_voxel_m: float = OUTPUT_VOXEL_M
) -> tuple[o3d.geometry.PointCloud, list[np.ndarray | None]]:
    """Globally align every frame via shared markers and merge the clouds.

    frames: list of (point cloud in camera frame, {tag_id: (4,3) camera-frame corners}).
    Returns (merged cloud in the world frame downsampled to output_voxel_m, camera_poses),
    where camera_poses[i] is the 4x4 pose of frame i's camera expressed in the anchor
    marker's frame (its rotation = camera orientation, its translation = camera position,
    both relative to the anchor marker), or None for a frame that could not be placed.
    """
    if not frames:
        return o3d.geometry.PointCloud(), []

    per_frame_corners = [snap_to_plane(cc) if cc else None for _pcd, cc in frames]
    if not any(per_frame_corners):
        print("[align] no markers with valid depth in any frame -- cannot align")
        return o3d.geometry.PointCloud(), [None] * len(frames)

    transforms, world_corners = global_marker_alignment(per_frame_corners)
    placed = sum(1 for t in transforms if t is not None)

    merged = o3d.geometry.PointCloud()
    residuals = []
    for i, ((pcd, _cc), transform) in enumerate(zip(frames, transforms)):
        if transform is None:
            print(f"[align] frame {i + 1}: shares no markers with any placed frame, skipped")
            continue
        rms = _corner_residual_mm(per_frame_corners[i], transform, world_corners)
        residuals.append(rms)
        print(f"[align] frame {i + 1}: {len(per_frame_corners[i])} markers | corner residual {rms:.2f} mm")
        merged += o3d.geometry.PointCloud(pcd).transform(transform)

    if residuals:
        print(f"[align] global fit over {placed}/{len(frames)} frames | mean corner residual {np.mean(residuals):.2f} mm")

    # Re-express each camera pose relative to the anchor marker (world -> anchor).
    camera_poses: list[np.ndarray | None] = [None] * len(frames)
    if world_corners:
        anchor_id, world_from_anchor = anchor_frame(world_corners)
        anchor_from_world = np.linalg.inv(world_from_anchor)
        for i, transform in enumerate(transforms):
            if transform is not None:
                camera_poses[i] = anchor_from_world @ transform
        print(f"[align] anchor = marker id {anchor_id}; camera poses reported relative to it")

        centroid, normal = fit_plane(np.concatenate(list(world_corners.values()), axis=0))
        camera_centers = np.array([t[:3, 3] for t in transforms if t is not None])
        camera_side = camera_centers.mean(axis=0)
        before = len(merged.points)
        merged = crop_below_plane(merged, centroid, normal, camera_side, UNDER_PLANE_MARGIN_M)
        print(f"[align] dropped {before - len(merged.points)} points >{UNDER_PLANE_MARGIN_M * 1000:.0f}mm under the marker plane")

    return merged.voxel_down_sample(output_voxel_m), camera_poses
