from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo import geojson_to_wkt, wkt_to_geojson
from app.models import Project, Region
from app.routers.flights import _flight_response
from app.schemas import FlightResponse, RegionCreate, RegionResponse, RegionUpdate
from app.services.flight_planner import RegionNotFoundError, plan_mapping_flights

router = APIRouter(tags=["regions"])


def _region_response(region: Region) -> RegionResponse:
    geometry = wkt_to_geojson(region.geometry)
    return RegionResponse(
        id=region.id,
        project_id=region.project_id,
        name=region.name,
        geometry=geometry or {"type": "Polygon", "coordinates": []},
    )


@router.get("/api/projects/{project_id}/rois", response_model=list[RegionResponse])
def list_rois(project_id: int, db: Session = Depends(get_db)) -> list[RegionResponse]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    regions = db.query(Region).filter(Region.project_id == project_id).order_by(Region.name).all()
    return [_region_response(region) for region in regions]


@router.post("/api/projects/{project_id}/rois", response_model=RegionResponse, status_code=201)
def create_roi(project_id: int, payload: RegionCreate, db: Session = Depends(get_db)) -> RegionResponse:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    region = Region(
        project_id=project_id,
        name=payload.name,
        geometry=geojson_to_wkt(payload.geometry.model_dump()),
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return _region_response(region)


@router.put("/api/rois/{region_id}", response_model=RegionResponse)
def update_roi(region_id: int, payload: RegionUpdate, db: Session = Depends(get_db)) -> RegionResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    if payload.name is not None:
        region.name = payload.name
    if payload.geometry is not None:
        region.geometry = geojson_to_wkt(payload.geometry.model_dump())
    db.commit()
    db.refresh(region)
    return _region_response(region)


@router.delete("/api/rois/{region_id}", status_code=204)
def delete_roi(region_id: int, db: Session = Depends(get_db)) -> None:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    db.delete(region)
    db.commit()


@router.post("/api/rois/{region_id}/plan-flights", response_model=list[FlightResponse], status_code=201)
def plan_region_mapping_flights(region_id: int, db: Session = Depends(get_db)) -> list[FlightResponse]:
    try:
        flights = plan_mapping_flights(db, region_id)
    except RegionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return [_flight_response(flight) for flight in flights]
