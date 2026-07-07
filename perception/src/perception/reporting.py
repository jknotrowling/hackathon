"""Console reporting for detected blobs: geometry plus a per-blob volume estimate."""
import open3d as o3d

from perception.volume import compute_volume_convex_hull, compute_volume_heightmap


def print_cluster_report(
    clusters: list[o3d.geometry.PointCloud],
    plane_model: tuple[float, float, float, float],
) -> list[float]:
    """Enumerate every blob and print its point count, AABB extent, centroid, and volume.

    Volume is the max-height DEM estimate above the ground plane, with the convex-hull
    volume printed alongside as a sanity check. Returns the per-blob DEM volumes (m^3).
    """
    if not clusters:
        print("No blobs found.")
        return []

    volumes: list[float] = []
    for i, c in enumerate(clusters):
        aabb = c.get_axis_aligned_bounding_box()
        ex, ey, ez = aabb.get_extent()
        cx, cy, cz = c.get_center()
        volume = compute_volume_heightmap(c, plane_model)
        hull_volume = compute_volume_convex_hull(c)
        volumes.append(volume)
        print(
            f"Blob {i:2d}: {len(c.points):6d} pts  "
            f"extent=({ex:.3f}, {ey:.3f}, {ez:.3f}) m  "
            f"centroid=({cx:.3f}, {cy:.3f}, {cz:.3f}) m"
        )
        print(
            f"          volume={volume:.5f} m^3  (convex-hull sanity-check={hull_volume:.5f} m^3)"
        )

    return volumes
