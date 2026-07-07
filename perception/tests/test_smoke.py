"""Smoke test: modules import and expected callables exist. No RealSense hardware required."""
import perception.capture
import perception.cli
import perception.reporting
import perception.segmentation
import perception.viewer


def test_modules_expose_expected_callables() -> None:
    """Every module loads and its public pipeline function is callable."""
    assert callable(perception.capture.capture_rgbd)
    assert callable(perception.segmentation.preprocess)
    assert callable(perception.segmentation.remove_ground)
    assert callable(perception.segmentation.cluster_heaps)
    assert callable(perception.reporting.print_cluster_report)
    assert callable(perception.viewer.run_viewer)
    assert callable(perception.cli.main)
