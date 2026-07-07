import { ActionIcon, Button, Group, Text, Title } from '@mantine/core';

type ToolbarProps = {
  projectName: string | null;
  drawMode: boolean;
  onToggleDraw: () => void;
  onSaveRoi: () => void;
  onDeleteRoi: () => void;
  selectedRegionName: string | null;
  saving: boolean;
  showRoiTools?: boolean;
  showFlightTools?: boolean;
  flightPlanMode?: boolean;
  onToggleFlightPlan?: () => void;
  onPlanMappingFlights?: () => void;
  planningMappingFlights?: boolean;
};

export function Toolbar({
  projectName,
  drawMode,
  onToggleDraw,
  onSaveRoi,
  onDeleteRoi,
  selectedRegionName,
  saving,
  showRoiTools = false,
  showFlightTools = false,
  flightPlanMode = false,
  onToggleFlightPlan,
  onPlanMappingFlights,
  planningMappingFlights = false,
}: ToolbarProps) {
  return (
    <Group justify="space-between" h="100%" px="md" wrap="nowrap">
      <div style={{ minWidth: 0 }}>
        <Title order={4}>Construction Site Monitoring</Title>
        <Text size="sm" c="dimmed" truncate>
          {projectName ?? 'Select a project'}
        </Text>
      </div>

      <Group gap="sm" wrap="nowrap">
        {showRoiTools && selectedRegionName && (
          <Text size="sm" c="dimmed">
            ROI: {selectedRegionName}
          </Text>
        )}
        {showRoiTools && selectedRegionName && onPlanMappingFlights && (
          <Button variant="light" onClick={onPlanMappingFlights} loading={planningMappingFlights}>
            Plan mapping flights
          </Button>
        )}
        {showRoiTools && (
          <>
            <Button variant={drawMode ? 'filled' : 'light'} onClick={onToggleDraw}>
              {drawMode ? 'Stop drawing' : 'Draw ROI'}
            </Button>
            <Button variant="light" onClick={onSaveRoi} loading={saving} disabled={!drawMode}>
              Save ROI
            </Button>
            <ActionIcon variant="light" color="red" onClick={onDeleteRoi} disabled={!selectedRegionName}>
              ✕
            </ActionIcon>
          </>
        )}
        {showFlightTools && onToggleFlightPlan && (
          <Button variant={flightPlanMode ? 'filled' : 'light'} onClick={onToggleFlightPlan}>
            {flightPlanMode ? 'Cancel flight planning' : 'Plan flight'}
          </Button>
        )}
      </Group>
    </Group>
  );
}
