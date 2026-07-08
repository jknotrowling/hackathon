"""Top-down (bird's-eye) rasterization of the detected blobs onto the tabletop.

Looks straight down the tabletop normal and rasterizes the blobs (the DBSCAN
clusters shown in viewer stage 4) into a regular grid whose axes are the anchor
marker's X/Y -- i.e. real coordinates on the tabletop. Every grid cell covered by
a blob encodes two things, packed into one 16-bit PNG:

    channel R (index 2): blob id + 1   (0 = no blob -> that pixel is dropped)
    channel G (index 1): height above the tabletop, in 0.1 mm units (uint16)
    channel B (index 0): unused (0)

Where several points share a cell, the tallest wins (its blob id and height are
kept). Cells no blob falls into stay all-zero, so non-blob pixels are dropped.
Reload with cv2.imread(path, cv2.IMREAD_UNCHANGED); blob index = R - 1,
height_m = G * HEIGHT_UNIT_M.
"""
import os

import cv2
import numpy as np
import open3d as o3d

TOPDOWN_CELL_SIZE_M = 0.003     # 3 mm grid cells on the tabletop
HEIGHT_UNIT_M = 0.0001          # height stored in 0.1 mm units (uint16 -> up to 6.55 m)
PREVIEW_MIN_SIZE_PX = 600       # upscale the viewable preview so its longer side is at least this many pixels


def _preview_path(out_path: str) -> str:
    """Companion preview path: '<name>.png' -> '<name>_preview.png'."""
    root, ext = os.path.splitext(out_path)
    return f"{root}_preview{ext or '.png'}"


def _write_preview(
    blob_map: np.ndarray, height_map: np.ndarray, n_blobs: int, out_path: str
) -> str:
    """Write a human-viewable image: distinct color per blob, brightness by height, black elsewhere."""
    hues = np.linspace(0, 179, max(n_blobs, 1), endpoint=False).astype(np.uint8)
    hsv = np.stack([hues, np.full_like(hues, 255), np.full_like(hues, 255)], axis=1).reshape(-1, 1, 3)
    palette = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR).reshape(-1, 3).astype(np.float32)   # (n_blobs, 3)

    mask = blob_map > 0
    ids0 = np.clip(blob_map.astype(np.int64) - 1, 0, max(n_blobs - 1, 0))
    heights_m = height_map.astype(np.float32) * HEIGHT_UNIT_M
    h_max = float(heights_m[mask].max()) if mask.any() else 1.0
    h_max = h_max if h_max > 1e-6 else 1.0
    brightness = 0.35 + 0.65 * (heights_m / h_max)          # floor so low blobs stay visible
    preview = (palette[ids0] * brightness[..., None]).astype(np.uint8)
    preview[~mask] = 0

    height, width = blob_map.shape
    scale = max(1, PREVIEW_MIN_SIZE_PX // max(width, height))
    if scale > 1:
        preview = cv2.resize(preview, (width * scale, height * scale), interpolation=cv2.INTER_NEAREST)

    preview_path = _preview_path(out_path)
    cv2.imwrite(preview_path, preview)
    return preview_path


def export_topdown_grid(
    clusters: list[o3d.geometry.PointCloud],
    world_from_anchor: np.ndarray,
    out_path: str = "captures/topdown.png",
    cell_size_m: float = TOPDOWN_CELL_SIZE_M,
) -> str | None:
    """Rasterize blobs into a top-down tabletop grid image; return out_path (or None if empty)."""
    if not clusters:
        print("[topdown] no blobs to export")
        return None

    anchor_from_world = np.linalg.inv(world_from_anchor)
    rotation = anchor_from_world[:3, :3]
    translation = anchor_from_world[:3, 3]

    xs, ys, heights, ids = [], [], [], []
    for blob_id, cluster in enumerate(clusters):
        points = np.asarray(cluster.points)
        if len(points) == 0:
            continue
        in_anchor = points @ rotation.T + translation     # tabletop frame: x,y on the table, z = height
        xs.append(in_anchor[:, 0])
        ys.append(in_anchor[:, 1])
        heights.append(in_anchor[:, 2])
        ids.append(np.full(len(points), blob_id))
    if not xs:
        print("[topdown] no blobs to export")
        return None

    xs = np.concatenate(xs)
    ys = np.concatenate(ys)
    heights = np.concatenate(heights)
    ids = np.concatenate(ids)

    # Blobs sit above the tabletop; if the anchor's Z happens to point into the table, flip up.
    if np.median(heights) < 0:
        heights = -heights

    cols = np.floor((xs - xs.min()) / cell_size_m).astype(np.int64)
    rows = np.floor((ys - ys.min()) / cell_size_m).astype(np.int64)
    width = int(cols.max()) + 1
    height = int(rows.max()) + 1
    rows = (height - 1) - rows                              # +Y (anchor) points up in the image

    # For each cell keep the tallest point: sort by (cell, height) and take the last per cell.
    flat = rows * width + cols
    order = np.lexsort((heights, flat))                    # primary: cell, secondary: height ascending
    flat_sorted = flat[order]
    is_last_in_cell = np.empty(len(flat_sorted), dtype=bool)
    is_last_in_cell[-1] = True
    is_last_in_cell[:-1] = flat_sorted[1:] != flat_sorted[:-1]
    winners = order[is_last_in_cell]

    win_rows = flat[winners] // width
    win_cols = flat[winners] % width

    blob_map = np.zeros((height, width), dtype=np.uint16)
    height_map = np.zeros((height, width), dtype=np.uint16)
    blob_map[win_rows, win_cols] = (ids[winners] + 1).astype(np.uint16)
    height_map[win_rows, win_cols] = np.clip(
        np.maximum(heights[winners], 0.0) / HEIGHT_UNIT_M, 0, 65535
    ).astype(np.uint16)

    image = np.zeros((height, width, 3), dtype=np.uint16)   # cv2 BGR: [B, G, R]
    image[..., 1] = height_map
    image[..., 2] = blob_map
    cv2.imwrite(out_path, image)

    preview_path = _write_preview(blob_map, height_map, len(clusters), out_path)

    occupied = int((blob_map > 0).sum())
    print(
        f"[topdown] wrote {out_path} ({width}x{height} @ {cell_size_m * 1000:.0f}mm/cell, "
        f"{occupied} blob pixels from {len(clusters)} blobs; R=blob id+1, G=height in 0.1mm)"
    )
    print(f"[topdown] wrote {preview_path} (viewable: color = blob, brightness = height)")
    return out_path
