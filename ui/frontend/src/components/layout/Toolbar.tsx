import { ActionIcon, Button, Group, Text, Title } from '@mantine/core';

type ToolbarProps = {
  projectName: string | null;
  drawMode: boolean;
  onToggleDraw: () => void;
  onSaveRoi: () => void;
  onDeleteRoi: () => void;
  selectedRegionName: string | null;
  saving: boolean;
};

export function Toolbar({
  projectName,
  drawMode,
  onToggleDraw,
  onSaveRoi,
  onDeleteRoi,
  selectedRegionName,
  saving,
}: ToolbarProps) {
  return (
    <Group justify="space-between" h="100%" px="md">
      <div>
        <Title order={4}>Construction Site Monitoring</Title>
        <Text size="sm" c="dimmed">
          {projectName ?? 'Select a project'}
        </Text>
      </div>

      <Group>
        {selectedRegionName && (
          <Text size="sm" c="dimmed">
            Selected ROI: {selectedRegionName}
          </Text>
        )}
        <Button variant={drawMode ? 'filled' : 'light'} onClick={onToggleDraw}>
          {drawMode ? 'Stop Drawing' : 'Draw ROI'}
        </Button>
        <Button variant="light" onClick={onSaveRoi} loading={saving} disabled={!drawMode}>
          Save ROI
        </Button>
        <ActionIcon variant="light" color="red" onClick={onDeleteRoi} disabled={!selectedRegionName}>
          ✕
        </ActionIcon>
      </Group>
    </Group>
  );
}
