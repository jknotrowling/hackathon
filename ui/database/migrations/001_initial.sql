-- Reference schema for PostgreSQL + PostGIS.
-- Tables are also created automatically by the backend on startup.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location VARCHAR(255),
    boundary GEOMETRY(POLYGON, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS regions (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    geometry GEOMETRY(POLYGON, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS stockpiles (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    material VARCHAR(100) NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    geometry GEOMETRY(POLYGON, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS surveys (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    data_reference VARCHAR(512),
    flight_path GEOMETRY(LINESTRING, 4326),
    orthophoto_url VARCHAR(512)
);

CREATE TABLE IF NOT EXISTS stockpile_measurements (
    id SERIAL PRIMARY KEY,
    stockpile_id INTEGER NOT NULL REFERENCES stockpiles(id) ON DELETE CASCADE,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    volume DOUBLE PRECISION NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_regions_project_id ON regions(project_id);
CREATE INDEX IF NOT EXISTS idx_stockpiles_project_id ON stockpiles(project_id);
CREATE INDEX IF NOT EXISTS idx_surveys_project_id ON surveys(project_id);
CREATE INDEX IF NOT EXISTS idx_measurements_stockpile_id ON stockpile_measurements(stockpile_id);

CREATE TABLE IF NOT EXISTS flights (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'planned',
    flight_path GEOMETRY(LINESTRING, 4326),
    notes TEXT,
    survey_id INTEGER REFERENCES surveys(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_flights_project_id ON flights(project_id);
