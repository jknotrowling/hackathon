import { AppShell, Badge, Group, NavLink, Stack, Text, Title } from '@mantine/core';
import { ReactNode } from 'react';

import type { Project, Survey } from '../../types';

type SidebarProps = {
  projects: Project[];
  selectedProjectId: number | null;
  onSelectProject: (id: number) => void;
  surveys: Survey[];
  activePanel: 'sites' | 'flights' | 'history';
  onPanelChange: (panel: 'sites' | 'flights' | 'history') => void;
  children?: ReactNode;
};

export function Sidebar({
  projects,
  selectedProjectId,
  onSelectProject,
  surveys,
  activePanel,
  onPanelChange,
  children,
}: SidebarProps) {
  return (
    <AppShell.Navbar p="md" withBorder>
      <Stack gap="md" h="100%">
        <div>
          <Title order={5}>Projects</Title>
          <Stack gap={4} mt="xs">
            {projects.map((project) => (
              <NavLink
                key={project.id}
                label={project.name}
                description={project.location ?? undefined}
                active={selectedProjectId === project.id}
                onClick={() => onSelectProject(project.id)}
              />
            ))}
          </Stack>
        </div>

        <div>
          <Title order={5}>Navigation</Title>
          <Stack gap={4} mt="xs">
            <NavLink
              label="Sites"
              description="Boundaries & ROIs"
              active={activePanel === 'sites'}
              onClick={() => onPanelChange('sites')}
            />
            <NavLink
              label="Flights"
              description="Drone survey paths"
              active={activePanel === 'flights'}
              onClick={() => onPanelChange('flights')}
            />
            <NavLink
              label="History"
              description="Survey timeline"
              active={activePanel === 'history'}
              onClick={() => onPanelChange('history')}
            />
          </Stack>
        </div>

        {activePanel === 'flights' && (
          <Stack gap="xs">
            <Text size="sm" fw={600}>
              Recent flights
            </Text>
            {surveys.slice(0, 5).map((survey) => (
              <Group key={survey.id} justify="space-between">
                <Text size="xs">{new Date(survey.timestamp).toLocaleDateString()}</Text>
                <Badge size="xs" variant="light">
                  {survey.data_reference ?? `Survey ${survey.id}`}
                </Badge>
              </Group>
            ))}
          </Stack>
        )}

        {children}
      </Stack>
    </AppShell.Navbar>
  );
}
