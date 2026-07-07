# Construction Site Monitoring Platform

Web-based construction site monitoring with drone survey visualization, ROI editing, and stockpile history.

## Architecture

- **Frontend**: React + TypeScript + Vite, MapLibre GL JS, Mantine, TanStack Query, ECharts
- **Backend**: FastAPI + SQLAlchemy + PostGIS
- **Database**: PostgreSQL with PostGIS extension

## Quick Start (Docker)

```powershell
cd UI
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Local Development

### Database

```powershell
cd UI
docker compose up db -d
```

### Backend

```powershell
cd UI/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd UI/frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` if needed (default).

## Milestone Features

1. MapLibre map with satellite imagery
2. Example project with boundary, ROIs, stockpiles, and surveys
3. Draw and save ROI polygons (click-to-draw on map)
4. Display stockpile polygons and flight paths (completed + planned)
5. Stockpile table and historical volume charts
6. Flight overview with upcoming/completed flights and flight planning

## API Endpoints

- `GET /api/projects`
- `GET /api/projects/{id}`
- `GET /api/projects/{id}/boundary`
- `GET/POST /api/projects/{id}/rois`
- `PUT/DELETE /api/rois/{id}`
- `GET /api/projects/{id}/stockpiles`
- `GET /api/projects/{id}/surveys`
- `GET/POST /api/projects/{id}/flights`
- `PUT/DELETE /api/flights/{id}`
