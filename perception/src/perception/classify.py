"""Classify each above-ground DBSCAN blob as an amorphous "heap" or a "stack" of
discrete rigid units, so downstream steps can branch on it.

The two discriminators are geometric and complementary:
  * a stack has a flat top face -> a RANSAC plane fits its top slice tightly;
  * a stack's visible surface has low normal-vector spread -> its normals cluster,
    while a heap's continuously curved surface fans its normals out.
A blob is a stack only if BOTH agree; anything else is a heap.

Note: "top"/"height" here is the +Z axis of the cloud's own frame (the classifier
takes no plane model), so this assumes Z is roughly up -- true for the pipeline's
above-ground clusters and for the synthetic test shapes.
"""
from dataclasses import dataclass

import numpy as np
import open3d as o3d

PLANE_FIT_RESIDUAL_THRESHOLD_M = 0.008   # top-surface RANSAC inlier distance; below this the top surface counts as "flat"
FLAT_TOP_INLIER_RATIO = 0.6              # fraction of top-surface points that must fit the plane to call the blob a stack
TOP_SLICE_FRACTION = 0.25               # fraction of the blob's height (from the top down) treated as "the top surface"
NORMAL_VARIANCE_THRESHOLD = 0.15        # stacks have low normal-vector variance on flat faces; heaps have high variance

PLANE_RANSAC_N = 3                       # minimum points to define a plane (mirrors remove_ground)
PLANE_NUM_ITERATIONS = 1000             # RANSAC iterations for a stable top-surface fit (mirrors remove_ground)
NORMAL_RADIUS_M = 0.02                   # neighbourhood radius for normal estimation on the blob
NORMAL_MAX_NN = 30                       # cap neighbours per normal estimate
MIN_CLUSTER_POINTS = 30                  # below this the blob is too sparse to classify; default to "heap"

STACK_COLOR = (0.85, 0.55, 0.1)          # orange: clusters classified as stacks, in the 3D viewer
HEAP_COLOR = (0.2, 0.5, 0.9)             # blue: clusters classified as heaps, in the 3D viewer


@dataclass
class ClusterClassification:
    """Result of classifying one cluster: the label plus the two metrics behind it."""
    label: str              # "heap" or "stack"
    top_plane_inlier_ratio: float
    normal_variance: float
    confidence: float       # 0-1 heuristic combination of how decisively both metrics agree


def _clamp01(x: float) -> float:
    """Clamp to [0, 1]."""
    return max(0.0, min(1.0, x))


def _top_slice_inlier_ratio(cluster_pcd: o3d.geometry.PointCloud) -> float:
    """Fraction of the top TOP_SLICE_FRACTION-of-height points that fit a single RANSAC plane."""
    points = np.asarray(cluster_pcd.points)
    z = points[:, 2]
    z_min, z_max = float(z.min()), float(z.max())
    cutoff = z_max - TOP_SLICE_FRACTION * (z_max - z_min)
    top = cluster_pcd.select_by_index(np.where(z >= cutoff)[0])

    if len(top.points) < PLANE_RANSAC_N:
        return 0.0
    _plane, inliers = top.segment_plane(
        distance_threshold=PLANE_FIT_RESIDUAL_THRESHOLD_M,
        ransac_n=PLANE_RANSAC_N,
        num_iterations=PLANE_NUM_ITERATIONS,
    )
    return len(inliers) / len(top.points)


def _normal_variance(cluster_pcd: o3d.geometry.PointCloud) -> float:
    """Mean angular spread (1 - cos) of the blob's surface normals about their mean direction."""
    cluster_pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=NORMAL_RADIUS_M, max_nn=NORMAL_MAX_NN)
    )
    # Orient normals into a common hemisphere (+Z) so a flat face's normals don't
    # cancel out through the arbitrary sign estimate_normals assigns.
    cluster_pcd.orient_normals_to_align_with_direction([0.0, 0.0, 1.0])
    normals = np.asarray(cluster_pcd.normals)
    if len(normals) == 0:
        return 1.0

    mean_normal = normals.mean(axis=0)
    norm = np.linalg.norm(mean_normal)
    if norm < 1e-9:
        return 1.0
    mean_normal /= norm
    return float(np.mean(1.0 - normals @ mean_normal))


def classify_cluster(cluster_pcd: o3d.geometry.PointCloud) -> ClusterClassification:
    """Classify one above-ground blob as "heap" or "stack" from its top-surface planarity
    and surface-normal spread. Degenerate (very sparse) clusters default to "heap"."""
    if len(cluster_pcd.points) < MIN_CLUSTER_POINTS:
        print(f"[classify] warning: cluster has only {len(cluster_pcd.points)} points (<{MIN_CLUSTER_POINTS}), defaulting to heap")
        return ClusterClassification(label="heap", top_plane_inlier_ratio=0.0, normal_variance=1.0, confidence=0.0)

    inlier_ratio = _top_slice_inlier_ratio(cluster_pcd)
    normal_variance = _normal_variance(cluster_pcd)

    is_stack = inlier_ratio >= FLAT_TOP_INLIER_RATIO and normal_variance <= NORMAL_VARIANCE_THRESHOLD
    label = "stack" if is_stack else "heap"

    # "Stackness" score in [-1, 1]: each metric votes how far past its threshold it is.
    plane_vote = (inlier_ratio - FLAT_TOP_INLIER_RATIO) / max(1.0 - FLAT_TOP_INLIER_RATIO, 1e-9)
    normal_vote = (NORMAL_VARIANCE_THRESHOLD - normal_variance) / max(NORMAL_VARIANCE_THRESHOLD, 1e-9)
    stackness = 0.5 * (max(-1.0, min(1.0, plane_vote)) + max(-1.0, min(1.0, normal_vote)))
    confidence = _clamp01(stackness) if is_stack else _clamp01(-stackness)

    return ClusterClassification(
        label=label,
        top_plane_inlier_ratio=float(inlier_ratio),
        normal_variance=float(normal_variance),
        confidence=float(confidence),
    )
