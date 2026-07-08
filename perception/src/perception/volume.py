"""Volume estimation for heap clusters.

The primary estimator rasterizes the cluster into a 2.5D digital elevation model
(DEM) on the ground plane: the plane is the reference surface, each grid cell holds
the MAX height-above-plane of the points that fall in it, and the volume is the sum
of those column heights times the cell area. This works directly from the RANSAC
plane model -- no need to rotate the cloud so the ground is axis-aligned.

A convex-hull volume is offered purely as a sanity-check figure to print alongside;
it overestimates concave piles, so it is never the reported number.
"""
import numpy as np
import open3d as o3d

HEIGHTMAP_CELL_SIZE_M = 0.005    # 5mm DEM cells; matches the voxel/point density used elsewhere in the pipeline

MIN_HEIGHTMAP_POINTS = 10        # below this the cluster is too sparse for a meaningful DEM
MIN_HULL_POINTS = 4              # a convex hull needs at least a tetrahedron's worth of points


def compute_volume_heightmap(
    cluster_pcd: o3d.geometry.PointCloud,
    plane_model: tuple[float, float, float, float],
    cell_size_m: float = HEIGHTMAP_CELL_SIZE_M,
) -> float:
    """Volume (m^3) between the cluster's top surface and the ground plane via a max-height DEM."""
    points = np.asarray(cluster_pcd.points)
    if len(points) < MIN_HEIGHTMAP_POINTS:
        print(f"[volume] warning: cluster has only {len(points)} points (<{MIN_HEIGHTMAP_POINTS}), volume=0")
        return 0.0

    a, b, c, d = plane_model
    normal = np.array([a, b, c], dtype=float)
    normal_len = np.linalg.norm(normal)
    unit_normal = normal / normal_len

    # Signed perpendicular distance to the plane = height above ground. Flip so the
    # cluster (which sits on one side of the plane) reads as positive height.
    heights = (points @ normal + d) / normal_len
    if np.median(heights) < 0:
        heights = -heights

    # Orthonormal in-plane basis (u, v) from the plane normal.
    seed = np.array([1.0, 0.0, 0.0]) if abs(unit_normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(unit_normal, seed)
    u /= np.linalg.norm(u)
    v = np.cross(unit_normal, u)

    # In-plane origin: the plane's closest point to the world origin.
    plane_origin = -(d / normal_len ** 2) * normal
    rel = points - plane_origin
    coords_u = rel @ u
    coords_v = rel @ v

    cell_u = np.floor(coords_u / cell_size_m).astype(np.int64)
    cell_v = np.floor(coords_v / cell_size_m).astype(np.int64)
    cells, inverse = np.unique(np.stack([cell_u, cell_v], axis=1), axis=0, return_inverse=True)

    cell_max = np.full(len(cells), -np.inf)
    np.maximum.at(cell_max, inverse, heights)
    cell_max = np.clip(cell_max, 0.0, None)

    return float(cell_max.sum() * cell_size_m ** 2)


def compute_volume_convex_hull(cluster_pcd: o3d.geometry.PointCloud) -> float:
    """Convex-hull volume (m^3) as a sanity check; 0.0 on degenerate/coplanar input."""
    if len(cluster_pcd.points) < MIN_HULL_POINTS:
        print(f"[volume] warning: cluster has only {len(cluster_pcd.points)} points, convex-hull volume=0")
        return 0.0
    try:
        hull, _ = cluster_pcd.compute_convex_hull()
        return float(hull.get_volume())
    except (RuntimeError, ValueError) as exc:
        print(f"[volume] warning: convex-hull volume failed ({exc}), returning 0")
        return 0.0
