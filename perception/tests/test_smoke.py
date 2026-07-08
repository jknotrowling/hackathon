"""Smoke test: modules import, expected callables exist, and the alignment math is correct.
No RealSense hardware required."""
import numpy as np

import perception.alignment
import perception.arithmetic
import perception.capture
import perception.classify_image
import perception.cli
import perception.digital_twin
import perception.export
import perception.export_unity
import perception.project_cluster
import perception.registration
import perception.reporting
import perception.segmentation
import perception.topdown
import perception.viewer


def test_modules_expose_expected_callables() -> None:
    """Every module loads and its public pipeline function is callable."""
    assert callable(perception.capture.capture_rgbd)
    assert callable(perception.capture.capture_frame_corners)
    assert callable(perception.segmentation.preprocess)
    assert callable(perception.segmentation.remove_ground)
    assert callable(perception.segmentation.cluster_heaps)
    assert callable(perception.reporting.print_cluster_report)
    assert callable(perception.viewer.run_viewer)
    assert callable(perception.alignment.deproject_corners)
    assert callable(perception.alignment.umeyama_rigid)
    assert callable(perception.registration.align_and_merge)
    assert callable(perception.registration.global_marker_alignment)
    assert callable(perception.registration.anchor_frame)
    assert callable(perception.export.export_rgbd_frames)
    assert callable(perception.topdown.export_topdown_grid)
    assert callable(perception.arithmetic.estimate_shape_and_count)
    assert callable(perception.arithmetic.count_units)
    assert callable(perception.digital_twin.place_units)
    assert callable(perception.classify_image.classify_crop_multiview)
    assert callable(perception.classify_image.classify_crop)
    assert callable(perception.project_cluster.rank_frames_for_cluster)
    assert callable(perception.project_cluster.pick_best_frame_for_cluster)
    assert callable(perception.export_unity.export_unity_scene)
    assert callable(perception.cli.main)


def test_global_marker_alignment_is_consistent_across_views() -> None:
    """Two views of the same coplanar markers, with corner noise, align to sub-noise consistency."""
    rng = np.random.default_rng(3)
    tag = 0.024
    markers = {
        tid: np.array([[ox, oy, 0], [ox + tag, oy, 0], [ox + tag, oy + tag, 0], [ox, oy + tag, 0]], float)
        for tid, (ox, oy) in enumerate([(-0.1, -0.1), (0.08, -0.1), (-0.1, 0.08), (0.08, 0.08)])
    }
    angle = np.deg2rad(20)
    rot = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    trans = np.array([0.03, 0.01, 0.5])

    view0 = {t: c + rng.normal(0, 0.002, c.shape) for t, c in markers.items()}
    view1 = {t: (c @ rot.T + trans) + rng.normal(0, 0.002, c.shape) for t, c in markers.items()}

    transforms, world = perception.registration.global_marker_alignment([view0, view1])
    assert all(t is not None for t in transforms)
    # every marker corner from both views should agree in the world to within ~the injected noise
    r0 = perception.registration._corner_residual_mm(view0, transforms[0], world)
    r1 = perception.registration._corner_residual_mm(view1, transforms[1], world)
    assert max(r0, r1) < 3.0


def test_umeyama_recovers_a_known_rigid_transform() -> None:
    """Umeyama recovers the exact transform that generated a set of corresponding points."""
    rng = np.random.default_rng(0)
    source = rng.standard_normal((12, 3))
    angle = 0.6
    rotation = np.array([
        [np.cos(angle), -np.sin(angle), 0.0],
        [np.sin(angle), np.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ])
    translation = np.array([0.1, -0.2, 0.3])
    target = source @ rotation.T + translation

    recovered = perception.alignment.umeyama_rigid(source, target)
    mapped = source @ recovered[:3, :3].T + recovered[:3, 3]
    assert np.allclose(mapped, target, atol=1e-9)


def test_crop_below_plane_removes_only_points_under_the_plane() -> None:
    """Points more than the margin under the plane are dropped; on/above-plane points are kept."""
    import open3d as o3d

    centroid = np.array([0.0, 0.0, 0.5])
    normal = np.array([0.0, 0.0, 1.0])          # plane z = 0.5; camera at origin is on the -z (below) side
    camera = np.array([0.0, 0.0, 0.0])
    pts = np.array([
        [0.0, 0.0, 0.40],    # 10cm toward the camera (above) -> keep
        [0.0, 0.0, 0.498],   # 2mm under -> keep (within 5mm)
        [0.0, 0.0, 0.51],    # 10mm under -> drop
    ])
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
    kept = np.asarray(perception.alignment.crop_below_plane(pcd, centroid, normal, camera, 0.005).points)
    assert len(kept) == 2
    assert not np.any(np.isclose(kept[:, 2], 0.51))


def test_snap_to_plane_flattens_a_noisy_marker() -> None:
    """Corners jittered off a plane get projected back so they are coplanar again."""
    flat = np.array([[0.0, 0.0, 1.0], [0.02, 0.0, 1.0], [0.02, 0.02, 1.0], [0.0, 0.02, 1.0]])
    noisy = flat + np.array([[0, 0, 0.003], [0, 0, -0.002], [0, 0, 0.004], [0, 0, -0.001]])
    snapped = perception.alignment.snap_to_plane({7: noisy})[7]
    centroid, normal = perception.alignment.fit_plane(snapped)
    assert np.allclose((snapped - centroid) @ normal, 0.0, atol=1e-9)
