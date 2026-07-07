"""Command-line entry point for the stockpile perception pipeline."""
import argparse
import os
import sys

import open3d as o3d

from perception.capture import capture_rgbd
from perception.reporting import print_cluster_report
from perception.segmentation import ABOVE_COLOR, cluster_heaps, preprocess, remove_ground
from perception.viewer import run_viewer


def parse_args() -> argparse.Namespace:
    """Parse the mutually exclusive --live / --bag / --ply input mode flags."""
    parser = argparse.ArgumentParser(description="Stockpile perception pipeline (steps 1-4)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="stream from a connected RealSense camera")
    group.add_argument("--bag", type=str, help="path to a recorded .bag file")
    group.add_argument("--ply", type=str, help="path to an existing point cloud (skip capture)")
    return parser.parse_args()


def _run(args: argparse.Namespace) -> None:
    """Execute capture (or load), preprocess, ground removal, clustering, and the viewer."""
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
    print_cluster_report(clusters)

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
