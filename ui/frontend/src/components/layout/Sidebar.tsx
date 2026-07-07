import { AppShell, NavLink, Stack, Title } from '@mantine/core';

import type { Project } from '../../types';

type SidebarProps = {
  projects: Project[];
  selectedProjectId: number | null;
  onSelectProject: (id: number) => void;
  activePanel: 'sites' | 'flights' | 'history';
  onPanelChange: (panel: 'sites' | 'flights' | 'history') => void;
};

export function Sidebar({
  projects,
  selectedProjectId,
  onSelectProject,
  activePanel,
  onPanelChange,
}: SidebarProps) {
  return (
    <AppShell.Navbar p="md" withBorder>
      <Stack gap="md">
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
              description="Past & upcoming flights"
              active={activePanel === 'flights'}
              onClick={() => onPanelChange('flights')}
            />
            <NavLink
              label="History"
              description="Stockpile measurements"
              active={activePanel === 'history'}
              onClick={() => onPanelChange('history')}
            />
          </Stack>
        </div>
      </Stack>
    </AppShell.Navbar>
  );
}
