"""Console reporting for detected heap clusters."""
import open3d as o3d


def print_cluster_report(clusters: list[o3d.geometry.PointCloud]) -> None:
    """Print index, point count, AABB extent, and centroid for each cluster."""
    if not clusters:
        print("No clusters found.")
        return
    for i, c in enumerate(clusters):
        aabb = c.get_axis_aligned_bounding_box()
        ex, ey, ez = aabb.get_extent()
        cx, cy, cz = c.get_center()
        print(
            f"Cluster {i:2d}: {len(c.points):6d} pts  "
            f"extent=({ex:.3f}, {ey:.3f}, {ez:.3f}) m  "
            f"centroid=({cx:.3f}, {cy:.3f}, {cz:.3f}) m"
        )
