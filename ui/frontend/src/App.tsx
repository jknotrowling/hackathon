import { AppShell, Loader, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useMemo, useState } from 'react';

import { HistoryChart } from './components/charts/HistoryChart';
import { StockpileTable } from './components/charts/StockpileTable';
import { Sidebar } from './components/layout/Sidebar';
import { Toolbar } from './components/layout/Toolbar';
import { SiteMap } from './components/map/SiteMap';
import {
  useBoundary,
  useProjects,
  useRegionMutations,
  useRegions,
  useStockpiles,
  useSurveys,
} from './hooks/useProjectData';
import type { GeoJSONPolygon } from './types';

export function App() {
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [activePanel, setActivePanel] = useState<'sites' | 'flights' | 'history'>('sites');
  const [drawMode, setDrawMode] = useState(false);
  const [selectedRegionId, setSelectedRegionId] = useState<number | null>(null);
  const [selectedStockpileId, setSelectedStockpileId] = useState<number | null>(null);
  const [draftGeometry, setDraftGeometry] = useState<GeoJSONPolygon | null>(null);

  const projectsQuery = useProjects();
  const projectId = selectedProjectId ?? projectsQuery.data?.[0]?.id ?? null;

  const boundaryQuery = useBoundary(projectId);
  const regionsQuery = useRegions(projectId);
  const stockpilesQuery = useStockpiles(projectId);
  const surveysQuery = useSurveys(projectId);
  const regionMutations = useRegionMutations(projectId);

  const selectedProject = useMemo(
    () => projectsQuery.data?.find((project) => project.id === projectId) ?? null,
    [projectsQuery.data, projectId],
  );

  const selectedRegion = regionsQuery.data?.find((region) => region.id === selectedRegionId) ?? null;

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
      await regionMutations.create.mutateAsync({
        name,
        geometry: draftGeometry,
      });
      setDraftGeometry(null);
      setDrawMode(false);
      notifications.show({
        color: 'green',
        title: 'ROI saved',
        message: `${name} was stored successfully.`,
      });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to save ROI',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const handleDeleteRoi = async () => {
    if (!selectedRegionId) {
      return;
    }

    try {
      await regionMutations.remove.mutateAsync(selectedRegionId);
      setSelectedRegionId(null);
      notifications.show({
        color: 'green',
        title: 'ROI deleted',
        message: 'The selected region was removed.',
      });
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to delete ROI',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  const loading =
    projectsQuery.isLoading ||
    boundaryQuery.isLoading ||
    regionsQuery.isLoading ||
    stockpilesQuery.isLoading ||
    surveysQuery.isLoading;

  const error =
    projectsQuery.error ??
    boundaryQuery.error ??
    regionsQuery.error ??
    stockpilesQuery.error ??
    surveysQuery.error;

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{ width: 280, breakpoint: 'sm' }}
      footer={{ height: 360 }}
      padding={0}
    >
      <AppShell.Header>
        <Toolbar
          projectName={selectedProject?.name ?? null}
          drawMode={drawMode}
          onToggleDraw={() => setDrawMode((value) => !value)}
          onSaveRoi={handleSaveRoi}
          onDeleteRoi={handleDeleteRoi}
          selectedRegionName={selectedRegion?.name ?? null}
          saving={regionMutations.create.isPending}
        />
      </AppShell.Header>

      <Sidebar
        projects={projectsQuery.data ?? []}
        selectedProjectId={projectId}
        onSelectProject={(id) => {
          setSelectedProjectId(id);
          setSelectedRegionId(null);
          setSelectedStockpileId(null);
        }}
        surveys={surveysQuery.data ?? []}
        activePanel={activePanel}
        onPanelChange={setActivePanel}
      />

      <AppShell.Main>
        {loading && (
          <Stack align="center" justify="center" h="100%">
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
        {!loading && !error && (
          <SiteMap
            boundary={boundaryQuery.data ?? null}
            regions={regionsQuery.data ?? []}
            stockpiles={stockpilesQuery.data ?? []}
            surveys={surveysQuery.data ?? []}
            drawMode={drawMode}
            selectedRegionId={selectedRegionId}
            onSelectRegion={setSelectedRegionId}
            onDraftGeometry={setDraftGeometry}
            showFlightPaths={activePanel === 'flights'}
          />
        )}
      </AppShell.Main>

      <AppShell.Footer>
        <StockpileTable
          stockpiles={stockpilesQuery.data ?? []}
          selectedStockpileId={selectedStockpileId}
          onSelectStockpile={setSelectedStockpileId}
        />
        <HistoryChart
          stockpiles={stockpilesQuery.data ?? []}
          surveys={surveysQuery.data ?? []}
          selectedStockpileId={selectedStockpileId}
        />
      </AppShell.Footer>
    </AppShell>
  );
}
