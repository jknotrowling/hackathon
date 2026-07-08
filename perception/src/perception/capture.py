"""RealSense capture: stream/playback aligned RGBD frames and convert them to point clouds."""
import numpy as np
import open3d as o3d

from perception.alignment import deproject_corners
from perception.markers import detect_tags

FRAME_WIDTH = 1280           # D435/D455 native resolution that keeps FPS steady
FRAME_HEIGHT = 720           # matches FRAME_WIDTH above
FRAME_FPS = 30               # standard streaming rate for both depth and color
WARMUP_FRAMES = 15           # discard ~1s @30fps so auto-exposure/white-balance settle
DEPTH_SCALE = 1000.0         # RealSense depth units are millimeters -> meters
DEPTH_TRUNC = 3.0            # ignore depth beyond 3 m, outside the stockpile working volume
FLIP_TRANSFORM = np.array([
    [1, 0, 0, 0],
    [0, -1, 0, 0],
    [0, 0, -1, 0],
    [0, 0, 0, 1],
], dtype=float)


def open_pipeline(source: str, bag_path: str | None = None):
    """Configure and start a RealSense pipeline (live device or .bag playback), aligned to color."""
    import pyrealsense2 as rs

    pipeline = rs.pipeline()
    config = rs.config()
    if source == "bag":
        config.enable_device_from_file(bag_path, repeat_playback=False)
    else:
        config.enable_stream(rs.stream.depth, FRAME_WIDTH, FRAME_HEIGHT, rs.format.z16, FRAME_FPS)
        config.enable_stream(rs.stream.color, FRAME_WIDTH, FRAME_HEIGHT, rs.format.bgr8, FRAME_FPS)

    try:
        pipeline.start(config)
    except RuntimeError as exc:
        raise RuntimeError(
            "Could not start the RealSense pipeline. Check that a D4xx-class "
            "device is connected (for --live) or that the .bag file is valid. "
            f"Underlying error: {exc}"
        ) from exc

    align = rs.align(rs.stream.color)
    return pipeline, align


def grab_frame(pipeline, align):
    """Grab one aligned RGBD frame.

    Returns (point cloud in raw camera frame, BGR image, 3x3 intrinsics,
    depth map in meters as a HxW float array with 0 = no reading). The depth map
    is what lets marker corners be back-projected to real 3D points for alignment.
    """
    frames = align.process(pipeline.wait_for_frames())
    depth_frame = frames.get_depth_frame()
    color_frame = frames.get_color_frame()
    if not depth_frame or not color_frame:
        raise RuntimeError("Received an empty depth or color frame from the camera/bag.")

    color_profile = color_frame.get_profile().as_video_stream_profile()
    intr = color_profile.get_intrinsics()
    o3d_intrinsic = o3d.camera.PinholeCameraIntrinsic(
        intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy
    )
    intrinsics_matrix = np.array([
        [intr.fx, 0.0, intr.ppx],
        [0.0, intr.fy, intr.ppy],
        [0.0, 0.0, 1.0],
    ])

    depth_image = np.asanyarray(depth_frame.get_data())
    depth_m = depth_image.astype(np.float32) / DEPTH_SCALE
    color_bgr = np.asanyarray(color_frame.get_data())
    color_rgb = np.ascontiguousarray(color_bgr[:, :, ::-1])

    o3d_color = o3d.geometry.Image(color_rgb)
    o3d_depth = o3d.geometry.Image(depth_image)
    rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
        o3d_color, o3d_depth,
        depth_scale=DEPTH_SCALE, depth_trunc=DEPTH_TRUNC,
        convert_rgb_to_intensity=False,
    )
    pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, o3d_intrinsic)
    # .copy() is REQUIRED: np.asanyarray gives a view into the RealSense frame's
    # internal buffer, which the SDK recycles on later grabs. Callers that keep the
    # image around (e.g. to export after capture) would otherwise see it go black.
    return pcd, color_bgr.copy(), intrinsics_matrix, depth_m


def capture_rgbd(source: str, bag_path: str | None = None) -> o3d.geometry.PointCloud:
    """Stream one aligned RGBD frame from a live RealSense device or a .bag file
    and convert it to a point cloud in the flipped (right-side-up) frame."""
    pipeline, align = open_pipeline(source, bag_path)
    try:
        for _ in range(WARMUP_FRAMES):
            pipeline.wait_for_frames()
        pcd, _color_bgr, _intrinsics_matrix, _depth_m = grab_frame(pipeline, align)
    finally:
        pipeline.stop()

    pcd.transform(FLIP_TRANSFORM)
    return pcd


def capture_frame_corners(
    pipeline, align,
) -> tuple[o3d.geometry.PointCloud, dict[int, np.ndarray], np.ndarray, np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    """Grab one frame, detect markers, and back-project their corners to 3D camera points.

    Returns (point cloud in camera frame, {tag_id: (4,3) camera-frame corners with valid
    depth}, BGR image, depth map in meters, 3x3 intrinsics, {tag_id: (4,2) image corners}).
    The 3D corners are what the aligner matches across frames; color+depth are exported per
    frame; the intrinsics let clusters be re-projected into these frames for classification.
    """
    pcd, color_bgr, intrinsics_matrix, depth_m = grab_frame(pipeline, align)
    detections = detect_tags(color_bgr)
    cam_corners = deproject_corners(detections, depth_m, intrinsics_matrix)
    return pcd, cam_corners, color_bgr, depth_m, intrinsics_matrix, detections