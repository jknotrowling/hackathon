from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo import wkt_to_geojson
from app.models import Project, Stockpile, StockpileMeasurement
from app.schemas import StockpileResponse

router = APIRouter(prefix="/api/projects", tags=["stockpiles"])


@router.get("/{project_id}/stockpiles", response_model=list[StockpileResponse])
def list_stockpiles(project_id: int, db: Session = Depends(get_db)) -> list[StockpileResponse]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stockpiles = db.query(Stockpile).filter(Stockpile.project_id == project_id).order_by(Stockpile.name).all()
    results: list[StockpileResponse] = []

    for stockpile in stockpiles:
        latest = (
            db.query(StockpileMeasurement)
            .filter(StockpileMeasurement.stockpile_id == stockpile.id)
            .order_by(StockpileMeasurement.measured_at.desc())
            .first()
        )
        last_scan = latest.measured_at.date().isoformat() if latest else None
        results.append(
            StockpileResponse(
                id=stockpile.id,
                name=stockpile.name,
                material=stockpile.material,
                volume=stockpile.volume,
                last_scan=last_scan,
                geometry=wkt_to_geojson(stockpile.geometry),
            )
        )

    return results
