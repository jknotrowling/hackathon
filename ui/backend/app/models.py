from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    boundary: Mapped[str | None] = mapped_column(Geometry("POLYGON", srid=4326))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    regions: Mapped[list["Region"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    stockpiles: Mapped[list["Stockpile"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    surveys: Mapped[list["Survey"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    flights: Mapped[list["Flight"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    geometry: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="regions")


class Stockpile(Base):
    __tablename__ = "stockpiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    material: Mapped[str] = mapped_column(String(100), nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    geometry: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="stockpiles")
    measurements: Mapped[list["StockpileMeasurement"]] = relationship(
        back_populates="stockpile", cascade="all, delete-orphan"
    )


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_reference: Mapped[str | None] = mapped_column(String(512))
    flight_path: Mapped[str | None] = mapped_column(Geometry("LINESTRING", srid=4326))
    orthophoto_url: Mapped[str | None] = mapped_column(String(512))

    project: Mapped["Project"] = relationship(back_populates="surveys")


class StockpileMeasurement(Base):
    __tablename__ = "stockpile_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stockpile_id: Mapped[int] = mapped_column(ForeignKey("stockpiles.id", ondelete="CASCADE"), nullable=False)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    stockpile: Mapped["Stockpile"] = relationship(back_populates="measurements")


class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    flight_path: Mapped[str | None] = mapped_column(Geometry("LINESTRING", srid=4326))
    notes: Mapped[str | None] = mapped_column(Text)
    survey_id: Mapped[int | None] = mapped_column(ForeignKey("surveys.id", ondelete="SET NULL"))

    project: Mapped["Project"] = relationship(back_populates="flights")
