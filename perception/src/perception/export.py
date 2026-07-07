"""Export helpers for captured data."""
import json
import os

import cv2
import numpy as np

DEPTH_PNG_SCALE = 1000.0     # store depth as 16-bit PNG in millimeters (meters * 1000), the RealSense/Open3D convention
DEPTH_PREVIEW_MAX_M = 2.0    # depth mapped to 0..255 over 0..this range for the human-viewable preview PNG


def _rotation_to_quaternion(rotation: np.ndarray) -> list[float]:
    """Convert a 3x3 rotation matrix to a quaternion [x, y, z, w] (numerically stable)."""
    trace = np.trace(rotation)
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (rotation[2, 1] - rotation[1, 2]) / s
        y = (rotation[0, 2] - rotation[2, 0]) / s
        z = (rotation[1, 0] - rotation[0, 1]) / s
    else:
        i = int(np.argmax([rotation[0, 0], rotation[1, 1], rotation[2, 2]]))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = np.sqrt(1.0 + rotation[i, i] - rotation[j, j] - rotation[k, k]) * 2.0
        q = [0.0, 0.0, 0.0]
        q[i] = 0.25 * s
        q[j] = (rotation[j, i] + rotation[i, j]) / s
        q[k] = (rotation[k, i] + rotation[i, k]) / s
        w = (rotation[k, j] - rotation[j, k]) / s
        x, y, z = q
    return [float(x), float(y), float(z), float(w)]


def export_rgbd_frames(
    frames: list[tuple[np.ndarray, np.ndarray]],
    camera_poses: list[np.ndarray | None] | None = None,
    out_dir: str = "captures",
) -> str:
    """Write each captured (color_bgr, depth_m) frame as a color+depth PNG pair, plus poses.

    color_XXXX.png is the 8-bit BGR image; depth_XXXX.png is a 16-bit single-channel
    depth map in millimeters (reload with cv2.imread(path, cv2.IMREAD_UNCHANGED)).

    If camera_poses is given, camera_poses.json records, per frame, the camera's
    orientation and position relative to the anchor marker: position_xyz (meters),
    orientation as a quaternion_xyzw and a rotation_matrix, and the full transform_4x4.

    Returns the output directory.
    """
    os.makedirs(out_dir, exist_ok=True)
    for i, (color_bgr, depth_m) in enumerate(frames):
        cv2.imwrite(os.path.join(out_dir, f"color_{i:04d}.png"), color_bgr)
        # Lossless 16-bit depth in millimeters (the reload-friendly source of truth)...
        depth_mm = np.clip(depth_m * DEPTH_PNG_SCALE, 0, 65535).astype(np.uint16)
        cv2.imwrite(os.path.join(out_dir, f"depth_{i:04d}.png"), depth_mm)
        # ...plus an 8-bit normalized preview, since 16-bit mm depth looks nearly black in viewers.
        preview = np.clip(depth_m / DEPTH_PREVIEW_MAX_M, 0.0, 1.0) * 255.0
        cv2.imwrite(os.path.join(out_dir, f"depth_{i:04d}_preview.png"), preview.astype(np.uint8))
    print(f"[export] wrote {len(frames)} RGBD frame(s) to {out_dir}/ (color_*.png + depth_*.png [16-bit mm] + depth_*_preview.png)")

    if camera_poses is not None:
        entries = []
        for i, pose in enumerate(camera_poses):
            if pose is None:
                entries.append({"frame": i, "color": f"color_{i:04d}.png", "pose": None})
                continue
            rotation = pose[:3, :3]
            entries.append({
                "frame": i,
                "color": f"color_{i:04d}.png",
                "depth": f"depth_{i:04d}.png",
                "position_xyz": [float(v) for v in pose[:3, 3]],
                "orientation_quaternion_xyzw": _rotation_to_quaternion(rotation),
                "rotation_matrix": [[float(v) for v in row] for row in rotation],
                "transform_4x4": [[float(v) for v in row] for row in pose],
            })
        manifest = {
            "frame_of_reference": "anchor marker (smallest tag id); pose maps camera -> anchor",
            "units": "meters",
            "frames": entries,
        }
        poses_path = os.path.join(out_dir, "camera_poses.json")
        with open(poses_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"[export] wrote camera poses (relative to anchor marker) to {poses_path}")

    return out_dir
