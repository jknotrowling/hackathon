"""Synthetic test for the top-down tabletop blob grid. No RealSense hardware required."""
import os

import cv2
import numpy as np
import open3d as o3d

from perception.topdown import HEIGHT_UNIT_M, _preview_path, export_topdown_grid


def _pcd(points: np.ndarray) -> o3d.geometry.PointCloud:
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))


def test_topdown_grid_encodes_blob_ids_and_heights(tmp_path) -> None:
    """Two blobs at known heights rasterize to a single image encoding id + height, empty cells dropped."""
    rng = np.random.default_rng(0)
    # blob 0: a patch at height ~0.02 m; blob 1: a separate patch at ~0.05 m. Anchor frame == world here.
    blob0 = np.column_stack([rng.uniform(0.00, 0.04, 500), rng.uniform(0.00, 0.04, 500), np.full(500, 0.02)])
    blob1 = np.column_stack([rng.uniform(0.10, 0.14, 500), rng.uniform(0.10, 0.14, 500), np.full(500, 0.05)])
    clusters = [_pcd(blob0), _pcd(blob1)]

    out = os.path.join(tmp_path, "topdown.png")
    result = export_topdown_grid(clusters, np.eye(4), out, cell_size_m=0.003)
    assert result == out and os.path.isfile(out)

    image = cv2.imread(out, cv2.IMREAD_UNCHANGED)
    assert image.dtype == np.uint16 and image.shape[2] == 3
    blob_map = image[..., 2]          # R = blob id + 1 (0 = empty)
    height_map = image[..., 1]        # G = height in 0.1 mm units

    # Both blob ids present (stored as id+1 -> values 1 and 2); background is dropped (0).
    assert set(np.unique(blob_map)) == {0, 1, 2}
    assert (blob_map == 0).any()      # empty/dropped cells exist between the two patches

    # Heights decode back to the injected values.
    h0 = np.median(height_map[blob_map == 1]) * HEIGHT_UNIT_M
    h1 = np.median(height_map[blob_map == 2]) * HEIGHT_UNIT_M
    assert abs(h0 - 0.02) < 0.002
    assert abs(h1 - 0.05) < 0.002

    # A viewable 8-bit color companion is written with a black (dropped) background.
    preview_path = _preview_path(out)
    assert os.path.isfile(preview_path)
    preview = cv2.imread(preview_path, cv2.IMREAD_UNCHANGED)
    assert preview.dtype == np.uint8 and preview.shape[2] == 3
    assert preview.max() > 0 and (preview.reshape(-1, 3) == 0).all(axis=1).any()  # colored blobs + black bg
