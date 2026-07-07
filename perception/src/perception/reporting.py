"""Console reporting for detected heap clusters, with heap/stack classification and volume."""
import open3d as o3d

from perception.classify import ClusterClassification, classify_cluster
from perception.volume import compute_volume_convex_hull, compute_volume_heightmap


def print_cluster_report(
    clusters: list[o3d.geometry.PointCloud],
    plane_model: tuple[float, float, float, float],
) -> list[ClusterClassification]:
    """Print per-cluster geometry, classification, and (for heaps) volume.

    Returns the per-cluster classifications so the caller can reuse them (e.g. to
    color-code the viewer) instead of recomputing.
    """
    if not clusters:
        print("No clusters found.")
        return []

    classifications: list[ClusterClassification] = []
    for i, c in enumerate(clusters):
        aabb = c.get_axis_aligned_bounding_box()
        ex, ey, ez = aabb.get_extent()
        cx, cy, cz = c.get_center()
        print(
            f"Cluster {i:2d}: {len(c.points):6d} pts  "
            f"extent=({ex:.3f}, {ey:.3f}, {ez:.3f}) m  "
            f"centroid=({cx:.3f}, {cy:.3f}, {cz:.3f}) m"
        )

        classification = classify_cluster(c)
        classifications.append(classification)

        if classification.label == "heap":
            volume = compute_volume_heightmap(c, plane_model)
            hull_volume = compute_volume_convex_hull(c)
            print(
                f"           -> heap (confidence {classification.confidence:.2f})  "
                f"volume={volume:.5f} m^3  (convex-hull sanity-check={hull_volume:.5f} m^3)"
            )
        else:
            print(
                f"           -> stack (confidence {classification.confidence:.2f})  "
                "(unit analysis: not yet implemented)"
            )

    return classifications
