import { Badge, Table, Text } from '@mantine/core';

import type { Stockpile } from '../../types';

type StockpileTableProps = {
  stockpiles: Stockpile[];
  selectedStockpileId: number | null;
  onSelectStockpile: (id: number | null) => void;
  embedded?: boolean;
};

export function StockpileTable({
  stockpiles,
  selectedStockpileId,
  onSelectStockpile,
  embedded = false,
}: StockpileTableProps) {
  const content = (
    <>
      <Table highlightOnHover striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Material</Table.Th>
            <Table.Th>Volume (m³)</Table.Th>
            <Table.Th>Last scan</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {stockpiles.map((stockpile) => (
            <Table.Tr
              key={stockpile.id}
              onClick={() =>
                onSelectStockpile(selectedStockpileId === stockpile.id ? null : stockpile.id)
              }
              style={{
                cursor: 'pointer',
                background:
                  selectedStockpileId === stockpile.id ? 'var(--mantine-color-blue-0)' : undefined,
              }}
            >
              <Table.Td>{stockpile.name}</Table.Td>
              <Table.Td>
                <Badge variant="light">{stockpile.material}</Badge>
              </Table.Td>
              <Table.Td>{stockpile.volume.toLocaleString()}</Table.Td>
              <Table.Td>{stockpile.last_scan ?? '—'}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {stockpiles.length === 0 && (
        <Text size="sm" c="dimmed" mt="sm">
          No stockpiles available for this project.
        </Text>
      )}
    </>
  );

  if (embedded) {
    return content;
  }

  return content;
}
