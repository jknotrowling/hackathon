from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import Flight, Region
from app.services.mapping import compute_mapping_flight_paths


class FlightPlanningError(Exception):
    """Base error for flight planning failures."""


class RegionNotFoundError(FlightPlanningError):
    """Raised when the requested region does not exist."""


@dataclass(frozen=True)
class MappingFlightPlan:
    name: str
    flight_path: Any | None
    notes: str | None


def _resolve_region(db: Session, region: Region | int) -> Region:
    if isinstance(region, Region):
        return region

    resolved = db.get(Region, region)
    if resolved is None:
        raise RegionNotFoundError(f"Region {region} not found")
    return resolved


def _build_mapping_flight_plans(region: Region) -> list[MappingFlightPlan]:
    flight_paths = compute_mapping_flight_paths(region.geometry)
    if not flight_paths:
        return [
            MappingFlightPlan(
                name=f"Mapping flight – {region.name}",
                flight_path=None,
                notes=f"Auto-planned mapping flight for region {region.name}",
            )
        ]

    plans: list[MappingFlightPlan] = []
    for index, flight_path in enumerate(flight_paths, start=1):
        suffix = f" {index}/{len(flight_paths)}" if len(flight_paths) > 1 else ""
        plans.append(
            MappingFlightPlan(
                name=f"Mapping flight{suffix} – {region.name}",
                flight_path=flight_path,
                notes=f"Auto-planned mapping flight for region {region.name}",
            )
        )
    return plans


def plan_mapping_flights(db: Session, region: Region | int) -> list[Flight]:
    """Plan mapping flights for a region and persist them as planned flights."""
    resolved_region = _resolve_region(db, region)
    plans = _build_mapping_flight_plans(resolved_region)

    flights: list[Flight] = []
    for plan in plans:
        flight = Flight(
            project_id=resolved_region.project_id,
            name=plan.name,
            status="planned",
            flight_path=plan.flight_path,
            notes=plan.notes,
        )
        db.add(flight)
        flights.append(flight)

    db.commit()
    for flight in flights:
        db.refresh(flight)
    return flights
