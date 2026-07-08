"""Reconstruct individual placed units from a classified blob's point cloud.

The reconstruction is layer-based, driven by the actual geometry rather than a
uniform grid:

  1. Points are expressed in the tabletop (anchor) frame and assigned to layers:
     a unit standing on layer k has its top surface near (k+1) * unit_height, so a
     point at height z belongs to layer floor(z / unit_height - 0.5) (top surfaces
     land exactly on their layer; side points fall in between and still resolve).
  2. Each layer's points are rasterized into an occupancy mask and split into
     connected components -- physically separate groups of units AT THAT LEVEL.
     This is what makes imperfect stacks work: an I-beam bridging two others is
     one component on layer 1, while its two supports are two components on
     layer 0. A max-height DEM cannot see this (the gap under the bridge would
     read as tall); per-layer point occupancy can.
  3. Each component gets an oriented minimum-area rectangle, and units are tiled
     along the rectangle's own axes -- so every group has its own position and
     yaw instead of sharing one blob-wide PCA angle.

place_units (the old uniform-grid fill) is kept as a fallback for degenerate
clusters where the layered reconstruction finds nothing.
"""
from dataclasses import dataclass
from math import atan2, ceil, cos, degrees, sin

import cv2
import numpy as np
import open3d as o3d

from perception.arithmetic import UNIT_DIMS_M

MIN_COMPONENT_FILL = 0.3        # component area below this fraction of a unit footprint = noise, skip
MIN_LAYER_POINTS = 12           # layers with fewer points than this are sensor speckle, skip
RASTER_CELLS_PER_MINOR = 4.0    # raster resolution: ~4 cells across a unit's short side
RASTER_CELL_MIN_M = 0.002       # but never finer than 2mm (keeps masks connected despite point sparsity)
TOP_SURFACE_BAND = 0.3          # points within this fraction of unit height of a layer top count as evidence


@dataclass
class UnitInstance:
    """One placed virtual unit: which prefab, where (tabletop metres), and its yaw (deg)."""
    shape: str
    position_xyz: list[float]     # in the anchor-marker (tabletop) frame, metres
    yaw_deg: float                # rotation about the tabletop normal


def _to_anchor(cluster_pcd: o3d.geometry.PointCloud, world_from_anchor: np.ndarray) -> np.ndarray:
    """Cluster points in the tabletop frame, with heights guaranteed to point up."""
    anchor_from_world = np.linalg.inv(world_from_anchor)
    points = np.asarray(cluster_pcd.points) @ anchor_from_world[:3, :3].T + anchor_from_world[:3, 3]
    if len(points) and np.median(points[:, 2]) < 0:
        points = points * np.array([1.0, 1.0, -1.0])
    return points


ELONGATION_FOR_PCA = 2.0        # eigenvalue ratio above which PCA orientation beats minAreaRect


def _rect_pose(xy: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    """Robust oriented rectangle of 2D points: (center, long_span, short_span, yaw_rad).

    Orientation: for elongated components the PCA major axis is used -- minAreaRect
    fits the noisy convex hull and can tilt by several degrees, which on a long thin
    part leaks length into the width (sin(7deg) * 145mm ~ 18mm, enough to double the
    across-count). PCA is least-squares stable there. For compact/square components
    (where PCA direction is degenerate but hull edges are meaningful) minAreaRect's
    angle is kept. Spans and centre come from 1-99% quantiles of the points projected
    onto the chosen axes, so single outliers cannot stretch the box.
    """
    centered = xy - xy.mean(axis=0)
    cov = centered.T @ centered / max(len(xy) - 1, 1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    if eigvals[0] > 1e-12 and eigvals[1] / eigvals[0] >= ELONGATION_FOR_PCA ** 2:
        major = eigvecs[:, -1]
        yaw = atan2(float(major[1]), float(major[0]))
    else:
        rect = cv2.minAreaRect(xy.astype(np.float32))
        corners = cv2.boxPoints(rect)
        edge_a = corners[1] - corners[0]
        edge_b = corners[2] - corners[1]
        long_edge = edge_a if np.linalg.norm(edge_a) >= np.linalg.norm(edge_b) else edge_b
        yaw = atan2(float(long_edge[1]), float(long_edge[0]))

    c, s = cos(yaw), sin(yaw)
    along = xy[:, 0] * c + xy[:, 1] * s
    across = -xy[:, 0] * s + xy[:, 1] * c
    a_lo, a_hi = np.quantile(along, (0.01, 0.99))
    b_lo, b_hi = np.quantile(across, (0.01, 0.99))
    mid_along = (a_lo + a_hi) / 2.0
    mid_across = (b_lo + b_hi) / 2.0
    center = np.array([mid_along * c - mid_across * s, mid_along * s + mid_across * c])
    return center, float(a_hi - a_lo), float(b_hi - b_lo), yaw


def _tile_component(
    xy: np.ndarray, shape: str, layer: int
) -> list[UnitInstance]:
    """Tile one connected component of one layer with units along its own oriented axes."""
    major_m, minor_m, height_m = UNIT_DIMS_M[shape]
    center, long_len, short_len, yaw = _rect_pose(xy)

    n_along = max(1, round(long_len / major_m))
    n_across = max(1, round(short_len / minor_m))
    c, s = cos(yaw), sin(yaw)
    z = (layer + 0.5) * height_m

    instances = []
    for j in range(n_across):
        for i in range(n_along):
            a = (i - (n_along - 1) / 2.0) * major_m       # offsets along the rect's long axis
            b = (j - (n_across - 1) / 2.0) * minor_m      # ... and short axis
            instances.append(UnitInstance(
                shape=shape,
                position_xyz=[float(center[0] + a * c - b * s), float(center[1] + a * s + b * c), float(z)],
                yaw_deg=float(degrees(yaw)),
            ))
    return instances


def reconstruct_units(
    cluster_pcd: o3d.geometry.PointCloud, shape: str, world_from_anchor: np.ndarray
) -> list[UnitInstance]:
    """Reconstruct posed unit instances from the blob's layered geometry (see module docstring).

    Returns [] for an unknown shape or when no layer yields a usable component
    (callers should then fall back to place_units with a volume-derived count).
    """
    if shape not in UNIT_DIMS_M:
        return []
    points = _to_anchor(cluster_pcd, world_from_anchor)
    if len(points) < MIN_LAYER_POINTS:
        return []

    major_m, minor_m, height_m = UNIT_DIMS_M[shape]
    cell_m = max(RASTER_CELL_MIN_M, minor_m / RASTER_CELLS_PER_MINOR)
    unit_footprint_m2 = major_m * minor_m

    # Only points near a layer's TOP surface (z close to a multiple of unit height)
    # count as occupancy evidence: a unit on layer k puts its top at (k+1)*h, and top
    # surfaces are what a downward-looking depth camera sees most of. Mid-height side
    # points are ambiguous (a bridge's lower flank overlaps its supports' tops in z)
    # and noisy tops leak across layer cuts, so both are simply discarded rather than
    # guessed -- the footprint lives in the tops.
    ratio = points[:, 2] / height_m
    frac = ratio - np.floor(ratio)
    near_top = (frac < TOP_SURFACE_BAND) | (frac > 1.0 - TOP_SURFACE_BAND)
    points = points[near_top]
    if len(points) < MIN_LAYER_POINTS:
        return []
    layers = np.clip(np.round(points[:, 2] / height_m).astype(int) - 1, 0, None)

    origin = points[:, :2].min(axis=0)
    instances: list[UnitInstance] = []

    for layer in range(int(layers.max()) + 1):
        layer_xy = points[layers == layer][:, :2]
        if len(layer_xy) < MIN_LAYER_POINTS:
            continue

        cells = np.floor((layer_xy - origin) / cell_m).astype(np.int64)
        w = int(cells[:, 0].max()) + 1
        h = int(cells[:, 1].max()) + 1
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[cells[:, 1], cells[:, 0]] = 1
        # close 1-cell gaps so sparse point sampling doesn't split a single physical unit
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

        n_labels, label_img = cv2.connectedComponents(mask)
        point_labels = label_img[cells[:, 1], cells[:, 0]]

        for label in range(1, n_labels):
            component_xy = layer_xy[point_labels == label]
            component_area_m2 = float(np.count_nonzero(label_img == label)) * cell_m ** 2
            if component_area_m2 < MIN_COMPONENT_FILL * unit_footprint_m2 or len(component_xy) < 4:
                continue
            instances.extend(_tile_component(component_xy, shape, layer))

    return instances


def _principal_yaw(xy: np.ndarray) -> float:
    """Angle (radians) of the dominant horizontal axis of the footprint via 2D PCA."""
    centered = xy - xy.mean(axis=0)
    if len(centered) < 2:
        return 0.0
    _eigvals, eigvecs = np.linalg.eigh(centered.T @ centered)
    major = eigvecs[:, -1]
    return atan2(major[1], major[0])


def place_units(
    cluster_pcd: o3d.geometry.PointCloud, shape: str, count: int, world_from_anchor: np.ndarray
) -> list[UnitInstance]:
    """Fallback: lay `count` units into a uniform grid over the blob footprint (single yaw).

    Used when reconstruct_units cannot recover structure (degenerate geometry); prefers
    a volume-derived count from arithmetic.count_units.
    """
    if shape not in UNIT_DIMS_M or count <= 0:
        return []
    points = _to_anchor(cluster_pcd, world_from_anchor)
    if len(points) == 0:
        return []
    xy = points[:, :2]
    heights = points[:, 2]

    center = xy.mean(axis=0)
    yaw = _principal_yaw(xy)
    c, s = cos(yaw), sin(yaw)
    rel = xy - center
    aligned_major = rel[:, 0] * c + rel[:, 1] * s
    aligned_minor = -rel[:, 0] * s + rel[:, 1] * c

    major_m, minor_m, height_m = UNIT_DIMS_M[shape]
    n_major = max(1, round(float(aligned_major.max() - aligned_major.min()) / major_m))
    n_minor = max(1, round(float(aligned_minor.max() - aligned_minor.min()) / minor_m))
    n_layers = max(1, ceil(count / (n_major * n_minor)), round(float(heights.max()) / height_m))

    origin_major = aligned_major.min()
    origin_minor = aligned_minor.min()

    instances: list[UnitInstance] = []
    for layer in range(n_layers):
        for j in range(n_minor):
            for i in range(n_major):
                if len(instances) >= count:
                    return instances
                a = origin_major + (i + 0.5) * major_m
                b = origin_minor + (j + 0.5) * minor_m
                instances.append(UnitInstance(
                    shape=shape,
                    position_xyz=[float(center[0] + a * c - b * s), float(center[1] + a * s + b * c),
                                  float((layer + 0.5) * height_m)],
                    yaw_deg=float(degrees(yaw)),
                ))
    return instances
