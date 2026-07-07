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
    """Interactive viewer; keys 1-4 swap geometry between pipeline stages in place."""
    stages = {"1": [raw], "2": [preprocessed], "3": [ground, above], "4": [clusters_agg]}
    names = {"1": "raw", "2": "preprocessed", "3": "ground+above", "4": "clusters"}
    coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=COORD_FRAME_SIZE)
    state = {"stage": "1"}

    def show_stage(vis: o3d.visualization.VisualizerWithKeyCallback, stage: str) -> None:
        state["stage"] = stage
        vis.clear_geometries()
        for geom in stages[stage]:
            vis.add_geometry(geom, reset_bounding_box=False)
        vis.add_geometry(coord_frame, reset_bounding_box=False)
        vis.update_renderer()
        print(f"[viewer] stage: {names[stage]}")

    def make_switch(stage: str):
        def _switch(vis):
            if stage != state["stage"]:
                show_stage(vis, stage)
            return False
        return _switch

    vis = o3d.visualization.VisualizerWithKeyCallback()
    vis.create_window(window_name="Stockpile Pipeline", width=1280, height=800)
    for key in "1234":
        vis.register_key_callback(ord(key), make_switch(key))

    print("Keys: 1=raw  2=preprocessed  3=ground+above  4=clusters  Q=quit")
    for geom in stages[state["stage"]]:
        vis.add_geometry(geom, reset_bounding_box=True)
    vis.add_geometry(coord_frame, reset_bounding_box=False)
    print(f"[viewer] stage: {names[state['stage']]}")

    while vis.poll_events():
        vis.update_renderer()
    vis.destroy_window()
