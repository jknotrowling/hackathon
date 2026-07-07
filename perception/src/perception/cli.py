"""Command-line entry point for the stockpile perception pipeline."""
import argparse
import os
import sys

import numpy as np
import open3d as o3d

from perception.capture import WARMUP_FRAMES, capture_frame_corners, capture_rgbd, grab_frame, open_pipeline
from perception.export import export_rgbd_frames
from perception.markers import TAG_SIZE_M, detect_tags_debug
from perception.reporting import print_cluster_report
from perception.registration import align_and_merge
from perception.segmentation import ABOVE_COLOR, cluster_heaps, preprocess, remove_ground
from perception.viewer import run_viewer

# TODO(export): when export.py grows a cluster manifest, populate each blob's entry
# with volume_m3 / volume_convex_hull_m3, reusing the volume list returned by
# print_cluster_report below rather than recomputing.


def parse_args() -> argparse.Namespace:
    """Parse the mutually exclusive --live / --bag / --ply / --multi-live input mode flags."""
    parser = argparse.ArgumentParser(description="Stockpile perception pipeline (steps 1-4)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="stream from a connected RealSense camera")
    group.add_argument("--bag", type=str, help="path to a recorded .bag file")
    group.add_argument("--ply", type=str, help="path to an existing point cloud (skip capture)")
    group.add_argument(
        "--multi-live", type=int, metavar="N",
        help="capture N live frames using auto-bootstrapped AprilTag markers",
    )
    parser.add_argument(
        "--tag-size", type=float, default=TAG_SIZE_M,
        help=f"AprilTag marker size in meters (default: {TAG_SIZE_M})",
    )
    return parser.parse_args()


def _preview_overlay(
    color_bgr: np.ndarray, detections: dict[int, np.ndarray], num_rejected: int,
    known_ids: set[int], k: int, num_frames: int,
) -> np.ndarray:
    """Draw detected tag outlines/ids and a status line (incl. detector diagnostics) on a copy of the frame."""
    import cv2

    preview = color_bgr.copy()
    if detections:
        corners = [d.reshape(1, 4, 2).astype(np.float32) for d in detections.values()]
        ids = np.array(list(detections.keys()), dtype=np.int32).reshape(-1, 1)
        cv2.aruco.drawDetectedMarkers(preview, corners, ids)

    overlap = len(set(detections) & known_ids) if known_ids else len(detections)
    status = f"captured {k}/{num_frames} | markers seen: {len(detections)} | overlap w/ prior: {overlap}"
    diag = f"known markers: {len(known_ids)} | rejected candidates: {num_rejected}"
    cv2.putText(preview, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(preview, diag, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    return preview


def _run_multi_live(num_frames: int, tag_size_m: float) -> None:
    """Capture num_frames live frames, align them via shared marker corners, then run the pipeline."""
    import cv2

    window_name = "Multi-view capture"
    pipeline, align = open_pipeline("live")
    captured: list[tuple[o3d.geometry.PointCloud, dict[int, np.ndarray]]] = []
    rgbd_frames: list[tuple[np.ndarray, np.ndarray]] = []
    known_ids: set[int] = set()

    try:
        for _ in range(WARMUP_FRAMES):
            pipeline.wait_for_frames()

        # HighGUI windows (unlike Open3D's GLFW window) don't grab OS keyboard
        # focus on their own, so cv2.waitKey silently sees nothing until the
        # user clicks the window; keep it on top to make that obvious.
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        print(f"[capture] click the '{window_name}' window to focus it, then use SPACE/ESC")

        k = 0
        while k < num_frames:
            print(
                f"[capture] frame {k + 1}/{num_frames}: press SPACE (need >=1 marker with depth; "
                "after frame 1, at least 1 must overlap a previously seen marker), ESC to abort"
            )
            while True:
                _preview_pcd, color_bgr, _intrinsics_matrix, _depth_m = grab_frame(pipeline, align)
                detections, num_rejected = detect_tags_debug(color_bgr)
                preview = _preview_overlay(color_bgr, detections, num_rejected, known_ids, k, num_frames)
                cv2.imshow(window_name, preview)
                cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
                key = cv2.waitKey(1) & 0xFF

                if key == 115:  # 's'
                    cv2.imwrite("debug_raw.png", color_bgr)
                    print("saved debug_raw.png")
                if key == 27:  # ESC
                    print("[capture] aborted")
                    return
                if key != 32:  # not SPACE
                    continue

                pcd, cam_corners, committed_color, committed_depth, _det = capture_frame_corners(pipeline, align)
                if not cam_corners:
                    print("[capture] no markers with valid depth, retry")
                    continue
                if known_ids and not (set(cam_corners) & known_ids):
                    print("[capture] none of these markers were seen before (can't align), retry")
                    continue

                captured.append((pcd, cam_corners))
                rgbd_frames.append((committed_color, committed_depth))
                known_ids |= set(cam_corners)
                print(f"[capture] frame {k + 1}: {len(cam_corners)} markers with depth | {len(known_ids)} known total")
                k += 1
                break
    finally:
        cv2.destroyAllWindows()
        pipeline.stop()

    if len(captured) < num_frames:
        return

    total_points_before = sum(len(pcd.points) for pcd, _ in captured)
    merged, camera_poses = align_and_merge(captured)
    print(f"[merge] combined {num_frames} clouds, {total_points_before} -> {len(merged.points)} points after downsample")

    preprocessed = preprocess(merged)
    ground, above, plane_model = remove_ground(preprocessed)
    above.paint_uniform_color(ABOVE_COLOR)
    print(f"Ground plane (a, b, c, d): {tuple(round(v, 4) for v in plane_model)}")

    clusters_agg, clusters = cluster_heaps(above)
    print_cluster_report(clusters, plane_model)

    # Save the captured pictures + each camera's pose relative to the anchor marker,
    # after the scene reconstruction has produced those poses.
    export_rgbd_frames(rgbd_frames, camera_poses)

    run_viewer(merged, preprocessed, ground, above, clusters_agg)


def _run(args: argparse.Namespace) -> None:
    """Execute capture (or load), preprocess, ground removal, clustering, and the viewer."""
    if args.multi_live is not None:
        _run_multi_live(args.multi_live, args.tag_size)
        return

    if args.ply:
        if not os.path.isfile(args.ply):
            raise FileNotFoundError(f"Point cloud file not found: {args.ply}")
        raw = o3d.io.read_point_cloud(args.ply)
        if raw.is_empty():
            raise RuntimeError(f"Loaded point cloud is empty: {args.ply}")
    else:
        if args.bag:
            if not os.path.isfile(args.bag):
                raise FileNotFoundError(f"Bag file not found: {args.bag}")
            raw = capture_rgbd("bag", args.bag)
        else:
            raw = capture_rgbd("live")

    preprocessed = preprocess(raw)
    ground, above, plane_model = remove_ground(preprocessed)
    above.paint_uniform_color(ABOVE_COLOR)
    print(f"Ground plane (a, b, c, d): {tuple(round(v, 4) for v in plane_model)}")

    clusters_agg, clusters = cluster_heaps(above)
    print_cluster_report(clusters, plane_model)

    run_viewer(raw, preprocessed, ground, above, clusters_agg)


def main() -> None:
    """Entry point: parse args, run the pipeline, and report errors cleanly."""
    try:
        _run(parse_args())
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()