"""Test scene-geometry building from a manifest (no window opened)."""
from perception.visualize_scene import build_scene_geometries


def test_build_scene_geometries_counts_units_and_bulk() -> None:
    """One geometry per placed unit + one per bulk blob, plus the coordinate frame."""
    manifest = {
        "blobs": [
            {"position_xyz": [0.1, 0.0, -0.02], "aabb_extent_xyz": [0.1, 0.1, 0.05], "instances": []},
            {"position_xyz": [0.0, 0.0, 0.0], "aabb_extent_xyz": [0, 0, 0], "instances": [
                {"shape": "brick", "position_xyz": [0.02, 0.0, 0.01], "yaw_deg": 0.0},
                {"shape": "i_beam", "position_xyz": [0.10, 0.0, 0.01], "yaw_deg": 90.0},
            ]},
        ]
    }
    geometries = build_scene_geometries(manifest)
    # 1 coordinate frame + 1 tabletop slab + 1 bulk box + 2 unit boxes
    assert len(geometries) == 5


def test_build_scene_geometries_handles_empty_manifest() -> None:
    """An empty manifest still yields just the coordinate frame, no crash."""
    assert len(build_scene_geometries({})) == 1
