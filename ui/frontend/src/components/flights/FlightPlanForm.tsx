import { Button, Group, Paper, Stack, Text, TextInput, Textarea } from '@mantine/core';

type FlightPlanFormProps = {
  name: string;
  notes: string;
  onNameChange: (value: string) => void;
  onNotesChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  canSavePlan: boolean;
  planning: boolean;
};

export function FlightPlanForm({
  name,
  notes,
  onNameChange,
  onNotesChange,
  onSave,
  onCancel,
  canSavePlan,
  planning,
}: FlightPlanFormProps) {
  const canSubmit = Boolean(name.trim() && canSavePlan);

  return (
    <Paper className="flight-plan-form" p="md" radius={0} withBorder>
      <Group align="flex-end" wrap="wrap" gap="md">
        <TextInput
          label="Flight name"
          placeholder="August site scan"
          value={name}
          onChange={(event) => onNameChange(event.currentTarget.value)}
          style={{ flex: '1 1 180px', minWidth: 160 }}
        />
        <Textarea
          label="Notes"
          placeholder="Optional"
          value={notes}
          onChange={(event) => onNotesChange(event.currentTarget.value)}
          autosize
          minRows={1}
          maxRows={2}
          style={{ flex: '2 1 240px', minWidth: 200 }}
        />
        <Stack gap={6} style={{ flex: '0 0 auto' }}>
          <Text size="xs" c={canSavePlan ? 'dimmed' : 'orange.8'}>
            {canSavePlan ? 'Flight path drawn on map' : 'Draw at least 2 points on the map'}
          </Text>
          <Group gap="sm">
            <Button variant="default" onClick={onCancel}>
              Cancel
            </Button>
            <Button onClick={onSave} loading={planning} disabled={!canSubmit}>
              Save planned flight
            </Button>
          </Group>
        </Stack>
      </Group>
    </Paper>
  );
}
