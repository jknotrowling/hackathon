from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Flight, FlightCapture, Project, Region, Stockpile, StockpileMeasurement, Survey
from app.routers import flight_captures, flights, projects, rois, stockpiles, surveys


def seed_database() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Project).first()
        if existing is not None:
            return

        project = Project(
            name="Construction Site A",
            description="Demo construction site with gravel and sand stockpiles.",
            location="Munich, Germany",
            boundary=WKTElement(
                "POLYGON((11.575 48.135, 11.585 48.135, 11.585 48.142, 11.575 48.142, 11.575 48.135))",
                srid=4326,
            ),
        )
        db.add(project)
        db.flush()

        roi = Region(
            project_id=project.id,
            name="Scan Area North",
            geometry=WKTElement(
                "POLYGON((11.577 48.137, 11.582 48.137, 11.582 48.140, 11.577 48.140, 11.577 48.137))",
                srid=4326,
            ),
        )
        db.add(roi)

        # gravel = Stockpile(
        #     project_id=project.id,
        #     name="Gravel pile",
        #     material="gravel",
        #     volume=3500,
        #     geometry=WKTElement(
        #         "POLYGON((11.578 48.138, 11.580 48.138, 11.580 48.139, 11.578 48.139, 11.578 48.138))",
        #         srid=4326,
        #     ),
        # )
        # sand = Stockpile(
        #     project_id=project.id,
        #     name="Sand pile",
        #     material="sand",
        #     volume=2100,
        #     geometry=WKTElement(
        #         "POLYGON((11.581 48.138, 11.583 48.138, 11.583 48.139, 11.581 48.139, 11.581 48.138))",
        #         srid=4326,
        #     ),
        # )
        # db.add_all([gravel, sand])
        # db.flush()

        # survey_dates = [
        #     datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        #     datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        #     datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        # ]
        # gravel_volumes = [3200, 3350, 3500]
        # sand_volumes = [1900, 2000, 2100]

        # for index, survey_date in enumerate(survey_dates):
        #     survey = Survey(
        #         project_id=project.id,
        #         timestamp=survey_date,
        #         data_reference=f"survey-{index + 1:03d}",
        #         flight_path=WKTElement(
        #             "LINESTRING(11.576 48.136, 11.578 48.139, 11.582 48.139, 11.584 48.136)",
        #             srid=4326,
        #         ),
        #         orthophoto_url="https://tile.openstreetmap.org/11/1100/715.png",
        #     )
        #     db.add(survey)
        #     db.flush()
        #     db.add_all(
        #         [
        #             StockpileMeasurement(
        #                 stockpile_id=gravel.id,
        #                 survey_id=survey.id,
        #                 volume=gravel_volumes[index],
        #                 measured_at=survey_date,
        #             ),
        #             StockpileMeasurement(
        #                 stockpile_id=sand.id,
        #                 survey_id=survey.id,
        #                 volume=sand_volumes[index],
        #                 measured_at=survey_date,
        #             ),
        #         ]
        #     )

        db.commit()
    finally:
        db.close()


def seed_flights() -> None:
    db = SessionLocal()
    try:
        project = db.query(Project).first()
        if project is None or db.query(Flight).filter(Flight.project_id == project.id).first() is not None:
            return

        db.add_all(
            [
                Flight(
                    project_id=project.id,
                    name="May survey flight",
                    status="completed",
                    flight_path=WKTElement(
                        "LINESTRING(11.576 48.136, 11.578 48.139, 11.582 48.139, 11.584 48.136)",
                        srid=4326,
                    ),
                    notes="Initial site scan",
                ),
                Flight(
                    project_id=project.id,
                    name="June survey flight",
                    status="completed",
                    flight_path=WKTElement(
                        "LINESTRING(11.577 48.136, 11.579 48.139, 11.583 48.138, 11.585 48.137)",
                        srid=4326,
                    ),
                    notes="Monthly progress scan",
                ),
                Flight(
                    project_id=project.id,
                    name="August survey flight",
                    status="planned",
                    flight_path=WKTElement(
                        "LINESTRING(11.576 48.137, 11.580 48.140, 11.584 48.138, 11.582 48.136)",
                        srid=4326,
                    ),
                    notes="Planned stockpile update",
                ),
                Flight(
                    project_id=project.id,
                    name="September survey flight",
                    status="planned",
                    flight_path=WKTElement(
                        "LINESTRING(11.578 48.136, 11.581 48.139, 11.585 48.137, 11.579 48.136)",
                        srid=4326,
                    ),
                    notes="End of summer capture",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def seed_flight_captures() -> None:
    db = SessionLocal()
    try:
        if db.query(FlightCapture).first() is not None:
            return

        flights = (
            db.query(Flight)
            .filter(Flight.status == "completed", Flight.flight_path.isnot(None))
            .order_by(Flight.id)
            .all()
        )
        placeholder_count = 4
        for flight in flights:
            line = to_shape(flight.flight_path)
            for index, (lng, lat) in enumerate(line.coords):
                db.add(
                    FlightCapture(
                        flight_id=flight.id,
                        waypoint_index=index,
                        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
                        image_url=f"/captures/placeholder-{(index % placeholder_count) + 1}.svg",
                    )
                )
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.execute(text("ALTER TABLE IF EXISTS flights DROP COLUMN IF EXISTS scheduled_at"))
        connection.commit()
    Base.metadata.create_all(bind=engine)
    seed_database()
    seed_flights()
    seed_flight_captures()
    yield


app = FastAPI(title="Construction Site Monitoring API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(rois.router)
app.include_router(stockpiles.router)
app.include_router(surveys.router)
app.include_router(flights.router)
app.include_router(flight_captures.router)

CAPTURES_DIR = Path(__file__).resolve().parent.parent / "static" / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=CAPTURES_DIR), name="captures")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
