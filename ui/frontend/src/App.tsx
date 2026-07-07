import { AppShell, Loader, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useMemo, useState } from 'react';

import { ErrorBoundary } from './components/ErrorBoundary';
import { FlightListPanel } from './components/flights/FlightListPanel';
import { FlightPlanForm } from './components/flights/FlightPlanForm';
import { Sidebar } from './components/layout/Sidebar';
import { Toolbar } from './components/layout/Toolbar';
import { SiteMap } from './components/map/SiteMap';
import { CapturesPanel } from './components/panels/CapturesPanel';
import { HistoryPanel } from './components/panels/HistoryPanel';
import {
  useBoundary,
  useFlightCaptures,
  useFlightMutations,
  useFlights,
  useProjects,
  useRegionMutations,
  useRegions,
  useStockpiles,
  useSurveys,
} from './hooks/useProjectData';
import type { FlightCreate, GeoJSONLineString, GeoJSONPolygon } from './types';

const HEADER_HEIGHT = 64;
const FOOTER_HISTORY = 340;
const FOOTER_FLIGHTS = 280;
const FOOTER_FLIGHTS_PLANNING = 320;
const FOOTER_CAPTURES = 340;

export function App() {
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [activePanel, setActivePanel] = useState<'sites' | 'flights' | 'history' | 'captures'>('sites');
  const [drawMode, setDrawMode] = useState(false);
  const [flightPlanMode, setFlightPlanMode] = useState(false);
  const [selectedRegionId, setSelectedRegionId] = useState<number | null>(null);
  const [selectedFlightId, setSelectedFlightId] = useState<number | null>(null);
  const [selectedCaptureId, setSelectedCaptureId] = useState<number | null>(null);
  const [captureFlightId, setCaptureFlightId] = useState<number | null>(null);
  const [selectedStockpileId, setSelectedStockpileId] = useState<number | null>(null);
  const [draftGeometry, setDraftGeometry] = useState<GeoJSONPolygon | null>(null);
  const [draftFlightPath, setDraftFlightPath] = useState<GeoJSONLineString | null>(null);
  const [planName, setPlanName] = useState('');
  const [planNotes, setPlanNotes] = useState('');

  const projectsQuery = useProjects();
  const projectId = selectedProjectId ?? projectsQuery.data?.[0]?.id ?? null;

  const boundaryQuery = useBoundary(projectId);
  const regionsQuery = useRegions(projectId);
  const stockpilesQuery = useStockpiles(projectId);
  const surveysQuery = useSurveys(projectId);
  const flightsQuery = useFlights(projectId);
  const flightCapturesQuery = useFlightCaptures(projectId);
  const regionMutations = useRegionMutations(projectId);
  const flightMutations = useFlightMutations(projectId);

  const selectedProject = useMemo(
    () => projectsQuery.data?.find((project) => project.id === projectId) ?? null,
    [projectsQuery.data, projectId],
  );

  const selectedRegion = regionsQuery.data?.find((region) => region.id === selectedRegionId) ?? null;

  const resetFlightPlan = () => {
    setFlightPlanMode(false);
    setDraftFlightPath(null);
    setPlanName('');
    setPlanNotes('');
  };

  const handleSaveRoi = async () => {
    if (!draftGeometry || !projectId) {
      notifications.show({
        color: 'yellow',
        title: 'No polygon drawn',
        message: 'Draw a polygon on the map before saving.',
      });
      return;
    }

    try {
      const name = `ROI ${(regionsQuery.data?.length ?? 0) + 1}`;
      await regionMutations.create.mutateAsync({ name, geometry: draftGeometry });
      setDraftGeometry(null);
      setDrawMode(false);
      notifications.show({ color: 'green', title: 'ROI saved', message: `${name} was stored successfully.` });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to save ROI',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const handleDeleteRoi = async () => {
    if (!selectedRegionId) return;

    try {
      await regionMutations.remove.mutateAsync(selectedRegionId);
      setSelectedRegionId(null);
      notifications.show({ color: 'green', title: 'ROI deleted', message: 'The selected region was removed.' });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to delete ROI',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const handlePlanFlight = async () => {
    if (!draftFlightPath || draftFlightPath.coordinates.length < 2) {
      notifications.show({
        color: 'yellow',
        title: 'No flight path drawn',
        message: 'Draw at least 2 points on the map before saving.',
      });
      return;
    }

    if (!planName.trim()) {
      notifications.show({
        color: 'yellow',
        title: 'Missing flight details',
        message: 'Enter a flight name.',
      });
      return;
    }

    const payload: FlightCreate = {
      name: planName.trim(),
      notes: planNotes.trim() || null,
      flight_path: draftFlightPath,
    };

    try {
      await flightMutations.create.mutateAsync(payload);
      resetFlightPlan();
      notifications.show({
        color: 'green',
        title: 'Flight planned',
        message: `${payload.name} was saved successfully.`,
      });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to plan flight',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const handlePlanMappingFlights = async () => {
    if (!selectedRegion) {
      return;
    }

    try {
      const flights = await flightMutations.planMapping.mutateAsync(selectedRegion.id);
      notifications.show({
        color: 'green',
        title: 'Mapping flights planned',
        message:
          flights.length === 1
            ? `${flights[0].name} was planned.`
            : `${flights.length} mapping flights were planned for "${selectedRegion.name}".`,
      });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to plan mapping flights',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const handleCancelFlight = async (flightId: number) => {
    try {
      await flightMutations.remove.mutateAsync(flightId);
      if (selectedFlightId === flightId) setSelectedFlightId(null);
      notifications.show({ color: 'green', title: 'Flight cancelled', message: 'The planned flight was removed.' });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to cancel flight',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const loading =
    projectsQuery.isPending ||
    (projectId !== null &&
      (boundaryQuery.isPending ||
        regionsQuery.isPending ||
        stockpilesQuery.isPending ||
        surveysQuery.isPending ||
        flightsQuery.isPending ||
        flightCapturesQuery.isPending));

  const error =
    projectsQuery.error ??
    boundaryQuery.error ??
    regionsQuery.error ??
    stockpilesQuery.error ??
    surveysQuery.error ??
    flightsQuery.error ??
    flightCapturesQuery.error;

  const showMap = projectId !== null && !error;
  const showFooter = activePanel === 'flights' || activePanel === 'history' || activePanel === 'captures';

  const footerHeight =
    activePanel === 'history' || activePanel === 'captures'
      ? activePanel === 'captures'
        ? FOOTER_CAPTURES
        : FOOTER_HISTORY
      : activePanel === 'flights'
        ? flightPlanMode
          ? FOOTER_FLIGHTS_PLANNING
          : FOOTER_FLIGHTS
        : 0;

  const mainHeight = `calc(100dvh - ${HEADER_HEIGHT}px - ${footerHeight}px)`;

  return (
    <AppShell
      header={{ height: HEADER_HEIGHT }}
      navbar={{ width: 280, breakpoint: 'sm' }}
      footer={showFooter ? { height: footerHeight } : undefined}
      padding={0}
      style={{ height: '100dvh' }}
    >
      <AppShell.Header>
        <Toolbar
          projectName={selectedProject?.name ?? null}
          drawMode={drawMode}
          onToggleDraw={() => {
            setDrawMode((value) => !value);
            if (!drawMode) resetFlightPlan();
          }}
          onSaveRoi={handleSaveRoi}
          onDeleteRoi={handleDeleteRoi}
          selectedRegionName={selectedRegion?.name ?? null}
          saving={regionMutations.create.isPending}
          showRoiTools={activePanel === 'sites'}
          onPlanMappingFlights={handlePlanMappingFlights}
          planningMappingFlights={flightMutations.planMapping.isPending}
          showFlightTools={activePanel === 'flights'}
          flightPlanMode={flightPlanMode}
          onToggleFlightPlan={() => {
            if (flightPlanMode) {
              resetFlightPlan();
              return;
            }
            setDrawMode(false);
            setFlightPlanMode(true);
            setDraftFlightPath(null);
          }}
        />
      </AppShell.Header>

      <Sidebar
        projects={projectsQuery.data ?? []}
        selectedProjectId={projectId}
        onSelectProject={(id) => {
          setSelectedProjectId(id);
          setSelectedRegionId(null);
          setSelectedFlightId(null);
          setSelectedStockpileId(null);
          setSelectedCaptureId(null);
          setCaptureFlightId(null);
        }}
        activePanel={activePanel}
        onPanelChange={(panel) => {
          setActivePanel(panel);
          if (panel !== 'sites') setDrawMode(false);
          if (panel !== 'flights') resetFlightPlan();
          if (panel !== 'history') setSelectedStockpileId(null);
          if (panel !== 'flights') setSelectedFlightId(null);
          if (panel !== 'captures') {
            setSelectedCaptureId(null);
            setCaptureFlightId(null);
          }
        }}
      />

      <AppShell.Main style={{ position: 'relative', height: mainHeight, padding: 0, overflow: 'hidden' }}>
        {loading && (
          <Stack
            align="center"
            justify="center"
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 2,
              background: 'rgba(255, 255, 255, 0.85)',
            }}
          >
            <Loader />
            <Text size="sm" c="dimmed">
              Loading project data...
            </Text>
          </Stack>
        )}
        {!loading && error && (
          <Stack align="center" justify="center" h="100%" p="md">
            <Text c="red" fw={600}>
              Failed to load data
            </Text>
            <Text size="sm" c="dimmed" ta="center">
              Ensure the backend is running at {import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}
            </Text>
          </Stack>
        )}
        {showMap && (
          <div className="map-panel">
            <ErrorBoundary title="Map failed to load">
              <SiteMap
                boundary={boundaryQuery.data ?? null}
                regions={regionsQuery.data ?? []}
                stockpiles={stockpilesQuery.data ?? []}
                flights={flightsQuery.data ?? []}
                drawMode={drawMode}
                flightPlanMode={flightPlanMode}
                selectedRegionId={selectedRegionId}
                selectedFlightId={selectedFlightId}
                onSelectRegion={setSelectedRegionId}
                onSelectFlight={setSelectedFlightId}
                onDraftGeometry={setDraftGeometry}
                onDraftFlightPath={setDraftFlightPath}
                showFlightPaths={activePanel === 'flights' || activePanel === 'captures'}
                captureMode={activePanel === 'captures'}
                flightCaptures={flightCapturesQuery.data ?? []}
                selectedCaptureId={selectedCaptureId}
                captureFlightId={captureFlightId}
                onSelectCapture={(captureId) => {
                  setSelectedCaptureId(captureId);
                  if (captureId !== null) {
                    const capture = flightCapturesQuery.data?.find((item) => item.id === captureId);
                    if (capture) {
                      setCaptureFlightId(capture.flight_id);
                    }
                  }
                }}
              />
            </ErrorBoundary>
          </div>
        )}
      </AppShell.Main>

      {showFooter && (
        <AppShell.Footer p={0} style={{ overflow: 'hidden' }}>
          {activePanel === 'flights' && (
            <Stack gap={0} h="100%">
              {flightPlanMode && (
                <FlightPlanForm
                  name={planName}
                  notes={planNotes}
                  onNameChange={setPlanName}
                  onNotesChange={setPlanNotes}
                  onSave={() => void handlePlanFlight()}
                  onCancel={resetFlightPlan}
                  canSavePlan={(draftFlightPath?.coordinates.length ?? 0) >= 2}
                  planning={flightMutations.create.isPending}
                />
              )}
              <ErrorBoundary title="Flight list failed to load">
                <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                  <FlightListPanel
                  flights={flightsQuery.data ?? []}
                  selectedFlightId={selectedFlightId}
                  onSelectFlight={setSelectedFlightId}
                  onCancelFlight={handleCancelFlight}
                />
                </div>
              </ErrorBoundary>
            </Stack>
          )}

          {activePanel === 'history' && (
            <ErrorBoundary title="History panel failed to load">
              <HistoryPanel
                stockpiles={stockpilesQuery.data ?? []}
                surveys={surveysQuery.data ?? []}
                selectedStockpileId={selectedStockpileId}
                onSelectStockpile={setSelectedStockpileId}
              />
            </ErrorBoundary>
          )}

          {activePanel === 'captures' && (
            <ErrorBoundary title="Captures panel failed to load">
              <CapturesPanel
                flights={flightsQuery.data ?? []}
                captures={flightCapturesQuery.data ?? []}
                selectedFlightId={captureFlightId}
                selectedCaptureId={selectedCaptureId}
                onSelectFlight={setCaptureFlightId}
                onSelectCapture={setSelectedCaptureId}
              />
            </ErrorBoundary>
          )}
        </AppShell.Footer>
      )}
    </AppShell>
  );
}
