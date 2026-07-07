import { Group, Paper, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useMemo } from 'react';

import type { Flight, FlightCapture } from '../../types';
import { resolveImageUrl } from '../../utils/assets';

type CapturesPanelProps = {
  flights: Flight[];
  captures: FlightCapture[];
  selectedFlightId: number | null;
  selectedCaptureId: number | null;
  onSelectFlight: (id: number | null) => void;
  onSelectCapture: (id: number | null) => void;
};

export function CapturesPanel({
  flights,
  captures,
  selectedFlightId,
  selectedCaptureId,
  onSelectFlight,
  onSelectCapture,
}: CapturesPanelProps) {
  const flightsWithCaptures = useMemo(() => {
    const flightIds = new Set(captures.map((capture) => capture.flight_id));
    return flights.filter((flight) => flightIds.has(flight.id));
  }, [captures, flights]);

  const flightCaptures = useMemo(() => {
    if (selectedFlightId === null) {
      return [];
    }
    return captures
      .filter((capture) => capture.flight_id === selectedFlightId)
      .sort((a, b) => a.waypoint_index - b.waypoint_index);
  }, [captures, selectedFlightId]);

  const selectedCapture = flightCaptures.find((capture) => capture.id === selectedCaptureId) ?? null;

  return (
    <div className="captures-panel">
      <Group align="stretch" gap={0} h="100%" wrap="nowrap">
        <Paper className="captures-panel__flights" radius={0} p="md" withBorder>
          <Title order={6} mb="xs">
            Flights
          </Title>
          <ScrollArea className="captures-panel__scroll" type="auto" offsetScrollbars>
            <Stack gap="xs">
              {flightsWithCaptures.length === 0 && (
                <Text size="sm" c="dimmed">
                  No captured flights yet.
                </Text>
              )}
              {flightsWithCaptures.map((flight) => (
                <Paper
                  key={flight.id}
                  withBorder
                  p="sm"
                  radius="sm"
                  style={{
                    cursor: 'pointer',
                    borderColor:
                      selectedFlightId === flight.id ? 'var(--mantine-color-blue-5)' : undefined,
                    background:
                      selectedFlightId === flight.id ? 'var(--mantine-color-blue-0)' : undefined,
                  }}
                  onClick={() => {
                    onSelectFlight(flight.id);
                    onSelectCapture(null);
                  }}
                >
                  <Text size="sm" fw={600}>
                    {flight.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {captures.filter((capture) => capture.flight_id === flight.id).length} captures
                  </Text>
                </Paper>
              ))}
            </Stack>
          </ScrollArea>
        </Paper>

        <Paper className="captures-panel__points" radius={0} p="md" withBorder>
          <Title order={6} mb="xs">
            Capture points
          </Title>
          <ScrollArea className="captures-panel__scroll" type="auto" offsetScrollbars>
            <Stack gap="xs">
              {!selectedFlightId && (
                <Text size="sm" c="dimmed">
                  Select a flight to view capture points.
                </Text>
              )}
              {selectedFlightId !== null && flightCaptures.length === 0 && (
                <Text size="sm" c="dimmed">
                  No captures for this flight.
                </Text>
              )}
              {flightCaptures.map((capture) => (
                <Paper
                  key={capture.id}
                  withBorder
                  p="sm"
                  radius="sm"
                  style={{
                    cursor: 'pointer',
                    borderColor:
                      selectedCaptureId === capture.id ? 'var(--mantine-color-orange-5)' : undefined,
                    background:
                      selectedCaptureId === capture.id ? 'var(--mantine-color-orange-0)' : undefined,
                  }}
                  onClick={() => onSelectCapture(capture.id)}
                >
                  <Text size="sm" fw={600}>
                    Point {capture.waypoint_index + 1}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {capture.location.coordinates[1].toFixed(5)}, {capture.location.coordinates[0].toFixed(5)}
                  </Text>
                </Paper>
              ))}
            </Stack>
          </ScrollArea>
        </Paper>

        <Paper className="captures-panel__preview" radius={0} p="md" withBorder>
          <Title order={6} mb="xs">
            Image preview
          </Title>
          {selectedCapture ? (
            <Stack gap="sm" className="captures-panel__preview-body">
              <Text size="sm" c="dimmed">
                Flight point {selectedCapture.waypoint_index + 1}
              </Text>
              <div className="captures-panel__image-wrap">
                <img
                  src={resolveImageUrl(selectedCapture.image_url)}
                  alt={`Capture at point ${selectedCapture.waypoint_index + 1}`}
                  className="captures-panel__image"
                />
              </div>
            </Stack>
          ) : (
            <Stack justify="center" h="100%">
              <Text size="sm" c="dimmed">
                Select a capture point on the map or in the list to view the image.
              </Text>
            </Stack>
          )}
        </Paper>
      </Group>
    </div>
  );
}
