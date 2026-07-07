export interface Project {
  id: number;
  name: string;
  location: string | null;
  description?: string | null;
  created_at?: string;
}

export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface GeoJSONLineString {
  type: 'LineString';
  coordinates: number[][];
}

export interface Region {
  id: number;
  project_id: number;
  name: string;
  geometry: GeoJSONPolygon;
}

export interface RegionCreate {
  name: string;
  geometry: GeoJSONPolygon;
}

export interface Stockpile {
  id: number;
  name: string;
  material: string;
  volume: number;
  last_scan: string | null;
  geometry: GeoJSONPolygon | null;
}

export interface Survey {
  id: number;
  timestamp: string;
  data_reference: string | null;
  orthophoto_url: string | null;
  flight_path: GeoJSONLineString | null;
  stockpile_volumes: Array<{
    stockpile_id: number;
    stockpile_name: string;
    volume: number;
  }>;
}
