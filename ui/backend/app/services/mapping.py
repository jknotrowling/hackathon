import math
from typing import Any

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, Polygon

METERS_PER_DEGREE_LAT = 111_320.0
GRID_SPACING_M = 10.0


def _meters_per_degree_lon(latitude: float) -> float:
    return METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude))


def _to_local_meters(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    x = (lon - origin_lon) * _meters_per_degree_lon(origin_lat)
    y = (lat - origin_lat) * METERS_PER_DEGREE_LAT
    return x, y


def _from_local_meters(x: float, y: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
    lat = origin_lat + y / METERS_PER_DEGREE_LAT
    lon = origin_lon + x / _meters_per_degree_lon(origin_lat)
    return lon, lat


def _frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    current = start
    while current <= stop + step / 2:
        values.append(current)
        current += step
    return values


def _local_bounding_box(polygon: Polygon) -> tuple[float, float, float, float, float, float]:
    """Return origin lon/lat and axis-aligned bounds in local meters."""
    coords = list(polygon.exterior.coords)
    origin_lon = sum(coord[0] for coord in coords) / len(coords)
    origin_lat = sum(coord[1] for coord in coords) / len(coords)

    local_points = [_to_local_meters(lon, lat, origin_lon, origin_lat) for lon, lat in coords]
    xs = [point[0] for point in local_points]
    ys = [point[1] for point in local_points]
    return origin_lon, origin_lat, min(xs), min(ys), max(xs), max(ys)


def _build_serpentine_grid_path(
    origin_lon: float,
    origin_lat: float,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    spacing_m: float,
) -> list[tuple[float, float]]:
    x_values = _frange(min_x, max_x, spacing_m)
    y_values = _frange(min_y, max_y, spacing_m)

    if not x_values or not y_values:
        center = _from_local_meters((min_x + max_x) / 2, (min_y + max_y) / 2, origin_lon, origin_lat)
        return [center, center]

    path: list[tuple[float, float]] = []
    for row_index, y in enumerate(y_values):
        row_x_values = x_values if row_index % 2 == 0 else list(reversed(x_values))
        for x in row_x_values:
            path.append(_from_local_meters(x, y, origin_lon, origin_lat))

    return path


def compute_mapping_flight_paths(
    region_geometry: Any,
    spacing_m: float = GRID_SPACING_M,
) -> list[WKTElement | None]:
    """Compute flight paths that cover a region for photogrammetry mapping.

    Builds an axis-aligned bounding box around the ROI and plans a serpentine
    path through a grid of points spaced at ``spacing_m`` meters inside the box.
    Returns one WKTElement per planned pass.
    """
    polygon = to_shape(region_geometry)
    if polygon.is_empty or not isinstance(polygon, Polygon):
        return []

    origin_lon, origin_lat, min_x, min_y, max_x, max_y = _local_bounding_box(polygon)
    path_coords = _build_serpentine_grid_path(
        origin_lon,
        origin_lat,
        min_x,
        min_y,
        max_x,
        max_y,
        spacing_m,
    )

    if len(path_coords) < 2:
        return []

    line = LineString(path_coords)
    return [WKTElement(line.wkt, srid=4326)]
