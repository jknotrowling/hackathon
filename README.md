# Stockpile Perception

Captures a scene from an Intel RealSense depth camera and runs the first four
steps of a stockpile perception pipeline (capture, preprocess, ground removal,
heap clustering) with an interactive 3D viewer.

## Construction Site Monitoring UI

A web platform for visualizing construction sites, drone surveys, stockpiles, and ROIs lives in [`UI/`](UI/README.md).

## Quickstart

### Windows PowerShell

```powershell
cd perception
uv sync
uv run stockpile --ply PATH_TO_A_PLY
```

### macOS / Linux

```bash
cd perception
uv sync
uv run stockpile --ply PATH_TO_A_PLY
```

## Smoke test

```bash
uv run python -c "import open3d, pyrealsense2, numpy; print('ok')"
```
