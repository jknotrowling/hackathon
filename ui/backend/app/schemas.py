from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None = None


class ProjectDetail(ProjectSummary):
    description: str | None = None
    created_at: datetime


class GeoJSONPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: list[list[list[float]]]


class GeoJSONLineString(BaseModel):
    type: str = "LineString"
    coordinates: list[list[float]]


class RegionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geometry: GeoJSONPolygon


class RegionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    geometry: GeoJSONPolygon | None = None


class RegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    geometry: dict[str, Any]


class StockpileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    material: str
    volume: float
    last_scan: str | None = None
    geometry: dict[str, Any] | None = None


class SurveyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    data_reference: str | None = None
    orthophoto_url: str | None = None
    flight_path: dict[str, Any] | None = None
    stockpile_volumes: list[dict[str, Any]] = []
