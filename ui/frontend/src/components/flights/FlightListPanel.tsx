import { ActionIcon, Badge, Group, Paper, ScrollArea, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useMemo } from 'react';

import type { Flight } from '../../types';

type FlightListPanelProps = {
  flights: Flight[];
  selectedFlightId: number | null;
  onSelectFlight: (id: number | null) => void;
  onCancelFlight: (id: number) => void;
};

function statusColor(status: Flight['status']) {
  if (status === 'completed') return 'green';
  if (status === 'cancelled') return 'gray';
  return 'blue';
}

export function FlightListPanel({
  flights,
  selectedFlightId,
  onSelectFlight,
  onCancelFlight,
}: FlightListPanelProps) {
  const { upcoming, completed } = useMemo(() => {
    const upcomingFlights = flights.filter((flight) => flight.status === 'planned');
    const completedFlights = flights.filter((flight) => flight.status === 'completed');
    return {
      upcoming: upcomingFlights.sort((a, b) => a.name.localeCompare(b.name)),
      completed: completedFlights.sort((a, b) => a.name.localeCompare(b.name)),
    };
  }, [flights]);

  const renderFlight = (flight: Flight) => (
    <Paper
      key={flight.id}
      withBorder
      p="sm"
      radius="sm"
      style={{
        cursor: 'pointer',
        borderColor: selectedFlightId === flight.id ? 'var(--mantine-color-blue-5)' : undefined,
        background: selectedFlightId === flight.id ? 'var(--mantine-color-blue-0)' : undefined,
      }}
      onClick={() => onSelectFlight(selectedFlightId === flight.id ? null : flight.id)}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Text size="sm" fw={600} truncate>
            {flight.name}
          </Text>
          {flight.notes && (
            <Text size="xs" c="dimmed" lineClamp={2}>
              {flight.notes}
            </Text>
          )}
        </Stack>
        <Group gap={4} wrap="nowrap">
          <Badge size="sm" color={statusColor(flight.status)} variant="light">
            {flight.status}
          </Badge>
          {flight.status === 'planned' && (
            <ActionIcon
              size="sm"
              variant="subtle"
              color="red"
              aria-label="Cancel flight"
              onClick={(event) => {
                event.stopPropagation();
                void onCancelFlight(flight.id);
              }}
            >
              ✕
            </ActionIcon>
          )}
        </Group>
      </Group>
    </Paper>
  );

  return (
    <div className="flight-list-panel">
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md" p="md" className="flight-list-grid">
        <Stack gap="xs" className="flight-list-column">
          <Title order={6}>Planned ({upcoming.length})</Title>
          <ScrollArea className="flight-list-scroll" type="auto" offsetScrollbars>
            <Stack gap="xs" pb="xs">
              {upcoming.length === 0 && (
                <Text size="sm" c="dimmed">
                  No flights planned.
                </Text>
              )}
              {upcoming.map(renderFlight)}
            </Stack>
          </ScrollArea>
        </Stack>

        <Stack gap="xs" className="flight-list-column">
          <Title order={6}>Completed ({completed.length})</Title>
          <ScrollArea className="flight-list-scroll" type="auto" offsetScrollbars>
            <Stack gap="xs" pb="xs">
              {completed.length === 0 && (
                <Text size="sm" c="dimmed">
                  No completed flights yet.
                </Text>
              )}
              {completed.map(renderFlight)}
            </Stack>
          </ScrollArea>
        </Stack>
      </SimpleGrid>
    </div>
  );
}
