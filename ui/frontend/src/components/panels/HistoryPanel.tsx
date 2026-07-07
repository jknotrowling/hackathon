import { Group, Paper, ScrollArea, Title } from '@mantine/core';

import { HistoryChart } from '../charts/HistoryChart';
import { StockpileTable } from '../charts/StockpileTable';
import type { Stockpile, Survey } from '../../types';

type HistoryPanelProps = {
  stockpiles: Stockpile[];
  surveys: Survey[];
  selectedStockpileId: number | null;
  onSelectStockpile: (id: number | null) => void;
};

export function HistoryPanel({
  stockpiles,
  surveys,
  selectedStockpileId,
  onSelectStockpile,
}: HistoryPanelProps) {
  return (
    <div className="history-panel">
      <Group align="stretch" gap={0} wrap="nowrap" style={{ height: '100%' }}>
        <Paper className="history-panel__table" p="md" radius={0} withBorder>
          <Title order={6} mb="sm">
            Stockpiles
          </Title>
          <ScrollArea className="history-panel__scroll" type="auto" offsetScrollbars>
            <StockpileTable
              stockpiles={stockpiles}
              selectedStockpileId={selectedStockpileId}
              onSelectStockpile={onSelectStockpile}
              embedded
            />
          </ScrollArea>
        </Paper>
        <Paper className="history-panel__chart" p="md" radius={0} withBorder>
          <Title order={6} mb="sm">
            Volume history
          </Title>
          <div className="history-panel__chart-body">
            <HistoryChart
            stockpiles={stockpiles}
            surveys={surveys}
            selectedStockpileId={selectedStockpileId}
            embedded
          />
          </div>
        </Paper>
      </Group>
    </div>
  );
}
