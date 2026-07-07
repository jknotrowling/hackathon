import ReactECharts from 'echarts-for-react';
import { Paper, Title } from '@mantine/core';
import { useMemo } from 'react';

import type { Stockpile, Survey } from '../../types';

type HistoryChartProps = {
  stockpiles: Stockpile[];
  surveys: Survey[];
  selectedStockpileId: number | null;
};

export function HistoryChart({ stockpiles, surveys, selectedStockpileId }: HistoryChartProps) {
  const option = useMemo(() => {
    const sortedSurveys = [...surveys].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    );
    const dates = sortedSurveys.map((survey) =>
      new Date(survey.timestamp).toLocaleDateString(),
    );

    const series = stockpiles
      .filter((stockpile) =>
        selectedStockpileId ? stockpile.id === selectedStockpileId : true,
      )
      .map((stockpile) => ({
        name: stockpile.name,
        type: 'line' as const,
        smooth: true,
        data: sortedSurveys.map((survey) => {
          const measurement = survey.stockpile_volumes.find(
            (item) => item.stockpile_id === stockpile.id,
          );
          return measurement?.volume ?? null;
        }),
      }));

    return {
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 48, right: 24, bottom: 32, top: 48 },
      xAxis: { type: 'category', data: dates },
      yAxis: {
        type: 'value',
        name: 'Volume (m³)',
      },
      series,
    };
  }, [stockpiles, surveys, selectedStockpileId]);

  return (
    <Paper p="md" radius={0} withBorder>
      <Title order={5} mb="sm">
        Stockpile History
      </Title>
      <ReactECharts option={option} style={{ height: 280 }} />
    </Paper>
  );
}
