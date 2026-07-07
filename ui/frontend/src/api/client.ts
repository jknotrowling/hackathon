import type {
  Flight,
  FlightCapture,
  FlightCreate,
  FlightUpdate,
  GeoJSONPolygon,
  Project,
  Region,
  RegionCreate,
  Stockpile,
  Survey,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  getProjects: () => request<Project[]>('/api/projects'),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  getBoundary: (projectId: number) =>
    request<GeoJSONPolygon>(`/api/projects/${projectId}/boundary`),
  getRegions: (projectId: number) =>
    request<Region[]>(`/api/projects/${projectId}/rois`),
  createRegion: (projectId: number, payload: RegionCreate) =>
    request<Region>(`/api/projects/${projectId}/rois`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateRegion: (regionId: number, payload: Partial<RegionCreate>) =>
    request<Region>(`/api/rois/${regionId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteRegion: (regionId: number) =>
    request<void>(`/api/rois/${regionId}`, { method: 'DELETE' }),
  getStockpiles: (projectId: number) =>
    request<Stockpile[]>(`/api/projects/${projectId}/stockpiles`),
  getSurveys: (projectId: number) =>
    request<Survey[]>(`/api/projects/${projectId}/surveys`),
  getFlights: (projectId: number) =>
    request<Flight[]>(`/api/projects/${projectId}/flights`),
  createFlight: (projectId: number, payload: FlightCreate) =>
    request<Flight>(`/api/projects/${projectId}/flights`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateFlight: (flightId: number, payload: FlightUpdate) =>
    request<Flight>(`/api/flights/${flightId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteFlight: (flightId: number) =>
    request<void>(`/api/flights/${flightId}`, { method: 'DELETE' }),
  planMappingFlights: (regionId: number) =>
    request<Flight[]>(`/api/rois/${regionId}/plan-flights`, { method: 'POST' }),
  getFlightCaptures: (projectId: number) =>
    request<FlightCapture[]>(`/api/projects/${projectId}/flight-captures`),
};
