from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo import geojson_to_wkt, wkt_to_geojson
from app.models import Flight, Project
from app.schemas import FlightCreate, FlightResponse, FlightUpdate

router = APIRouter(tags=["flights"])


def _flight_response(flight: Flight) -> FlightResponse:
    return FlightResponse(
        id=flight.id,
        project_id=flight.project_id,
        name=flight.name,
        status=flight.status,
        flight_path=wkt_to_geojson(flight.flight_path),
        notes=flight.notes,
        survey_id=flight.survey_id,
    )


@router.get("/api/projects/{project_id}/flights", response_model=list[FlightResponse])
def list_flights(project_id: int, db: Session = Depends(get_db)) -> list[FlightResponse]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    flights = (
        db.query(Flight)
        .filter(Flight.project_id == project_id)
        .order_by(Flight.id.desc())
        .all()
    )
    return [_flight_response(flight) for flight in flights]


@router.post("/api/projects/{project_id}/flights", response_model=FlightResponse, status_code=201)
def plan_flight(project_id: int, payload: FlightCreate, db: Session = Depends(get_db)) -> FlightResponse:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    flight = Flight(
        project_id=project_id,
        name=payload.name,
        status="planned",
        notes=payload.notes,
        flight_path=geojson_to_wkt(payload.flight_path.model_dump()) if payload.flight_path else None,
    )
    db.add(flight)
    db.commit()
    db.refresh(flight)
    return _flight_response(flight)


@router.put("/api/flights/{flight_id}", response_model=FlightResponse)
def update_flight(flight_id: int, payload: FlightUpdate, db: Session = Depends(get_db)) -> FlightResponse:
    flight = db.get(Flight, flight_id)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")

    if payload.name is not None:
        flight.name = payload.name
    if payload.notes is not None:
        flight.notes = payload.notes
    if payload.flight_path is not None:
        flight.flight_path = geojson_to_wkt(payload.flight_path.model_dump())
    if payload.status is not None:
        flight.status = payload.status

    db.commit()
    db.refresh(flight)
    return _flight_response(flight)


@router.delete("/api/flights/{flight_id}", status_code=204)
def delete_flight(flight_id: int, db: Session = Depends(get_db)) -> None:
    flight = db.get(Flight, flight_id)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    db.delete(flight)
    db.commit()
