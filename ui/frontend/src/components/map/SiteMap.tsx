import { useEffect, useRef, useState } from 'react';
import maplibregl, { Map, MapLayerMouseEvent, MapMouseEvent } from 'maplibre-gl';

import type { Flight, GeoJSONLineString, GeoJSONPolygon, Region, Stockpile } from '../../types';

import 'maplibre-gl/dist/maplibre-gl.css';

type SiteMapProps = {
  boundary: GeoJSONPolygon | null;
  regions: Region[];
  stockpiles: Stockpile[];
  flights: Flight[];
  drawMode: boolean;
  flightPlanMode: boolean;
  selectedRegionId: number | null;
  selectedFlightId: number | null;
  onSelectRegion: (regionId: number | null) => void;
  onSelectFlight: (flightId: number | null) => void;
  onDraftGeometry: (geometry: GeoJSONPolygon | null) => void;
  onDraftFlightPath: (geometry: GeoJSONLineString | null) => void;
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

function flightPathToPointFeatures(flight: Flight) {
  if (!flight.flight_path) {
    return [];
  }

  return flight.flight_path.coordinates.map((coordinate, index) => ({
    type: 'Feature' as const,
    properties: {
      id: flight.id,
      status: flight.status,
      name: flight.name,
      index,
    },
    geometry: {
      type: 'Point' as const,
      coordinates: coordinate,
    },
  }));
}

function pointsToPolygon(points: [number, number][]): GeoJSONPolygon | null {
  if (points.length < 3) {
    return null;
  }
  const ring = [...points, points[0]];
  return { type: 'Polygon', coordinates: [ring] };
}

function pointsToLineString(points: [number, number][]): GeoJSONLineString | null {
  if (points.length < 2) {
    return null;
  }
  return { type: 'LineString', coordinates: points };
}

export function SiteMap({
  boundary,
  regions,
  stockpiles,
  flights,
  drawMode,
  flightPlanMode,
  selectedRegionId,
  selectedFlightId,
  onSelectRegion,
  onSelectFlight,
  onDraftGeometry,
  onDraftFlightPath,
  showFlightPaths,
}: SiteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const roiPointsRef = useRef<[number, number][]>([]);
  const flightPointsRef = useRef<[number, number][]>([]);
  const onSelectRegionRef = useRef(onSelectRegion);
  const onSelectFlightRef = useRef(onSelectFlight);
  const onDraftGeometryRef = useRef(onDraftGeometry);
  const onDraftFlightPathRef = useRef(onDraftFlightPath);
  const [mapReady, setMapReady] = useState(false);

  onSelectRegionRef.current = onSelectRegion;
  onSelectFlightRef.current = onSelectFlight;
  onDraftGeometryRef.current = onDraftGeometry;
  onDraftFlightPathRef.current = onDraftFlightPath;

  const updateDraftRoiLayer = (map: Map, points: [number, number][]) => {
    const polygon = pointsToPolygon(points);
    const lineCoordinates = points.length > 1 ? points : [];
    const data: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        ...(polygon
          ? [{ type: 'Feature' as const, properties: { kind: 'draft-fill' }, geometry: polygon }]
          : []),
        ...(lineCoordinates.length > 0
          ? [{
              type: 'Feature' as const,
              properties: { kind: 'draft-line' },
              geometry: { type: 'LineString' as const, coordinates: lineCoordinates },
            }]
          : []),
        ...points.map((point, index) => ({
          type: 'Feature' as const,
          properties: { kind: 'draft-point', index },
          geometry: { type: 'Point' as const, coordinates: point },
        })),
      ],
    };

    const source = map.getSource('draft-roi') as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(data);
    } else {
      map.addSource('draft-roi', { type: 'geojson', data });
      map.addLayer({
        id: 'draft-roi-fill',
        type: 'fill',
        source: 'draft-roi',
        filter: ['==', ['get', 'kind'], 'draft-fill'],
        paint: { 'fill-color': '#ffd43b', 'fill-opacity': 0.25 },
      });
      map.addLayer({
        id: 'draft-roi-line',
        type: 'line',
        source: 'draft-roi',
        filter: ['==', ['get', 'kind'], 'draft-line'],
        paint: { 'line-color': '#ffd43b', 'line-width': 2, 'line-dasharray': [2, 2] },
      });
      map.addLayer({
        id: 'draft-roi-points',
        type: 'circle',
        source: 'draft-roi',
        filter: ['==', ['get', 'kind'], 'draft-point'],
        paint: { 'circle-radius': 5, 'circle-color': '#ffd43b', 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' },
      });
    }

    onDraftGeometryRef.current(polygon);
  };

  const updateDraftFlightLayer = (map: Map, points: [number, number][]) => {
    const line = pointsToLineString(points);
    const data: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [
        ...(line
          ? [{ type: 'Feature' as const, properties: { kind: 'draft-flight-line' }, geometry: line }]
          : []),
        ...points.map((point, index) => ({
          type: 'Feature' as const,
          properties: { kind: 'draft-flight-point', index },
          geometry: { type: 'Point' as const, coordinates: point },
        })),
      ],
    };

    const source = map.getSource('draft-flight') as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(data);
    } else {
      map.addSource('draft-flight', { type: 'geojson', data });
      map.addLayer({
        id: 'draft-flight-line',
        type: 'line',
        source: 'draft-flight',
        filter: ['==', ['get', 'kind'], 'draft-flight-line'],
        paint: { 'line-color': '#74c0fc', 'line-width': 3, 'line-dasharray': [2, 2] },
      });
      map.addLayer({
        id: 'draft-flight-points',
        type: 'circle',
        source: 'draft-flight',
        filter: ['==', ['get', 'kind'], 'draft-flight-point'],
        paint: { 'circle-radius': 5, 'circle-color': '#74c0fc', 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' },
      });
    }

    onDraftFlightPathRef.current(line);
  };

  const clearDraftRoiLayer = (map: Map) => {
    roiPointsRef.current = [];
    onDraftGeometryRef.current(null);
    if (map.getSource('draft-roi')) {
      (map.getSource('draft-roi') as maplibregl.GeoJSONSource).setData({
        type: 'FeatureCollection',
        features: [],
      });
    }
  };

  const clearDraftFlightLayer = (map: Map) => {
    flightPointsRef.current = [];
    onDraftFlightPathRef.current(null);
    if (map.getSource('draft-flight')) {
      (map.getSource('draft-flight') as maplibregl.GeoJSONSource).setData({
        type: 'FeatureCollection',
        features: [],
      });
    }
  };

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center: [11.58, 48.138],
      zoom: 14,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.on('load', () => {
      setMapReady(true);
      requestAnimationFrame(() => map.resize());
    });

    const container = containerRef.current;
    const resizeObserver = new ResizeObserver(() => mapRef.current?.resize());
    resizeObserver.observe(container);

    mapRef.current = map;

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
      roiPointsRef.current = [];
      flightPointsRef.current = [];
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }

    if (!drawMode) {
      clearDraftRoiLayer(map);
      if (!flightPlanMode) {
        map.getCanvas().style.cursor = '';
      }
      if (!flightPlanMode) {
        return;
      }
    }

    if (drawMode) {
      map.getCanvas().style.cursor = 'crosshair';

      const handleClick = (event: MapMouseEvent) => {
        roiPointsRef.current = [...roiPointsRef.current, [event.lngLat.lng, event.lngLat.lat]];
        updateDraftRoiLayer(map, roiPointsRef.current);
      };

      const handleDoubleClick = (event: MapMouseEvent) => {
        event.preventDefault();
        const polygon = pointsToPolygon(roiPointsRef.current);
        if (polygon) {
          onDraftGeometryRef.current(polygon);
        }
      };

      map.on('click', handleClick);
      map.on('dblclick', handleDoubleClick);
      map.doubleClickZoom.disable();

      return () => {
        map.off('click', handleClick);
        map.off('dblclick', handleDoubleClick);
        map.doubleClickZoom.enable();
      };
    }

    return undefined;
  }, [drawMode, flightPlanMode, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }

    if (!flightPlanMode) {
      clearDraftFlightLayer(map);
      if (!drawMode) {
        map.getCanvas().style.cursor = '';
      }
      if (!drawMode) {
        return;
      }
    }

    if (flightPlanMode) {
      map.getCanvas().style.cursor = 'crosshair';

      const handleClick = (event: MapMouseEvent) => {
        flightPointsRef.current = [...flightPointsRef.current, [event.lngLat.lng, event.lngLat.lat]];
        updateDraftFlightLayer(map, flightPointsRef.current);
      };

      const handleDoubleClick = (event: MapMouseEvent) => {
        event.preventDefault();
        const line = pointsToLineString(flightPointsRef.current);
        if (line) {
          onDraftFlightPathRef.current(line);
        }
      };

      map.on('click', handleClick);
      map.on('dblclick', handleDoubleClick);
      map.doubleClickZoom.disable();

      return () => {
        map.off('click', handleClick);
        map.off('dblclick', handleDoubleClick);
        map.doubleClickZoom.enable();
      };
    }

    return undefined;
  }, [flightPlanMode, drawMode, mapReady]);

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
        polygonToFeature(region.id, region.geometry, { id: region.id, name: region.name }),
      ),
    });
    upsertLayer({
      id: 'roi-fill',
      type: 'fill',
      source: 'rois',
      paint: {
        'fill-color': ['case', ['==', ['get', 'id'], selectedRegionId ?? -1], '#ffd43b', '#339af0'],
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
      const flightFeatures = flights
        .filter((flight) => flight.flight_path)
        .map((flight) =>
          lineToFeature(flight.id, flight.flight_path!, {
            id: flight.id,
            status: flight.status,
            name: flight.name,
          }),
        );

      const flightPointFeatures = flights.flatMap((flight) => flightPathToPointFeatures(flight));

      upsertSource('flights', { type: 'FeatureCollection', features: flightFeatures });
      upsertSource('flight-points', { type: 'FeatureCollection', features: flightPointFeatures });

      if (!map.getLayer('flight-path-completed')) {
        map.addLayer({
          id: 'flight-path-completed',
          type: 'line',
          source: 'flights',
          filter: ['==', ['get', 'status'], 'completed'],
          paint: {
            'line-color': [
              'case',
              ['==', ['get', 'id'], selectedFlightId ?? -1],
              '#ffd43b',
              '#51cf66',
            ],
            'line-width': ['case', ['==', ['get', 'id'], selectedFlightId ?? -1], 5, 3],
          },
        });
      }

      if (!map.getLayer('flight-path-planned')) {
        map.addLayer({
          id: 'flight-path-planned',
          type: 'line',
          source: 'flights',
          filter: ['==', ['get', 'status'], 'planned'],
          paint: {
            'line-color': [
              'case',
              ['==', ['get', 'id'], selectedFlightId ?? -1],
              '#ffd43b',
              '#339af0',
            ],
            'line-width': ['case', ['==', ['get', 'id'], selectedFlightId ?? -1], 5, 3],
            'line-dasharray': [2, 2],
          },
        });
      }

      upsertLayer({
        id: 'flight-points-completed',
        type: 'circle',
        source: 'flight-points',
        filter: ['==', ['get', 'status'], 'completed'],
        paint: {
          'circle-radius': ['case', ['==', ['get', 'id'], selectedFlightId ?? -1], 3, 2],
          'circle-color': [
            'case',
            ['==', ['get', 'id'], selectedFlightId ?? -1],
            '#ffd43b',
            '#51cf66',
          ],
          'circle-opacity': 0.9,
        },
      });

      upsertLayer({
        id: 'flight-points-planned',
        type: 'circle',
        source: 'flight-points',
        filter: ['==', ['get', 'status'], 'planned'],
        paint: {
          'circle-radius': ['case', ['==', ['get', 'id'], selectedFlightId ?? -1], 3, 2],
          'circle-color': [
            'case',
            ['==', ['get', 'id'], selectedFlightId ?? -1],
            '#ffd43b',
            '#339af0',
          ],
          'circle-opacity': 0.9,
        },
      });

      for (const [layerId, baseColor] of [
        ['flight-points-completed', '#51cf66'],
        ['flight-points-planned', '#339af0'],
      ] as const) {
        if (!map.getLayer(layerId)) {
          continue;
        }
        map.setPaintProperty(layerId, 'circle-radius', [
          'case',
          ['==', ['get', 'id'], selectedFlightId ?? -1],
          3,
          2,
        ]);
        map.setPaintProperty(layerId, 'circle-color', [
          'case',
          ['==', ['get', 'id'], selectedFlightId ?? -1],
          '#ffd43b',
          baseColor,
        ]);
      }
    } else {
      for (const layerId of [
        'flight-path-completed',
        'flight-path-planned',
        'flight-points-completed',
        'flight-points-planned',
      ]) {
        if (map.getLayer(layerId)) {
          map.removeLayer(layerId);
        }
      }
      for (const sourceId of ['flights', 'flight-points']) {
        if (map.getSource(sourceId)) {
          map.removeSource(sourceId);
        }
      }
    }

    if (boundary && !drawMode && !flightPlanMode) {
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
  }, [
    boundary,
    regions,
    stockpiles,
    flights,
    selectedRegionId,
    selectedFlightId,
    showFlightPaths,
    mapReady,
    drawMode,
    flightPlanMode,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || drawMode || flightPlanMode) {
      return;
    }

    const handleRoiClick = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (feature?.properties?.id != null) {
        onSelectRegionRef.current(Number(feature.properties.id));
      }
    };

    const handleFlightClick = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (feature?.properties?.id != null) {
        onSelectFlightRef.current(Number(feature.properties.id));
      }
    };

    if (map.getLayer('roi-fill')) {
      map.on('click', 'roi-fill', handleRoiClick);
    }
    if (map.getLayer('flight-path-completed')) {
      map.on('click', 'flight-path-completed', handleFlightClick);
    }
    if (map.getLayer('flight-path-planned')) {
      map.on('click', 'flight-path-planned', handleFlightClick);
    }
    if (map.getLayer('flight-points-completed')) {
      map.on('click', 'flight-points-completed', handleFlightClick);
    }
    if (map.getLayer('flight-points-planned')) {
      map.on('click', 'flight-points-planned', handleFlightClick);
    }

    return () => {
      map.off('click', 'roi-fill', handleRoiClick);
      map.off('click', 'flight-path-completed', handleFlightClick);
      map.off('click', 'flight-path-planned', handleFlightClick);
      map.off('click', 'flight-points-completed', handleFlightClick);
      map.off('click', 'flight-points-planned', handleFlightClick);
    };
  }, [mapReady, drawMode, flightPlanMode, regions, flights]);

  return <div ref={containerRef} className="map-container" />;
}
