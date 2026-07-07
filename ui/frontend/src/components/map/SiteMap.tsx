import { useEffect, useRef, useState } from 'react';
import maplibregl, { Map, MapLayerMouseEvent } from 'maplibre-gl';
import { TerraDraw } from 'terra-draw';
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter';
import {
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
} from 'terra-draw';

import type { GeoJSONLineString, GeoJSONPolygon, Region, Stockpile, Survey } from '../../types';

import 'maplibre-gl/dist/maplibre-gl.css';

type SiteMapProps = {
  boundary: GeoJSONPolygon | null;
  regions: Region[];
  stockpiles: Stockpile[];
  surveys: Survey[];
  drawMode: boolean;
  selectedRegionId: number | null;
  onSelectRegion: (regionId: number | null) => void;
  onDraftGeometry: (geometry: GeoJSONPolygon | null) => void;
  showFlightPaths: boolean;
};

const SATELLITE_STYLE = {
  version: 8,
  sources: {
    satellite: {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: 'Esri World Imagery',
    },
  },
  layers: [
    {
      id: 'satellite',
      type: 'raster',
      source: 'satellite',
    },
  ],
} as maplibregl.StyleSpecification;

function polygonToFeature(id: string | number, geometry: GeoJSONPolygon, properties: Record<string, unknown>) {
  return {
    type: 'Feature' as const,
    id,
    properties,
    geometry,
  };
}

function lineToFeature(id: string | number, geometry: GeoJSONLineString, properties: Record<string, unknown>) {
  return {
    type: 'Feature' as const,
    id,
    properties,
    geometry,
  };
}

export function SiteMap({
  boundary,
  regions,
  stockpiles,
  surveys,
  drawMode,
  selectedRegionId,
  onSelectRegion,
  onDraftGeometry,
  showFlightPaths,
}: SiteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center: [11.58, 48.138],
      zoom: 14,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    const draw = new TerraDraw({
      adapter: new TerraDrawMapLibreGLAdapter({ map }),
      modes: [
        new TerraDrawSelectMode({
          flags: {
            polygon: {
              feature: {
                draggable: true,
                coordinates: {
                  midpoints: true,
                  draggable: true,
                  deletable: true,
                },
              },
            },
          },
        }),
        new TerraDrawPolygonMode(),
      ],
    });

    map.on('load', () => {
      draw.start();
      draw.setMode('select');
      setMapReady(true);
    });

    draw.on('finish', (id) => {
      const snapshot = draw.getSnapshot();
      const feature = snapshot.find((item) => String(item.id) === String(id));
      if (feature && feature.geometry.type === 'Polygon') {
        onDraftGeometry(feature.geometry as GeoJSONPolygon);
      }
    });

    draw.on('change', () => {
      const snapshot = draw.getSnapshot();
      const draft = snapshot.find((feature) => feature.properties?.draft);
      if (draft && draft.geometry.type === 'Polygon') {
        onDraftGeometry(draft.geometry as GeoJSONPolygon);
      }
    });

    map.on('click', 'roi-fill', (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (feature?.properties?.id) {
        onSelectRegion(Number(feature.properties.id));
      }
    });

    mapRef.current = map;
    drawRef.current = draw;

    return () => {
      draw.stop();
      map.remove();
      mapRef.current = null;
      drawRef.current = null;
      setMapReady(false);
    };
  }, [onDraftGeometry, onSelectRegion]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }

    const upsertSource = (sourceId: string, data: GeoJSON.FeatureCollection) => {
      const existing = map.getSource(sourceId);
      if (existing) {
        (existing as maplibregl.GeoJSONSource).setData(data);
      } else {
        map.addSource(sourceId, { type: 'geojson', data });
      }
    };

    const upsertLayer = (layer: maplibregl.LayerSpecification) => {
      if (!map.getLayer(layer.id)) {
        map.addLayer(layer);
      }
    };

    if (boundary) {
      upsertSource('boundary', {
        type: 'FeatureCollection',
        features: [polygonToFeature('boundary', boundary, { kind: 'boundary' })],
      });
      upsertLayer({
        id: 'boundary-line',
        type: 'line',
        source: 'boundary',
        paint: { 'line-color': '#ffffff', 'line-width': 3 },
      });
    }

    upsertSource('rois', {
      type: 'FeatureCollection',
      features: regions.map((region) =>
        polygonToFeature(region.id, region.geometry, {
          id: region.id,
          name: region.name,
        }),
      ),
    });
    upsertLayer({
      id: 'roi-fill',
      type: 'fill',
      source: 'rois',
      paint: {
        'fill-color': [
          'case',
          ['==', ['get', 'id'], selectedRegionId ?? -1],
          '#ffd43b',
          '#339af0',
        ],
        'fill-opacity': 0.35,
      },
    });
    upsertLayer({
      id: 'roi-line',
      type: 'line',
      source: 'rois',
      paint: { 'line-color': '#1864ab', 'line-width': 2 },
    });

    upsertSource('stockpiles', {
      type: 'FeatureCollection',
      features: stockpiles
        .filter((stockpile) => stockpile.geometry)
        .map((stockpile) =>
          polygonToFeature(stockpile.id, stockpile.geometry!, {
            id: stockpile.id,
            name: stockpile.name,
            material: stockpile.material,
          }),
        ),
    });
    upsertLayer({
      id: 'stockpile-fill',
      type: 'fill',
      source: 'stockpiles',
      paint: { 'fill-color': '#e8590c', 'fill-opacity': 0.45 },
    });
    upsertLayer({
      id: 'stockpile-line',
      type: 'line',
      source: 'stockpiles',
      paint: { 'line-color': '#d9480f', 'line-width': 2 },
    });

    if (showFlightPaths) {
      upsertSource('flights', {
        type: 'FeatureCollection',
        features: surveys
          .filter((survey) => survey.flight_path)
          .map((survey) =>
            lineToFeature(survey.id, survey.flight_path!, {
              id: survey.id,
              date: survey.timestamp,
            }),
          ),
      });
      upsertLayer({
        id: 'flight-path',
        type: 'line',
        source: 'flights',
        paint: { 'line-color': '#51cf66', 'line-width': 3, 'line-dasharray': [2, 1] },
      });
    } else if (map.getLayer('flight-path')) {
      map.removeLayer('flight-path');
      if (map.getSource('flights')) {
        map.removeSource('flights');
      }
    }

    if (boundary) {
      const coords = boundary.coordinates[0];
      const lngs = coords.map((coord) => coord[0]);
      const lats = coords.map((coord) => coord[1]);
      map.fitBounds(
        [
          [Math.min(...lngs), Math.min(...lats)],
          [Math.max(...lngs), Math.max(...lats)],
        ],
        { padding: 80, duration: 500 },
      );
    }
  }, [boundary, regions, stockpiles, surveys, selectedRegionId, showFlightPaths, mapReady]);

  useEffect(() => {
    const draw = drawRef.current;
    if (!draw) {
      return;
    }
    draw.setMode(drawMode ? 'polygon' : 'select');
  }, [drawMode]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
