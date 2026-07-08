"""Turn a classified blob (shape + count) into individual placed unit instances.

We cannot see each unit precisely from surface scans, so placement is a physically
grounded *estimate*: orient a grid to the blob's dominant horizontal axis (PCA of its
footprint), size the grid from the blob's measured extent and the unit envelope, and
lay `count` units into the grid cells (filling layer by layer, stacking up if needed).
Each instance gets a position on the tabletop (anchor-marker frame, metres) and a yaw
about the vertical -- exactly what a Unity scene needs to instantiate a prefab.

This is the hand-off to a digital twin: per-blob aggregates become per-object poses.
"""
from dataclasses import dataclass
from math import atan2, ceil, cos, sin

import numpy as np
import open3d as o3d

from perception.arithmetic import UNIT_DIMS_M


@dataclass
class UnitInstance:
    """One placed virtual unit: which prefab, where (tabletop metres), and its yaw (deg)."""
    shape: str
    position_xyz: list[float]     # in the anchor-marker (tabletop) frame, metres
    yaw_deg: float                # rotation about the tabletop normal


def _principal_yaw(xy: np.ndarray) -> float:
    """Angle (radians) of the dominant horizontal axis of the footprint via 2D PCA."""
    centered = xy - xy.mean(axis=0)
    if len(centered) < 2:
        return 0.0
    _eigvals, eigvecs = np.linalg.eigh(centered.T @ centered)
    major = eigvecs[:, -1]        # eigenvector of the largest eigenvalue
    return atan2(major[1], major[0])


def place_units(
    cluster_pcd: o3d.geometry.PointCloud, shape: str, count: int, world_from_anchor: np.ndarray
) -> list[UnitInstance]:
    """Lay `count` units of `shape` into the blob's measured footprint, as posed instances.

    Returns [] if the shape is unknown or count <= 0. Positions are in the anchor (tabletop)
    frame; the grid is oriented to the blob's PCA major axis and stacked upward if the
    footprint cannot hold `count` in a single layer.
    """
    if shape not in UNIT_DIMS_M or count <= 0:
        return []

    anchor_from_world = np.linalg.inv(world_from_anchor)
    points = np.asarray(cluster_pcd.points) @ anchor_from_world[:3, :3].T + anchor_from_world[:3, 3]
    if len(points) == 0:
        return []
    xy = points[:, :2]
    heights = points[:, 2]
    if np.median(heights) < 0:                    # ensure heights point up from the tabletop
        heights = -heights

    center = xy.mean(axis=0)
    yaw = _principal_yaw(xy)
    c, s = cos(yaw), sin(yaw)
    # Express the footprint in the grid's own frame (rotate by -yaw about the centroid).
    rel = xy - center
    aligned_major = rel[:, 0] * c + rel[:, 1] * s
    aligned_minor = -rel[:, 0] * s + rel[:, 1] * c

    major_m, minor_m, height_m = UNIT_DIMS_M[shape]
    span_major = float(aligned_major.max() - aligned_major.min())
    span_minor = float(aligned_minor.max() - aligned_minor.min())
    top = float(heights.max())

    n_major = max(1, round(span_major / major_m))
    n_minor = max(1, round(span_minor / minor_m))
    n_layers = max(1, ceil(count / (n_major * n_minor)), round(top / height_m))

    # Grid cell centres in the aligned frame, origin at the footprint's min corner.
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
                # rotate the cell centre back into the tabletop frame and offset by the centroid
                x = center[0] + a * c - b * s
                y = center[1] + a * s + b * c
                z = (layer + 0.5) * height_m
                instances.append(UnitInstance(
                    shape=shape,
                    position_xyz=[float(x), float(y), float(z)],
                    yaw_deg=float(np.degrees(yaw)),
                ))
    return instances
