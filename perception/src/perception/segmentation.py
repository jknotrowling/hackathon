"""Point-cloud preprocessing: downsampling, ground-plane removal, and heap clustering."""
import numpy as np
import open3d as o3d

VOXEL_SIZE = 0.003           # 3 mm voxels: resolves fist-sized rocks, cheap at table/pile scale
SOR_NB_NEIGHBORS = 20        # statistical outlier removal: neighbors sampled per point
SOR_STD_RATIO = 2.0          # statistical outlier removal: moderate aggressiveness

PLANE_DIST_THRESH = 0.008    # 8 mm: matches typical D4xx depth noise at 1-2 m range
PLANE_RANSAC_N = 3           # minimum points needed to define a plane
PLANE_NUM_ITERATIONS = 1000  # RANSAC iterations for a stable ground fit

DBSCAN_EPS = 0.02            # 2 cm: gap size that separates distinct heaps
DBSCAN_MIN_POINTS = 50       # clusters smaller than this are treated as noise/debris
RANDOM_SEED = 42             # deterministic cluster color palette

GROUND_COLOR = (0.5, 0.5, 0.5)
ABOVE_COLOR = (1.0, 0.55, 0.0)    # orange
NOISE_COLOR = (0.0, 0.0, 0.0)     # black for DBSCAN noise (label == -1)


def preprocess(pcd: o3d.geometry.PointCloud, voxel: float = VOXEL_SIZE) -> o3d.geometry.PointCloud:
    """Downsample to a uniform voxel grid, then drop statistical outliers."""
    down = pcd.voxel_down_sample(voxel)
    clean, _ = down.remove_statistical_outlier(nb_neighbors=SOR_NB_NEIGHBORS, std_ratio=SOR_STD_RATIO)
    return clean


def remove_ground(
    pcd: o3d.geometry.PointCloud,
) -> tuple[o3d.geometry.PointCloud, o3d.geometry.PointCloud, tuple[float, float, float, float]]:
    """RANSAC-fit the dominant plane (the ground, whatever its tilt) and split
    the cloud into ground (gray) and above-ground points."""
    plane_model, inliers = pcd.segment_plane(
        distance_threshold=PLANE_DIST_THRESH,
        ransac_n=PLANE_RANSAC_N,
        num_iterations=PLANE_NUM_ITERATIONS,
    )
    ground = pcd.select_by_index(inliers)
    above = pcd.select_by_index(inliers, invert=True)
    ground.paint_uniform_color(GROUND_COLOR)
    return ground, above, tuple(plane_model)


def cluster_heaps(
    pcd: o3d.geometry.PointCloud, eps: float = DBSCAN_EPS, min_points: int = DBSCAN_MIN_POINTS
) -> tuple[o3d.geometry.PointCloud, list[o3d.geometry.PointCloud]]:
    """DBSCAN-cluster the above-ground points into candidate heaps. Noise
    (label == -1) is colored black; each cluster gets a deterministic color."""
    labels = np.array(pcd.cluster_dbscan(eps=eps, min_points=min_points, print_progress=False))
    aggregate = o3d.geometry.PointCloud(pcd)
    if labels.size == 0:
        return aggregate, []

    max_label = int(labels.max())
    rng = np.random.default_rng(RANDOM_SEED)
    palette = rng.random((max(max_label + 1, 1), 3))

    colors = np.zeros((labels.shape[0], 3))
    clusters = []
    for i in range(max_label + 1):
        idx = np.where(labels == i)[0]
        colors[idx] = palette[i]
        cluster = pcd.select_by_index(idx)
        cluster.paint_uniform_color(palette[i])
        clusters.append(cluster)
    colors[labels == -1] = NOISE_COLOR
    aggregate.colors = o3d.utility.Vector3dVector(colors)
    return aggregate, clusters
