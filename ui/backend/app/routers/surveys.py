from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo import wkt_to_geojson
from app.models import Project, Stockpile, StockpileMeasurement, Survey
from app.schemas import SurveyResponse

router = APIRouter(prefix="/api/projects", tags=["surveys"])


@router.get("/{project_id}/surveys", response_model=list[SurveyResponse])
def list_surveys(project_id: int, db: Session = Depends(get_db)) -> list[SurveyResponse]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    surveys = db.query(Survey).filter(Survey.project_id == project_id).order_by(Survey.timestamp.desc()).all()
    stockpiles = db.query(Stockpile).filter(Stockpile.project_id == project_id).all()
    stockpile_by_id = {stockpile.id: stockpile for stockpile in stockpiles}

    results: list[SurveyResponse] = []
    for survey in surveys:
        measurements = (
            db.query(StockpileMeasurement)
            .filter(StockpileMeasurement.survey_id == survey.id)
            .order_by(StockpileMeasurement.stockpile_id)
            .all()
        )
        stockpile_volumes = [
            {
                "stockpile_id": measurement.stockpile_id,
                "stockpile_name": stockpile_by_id[measurement.stockpile_id].name,
                "volume": measurement.volume,
            }
            for measurement in measurements
            if measurement.stockpile_id in stockpile_by_id
        ]
        results.append(
            SurveyResponse(
                id=survey.id,
                timestamp=survey.timestamp,
                data_reference=survey.data_reference,
                orthophoto_url=survey.orthophoto_url,
                flight_path=wkt_to_geojson(survey.flight_path),
                stockpile_volumes=stockpile_volumes,
            )
        )

    return results
