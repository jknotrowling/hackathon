"""Small viewer for a Unity scene manifest (unity_scene.json).

Renders each placed unit as an oriented box (coloured by shape) at its tabletop
position, and each bulk blob as a grey wireframe box, plus the anchor coordinate
frame. Run it as:

    uv run python -m perception.visualize_scene [captures/unity_scene.json]
"""
import json
import math
import sys

import numpy as np
import open3d as o3d

from perception.arithmetic import UNIT_DIMS_M

SHAPE_COLORS = {
    "pallet": (0.60, 0.40, 0.20),    # wood brown
    "i_beam": (0.55, 0.57, 0.62),    # steel grey
    "brick": (0.72, 0.28, 0.22),     # clay red
}
FALLBACK_COLOR = (0.4, 0.7, 0.4)
BULK_COLOR = (0.5, 0.5, 0.5)
DEFAULT_MANIFEST = "captures/unity_scene.json"


def _unit_box(shape: str, position: list[float], yaw_deg: float) -> o3d.geometry.TriangleMesh:
    """A shaded, coloured box for one placed unit, rotated by yaw and moved to position."""
    width, depth, height = UNIT_DIMS_M.get(shape, (0.03, 0.03, 0.03))
    box = o3d.geometry.TriangleMesh.create_box(width, depth, height)
    box.translate((-width / 2, -depth / 2, -height / 2))     # centre on the origin
    rotation = o3d.geometry.get_rotation_matrix_from_axis_angle([0.0, 0.0, math.radians(yaw_deg)])
    box.rotate(rotation, center=(0.0, 0.0, 0.0))
    box.translate(position)
    box.paint_uniform_color(SHAPE_COLORS.get(shape, FALLBACK_COLOR))
    box.compute_vertex_normals()
    return box


def _bulk_box(position: list[float], extent: list[float]) -> o3d.geometry.AxisAlignedBoundingBox:
    """A grey wireframe box approximating a bulk blob's footprint/size at its centroid."""
    pos = np.asarray(position, dtype=float)
    half = np.asarray(extent, dtype=float) / 2.0
    aabb = o3d.geometry.AxisAlignedBoundingBox(pos - half, pos + half)
    aabb.color = BULK_COLOR
    return aabb


def build_scene_geometries(manifest: dict) -> list:
    """Build the list of Open3D geometries for a loaded manifest (no window opened)."""
    geometries: list = [o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.1)]
    for blob in manifest.get("blobs", []):
        if blob.get("instances"):
            for inst in blob["instances"]:
                geometries.append(_unit_box(inst["shape"], inst["position_xyz"], inst["yaw_deg"]))
        else:
            geometries.append(_bulk_box(blob["position_xyz"], blob["aabb_extent_xyz"]))
    return geometries


def visualize_scene(path: str = DEFAULT_MANIFEST) -> None:
    """Load a Unity scene manifest and render it top-down."""
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)

    geometries = build_scene_geometries(manifest)
    n_units = sum(len(b.get("instances", [])) for b in manifest.get("blobs", []))
    n_bulk = sum(1 for b in manifest.get("blobs", []) if not b.get("instances"))
    print(f"[viz] {path}: {n_units} placed unit(s), {n_bulk} bulk blob(s) -- close the window to exit")

    o3d.visualization.draw_geometries(
        geometries, window_name="Unity scene", width=1100, height=800,
        front=[0.0, 0.0, -1.0], up=[0.0, 1.0, 0.0], zoom=0.7, lookat=[0.0, 0.0, 0.0],
    )


def main() -> None:
    """CLI entry: python -m perception.visualize_scene [manifest.json]."""
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MANIFEST
    visualize_scene(path)


if __name__ == "__main__":
    main()
