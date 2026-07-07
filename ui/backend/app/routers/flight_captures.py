from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo import geojson_to_wkt, wkt_to_geojson
from app.models import Flight, FlightCapture, Project
from app.schemas import FlightCaptureCreate, FlightCaptureResponse, FlightCaptureUpdate

router = APIRouter(tags=["flight-captures"])


def _capture_response(capture: FlightCapture) -> FlightCaptureResponse:
    location = wkt_to_geojson(capture.location)
    return FlightCaptureResponse(
        id=capture.id,
        flight_id=capture.flight_id,
        waypoint_index=capture.waypoint_index,
        location=location or {"type": "Point", "coordinates": [0, 0]},
        image_url=capture.image_url,
    )


@router.get("/api/projects/{project_id}/flight-captures", response_model=list[FlightCaptureResponse])
def list_project_flight_captures(project_id: int, db: Session = Depends(get_db)) -> list[FlightCaptureResponse]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    captures = (
        db.query(FlightCapture)
        .join(Flight)
        .filter(Flight.project_id == project_id)
        .order_by(FlightCapture.flight_id, FlightCapture.waypoint_index)
        .all()
    )
    return [_capture_response(capture) for capture in captures]


@router.get("/api/flights/{flight_id}/captures", response_model=list[FlightCaptureResponse])
def list_flight_captures(flight_id: int, db: Session = Depends(get_db)) -> list[FlightCaptureResponse]:
    flight = db.get(Flight, flight_id)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")

    captures = (
        db.query(FlightCapture)
        .filter(FlightCapture.flight_id == flight_id)
        .order_by(FlightCapture.waypoint_index)
        .all()
    )
    return [_capture_response(capture) for capture in captures]


@router.post("/api/flights/{flight_id}/captures", response_model=FlightCaptureResponse, status_code=201)
def create_flight_capture(
    flight_id: int,
    payload: FlightCaptureCreate,
    db: Session = Depends(get_db),
) -> FlightCaptureResponse:
    flight = db.get(Flight, flight_id)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")

    capture = FlightCapture(
        flight_id=flight_id,
        waypoint_index=payload.waypoint_index,
        location=geojson_to_wkt(payload.location.model_dump()),
        image_url=payload.image_url,
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)
    return _capture_response(capture)


@router.put("/api/flight-captures/{capture_id}", response_model=FlightCaptureResponse)
def update_flight_capture(
    capture_id: int,
    payload: FlightCaptureUpdate,
    db: Session = Depends(get_db),
) -> FlightCaptureResponse:
    capture = db.get(FlightCapture, capture_id)
    if capture is None:
        raise HTTPException(status_code=404, detail="Flight capture not found")

    if payload.waypoint_index is not None:
        capture.waypoint_index = payload.waypoint_index
    if payload.location is not None:
        capture.location = geojson_to_wkt(payload.location.model_dump())
    if payload.image_url is not None:
        capture.image_url = payload.image_url

    db.commit()
    db.refresh(capture)
    return _capture_response(capture)


@router.delete("/api/flight-captures/{capture_id}", status_code=204)
def delete_flight_capture(capture_id: int, db: Session = Depends(get_db)) -> None:
    capture = db.get(FlightCapture, capture_id)
    if capture is None:
        raise HTTPException(status_code=404, detail="Flight capture not found")
    db.delete(capture)
    db.commit()
