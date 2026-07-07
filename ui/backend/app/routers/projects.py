from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo import wkt_to_geojson
from app.models import Project
from app.schemas import GeoJSONPolygon, ProjectDetail, ProjectSummary

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).order_by(Project.name).all()


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/boundary", response_model=GeoJSONPolygon)
def get_project_boundary(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.boundary is None:
        raise HTTPException(status_code=404, detail="Boundary not defined")
    geojson = wkt_to_geojson(project.boundary)
    if geojson is None:
        raise HTTPException(status_code=404, detail="Boundary not defined")
    return geojson
