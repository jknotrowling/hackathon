"""AprilTag marker detection.

This module only *finds* markers and returns their image corners. Turning those
corners into 3D and aligning frames lives in perception.alignment /
perception.registration -- alignment is done directly from measured depth, not
from monocular pose estimation.
"""
import cv2
import numpy as np

TAG_SIZE_M = 0.03                                  # default tag marker edge length, 24 mm
DICT = cv2.aruco.DICT_APRILTAG_25h9                 # marker family used on the base plate
MIN_MARKER_PERIMETER_RATE = 0.01                    # default 0.03 misses small tags seen from further back
ADAPTIVE_THRESH_WIN_SIZE_MAX = 53                   # default 23 struggles with uneven lighting


def _build_detector() -> cv2.aruco.ArucoDetector:
    """Detector tuned for small markers seen under uneven lighting."""
    dictionary = cv2.aruco.getPredefinedDictionary(DICT)
    parameters = cv2.aruco.DetectorParameters()
    parameters.minMarkerPerimeterRate = MIN_MARKER_PERIMETER_RATE
    parameters.adaptiveThreshWinSizeMax = ADAPTIVE_THRESH_WIN_SIZE_MAX
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(dictionary, parameters)


def detect_tags(color_bgr: np.ndarray) -> dict[int, np.ndarray]:
    """Detect markers in a BGR image; return {tag_id: (4,2) image corners (TL,TR,BR,BL)}."""
    detections, _num_rejected = detect_tags_debug(color_bgr)
    return detections


def detect_tags_debug(color_bgr: np.ndarray) -> tuple[dict[int, np.ndarray], int]:
    """Like detect_tags, but also returns how many candidate quads were found yet failed id
    decoding -- a non-zero count here (vs. 0 candidates at all) points at a dictionary/family
    mismatch or blur, rather than a lighting/printing/quiet-zone problem."""
    corners, ids, rejected = _build_detector().detectMarkers(color_bgr)
    if ids is None:
        detections: dict[int, np.ndarray] = {}
    else:
        detections = {int(tag_id): corners[i].reshape(4, 2).astype(np.float64) for i, tag_id in enumerate(np.ravel(ids))}
    num_rejected = 0 if rejected is None else len(rejected)
    return detections, num_rejected
