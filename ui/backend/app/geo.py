import json
from typing import Any

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry


def geojson_to_wkt(geojson: dict[str, Any]) -> WKTElement:
    geom = shape(geojson)
    return WKTElement(geom.wkt, srid=4326)


def wkt_to_geojson(geometry: Any) -> dict[str, Any] | None:
    if geometry is None:
        return None
    shapely_geom: BaseGeometry = to_shape(geometry)
    return mapping(shapely_geom)


def geojson_dumps(geojson: dict[str, Any]) -> str:
    return json.dumps(geojson)
