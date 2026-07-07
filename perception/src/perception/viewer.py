"""Interactive Open3D viewer for stepping through pipeline stages."""
import open3d as o3d

COORD_FRAME_SIZE = 0.1       # 10 cm reference axes


def run_viewer(
    raw: o3d.geometry.PointCloud,
    preprocessed: o3d.geometry.PointCloud,
    ground: o3d.geometry.PointCloud,
    above: o3d.geometry.PointCloud,
    clusters_agg: o3d.geometry.PointCloud,
) -> None:
    """Interactive viewer; keys 1-4 switch between pipeline stages."""
    stages = {"1": [raw], "2": [preprocessed], "3": [ground, above], "4": [clusters_agg]}
    names = {"1": "Raw capture", "2": "Preprocessed", "3": "Ground + above-ground", "4": "Clustered heaps"}
    coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=COORD_FRAME_SIZE)
    state = {"stage": "1", "vis": None}

    def build_window(stage: str, cam_params=None) -> o3d.visualization.VisualizerWithKeyCallback:
        vis = o3d.visualization.VisualizerWithKeyCallback()
        vis.create_window(window_name=f"Stockpile Pipeline - Stage {stage}: {names[stage]}", width=1280, height=800)
        for geom in stages[stage]:
            vis.add_geometry(geom)
        vis.add_geometry(coord_frame)
        if cam_params is not None:
            vis.get_view_control().convert_from_pinhole_camera_parameters(cam_params)
        for key in "1234":
            vis.register_key_callback(ord(key), make_switch(key))
        return vis

    def make_switch(stage: str):
        def _switch(vis):
            if stage == state["stage"]:
                return False
            cam_params = vis.get_view_control().convert_to_pinhole_camera_parameters()
            vis.destroy_window()
            state["stage"] = stage
            state["vis"] = build_window(stage, cam_params)
            return False
        return _switch

    state["vis"] = build_window(state["stage"])
    while state["vis"].poll_events():
        state["vis"].update_renderer()
    state["vis"].destroy_window()
