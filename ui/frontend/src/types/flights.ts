import type { GeoJSONLineString } from './index';

export type FlightStatus = 'planned' | 'completed' | 'cancelled';

export interface Flight {
  id: number;
  project_id: number;
  name: string;
  status: FlightStatus;
  flight_path: GeoJSONLineString | null;
  notes: string | null;
  survey_id: number | null;
}

export interface FlightCreate {
  name: string;
  flight_path?: GeoJSONLineString | null;
  notes?: string | null;
}

export interface FlightUpdate {
  name?: string;
  flight_path?: GeoJSONLineString | null;
  notes?: string | null;
  status?: FlightStatus;
}
