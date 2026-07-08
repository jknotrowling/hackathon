"""Export the analysed blobs as a Unity-consumable scene manifest (JSON).

Each blob entry carries its tabletop-anchored position and size, its measured volume,
and the results of the CLIP material / unit-type classification and (for discrete-unit
blobs) the arithmetic shape/count estimate.
"""
import json
import os
from dataclasses import dataclass, field

import numpy as np
import open3d as o3d

from perception.digital_twin import UnitInstance


@dataclass
class BlobAnalysis:
    """Per-blob classification/volume results the manifest records alongside geometry."""
    volume_m3: float
    material: str
    material_confidence: float
    unit_type: str                      # "discrete" | "bulk" | "unknown"
    shape: str | None
    estimated_count: int | None
    shape_fit_error: float | None
    num_views_used: int
    instances: list[UnitInstance] = field(default_factory=list)   # placed virtual units (digital twin)


def export_unity_scene(
    clusters: list[o3d.geometry.PointCloud],
    analyses: list[BlobAnalysis],
    world_from_anchor: np.ndarray,
    out_path: str = "captures/unity_scene.json",
) -> str:
    """Write a JSON scene manifest of the blobs in tabletop (anchor-marker) coordinates."""
    anchor_from_world = np.linalg.inv(world_from_anchor)
    rotation = anchor_from_world[:3, :3]
    translation = anchor_from_world[:3, 3]

    entries = []
    for i, (cluster, analysis) in enumerate(zip(clusters, analyses)):
        center_world = np.asarray(cluster.get_center())
        center_anchor = rotation @ center_world + translation
        extent = cluster.get_axis_aligned_bounding_box().get_extent()
        entries.append({
            "id": i,
            "position_xyz": [float(v) for v in center_anchor],
            "aabb_extent_xyz": [float(v) for v in extent],
            "volume_m3": float(analysis.volume_m3),
            "material": analysis.material,
            "material_confidence": float(analysis.material_confidence),
            "unit_type": analysis.unit_type,
            "shape": analysis.shape,
            "estimated_count": analysis.estimated_count,
            "shape_fit_error": analysis.shape_fit_error,
            "num_views_used": int(analysis.num_views_used),
            "instances": [
                {"shape": inst.shape, "position_xyz": inst.position_xyz, "yaw_deg": inst.yaw_deg}
                for inst in analysis.instances
            ],
        })

    total_instances = sum(len(a.instances) for a in analyses)
    manifest = {
        "frame_of_reference": "anchor marker (tabletop); positions map world -> anchor",
        "units": "meters",
        "instance_count": total_instances,
        "blobs": entries,
    }

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[unity] wrote scene manifest with {len(entries)} blob(s), {total_instances} placed unit(s) to {out_path}")
    return out_path
