<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries } from '../types';
import type { CompareTag } from '../types';

const props = defineProps<{
  series: ChartSeries[];
  tags: CompareTag[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: 'hover-change', data: { time: number; values: Record<string, number> }): void;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const initChart = () => {
  if (!chartRef.value) return;
  chart = echarts.init(chartRef.value);

  // Build markArea data from tags (using relative time as value)
  const peakAreas = props.tags
    .filter(t => t.type === 'peak')
    .map(t => {
      const start = new Date(t.start_time).getTime();
      const end = new Date(t.end_time).getTime();
      return [{ xAxis: start }, { xAxis: end }] as Array<{ xAxis: number }>;
    });

  const stableAreas = props.tags
    .filter(t => t.type === 'stable')
    .map(t => {
      const start = new Date(t.start_time).getTime();
      const end = new Date(t.end_time).getTime();
      return [{ xAxis: start }, { xAxis: end }] as Array<{ xAxis: number }>;
    });

  const seriesData = props.series.map((s, index) => ({
    name: s.name,
    type: 'line',
    data: s.data.map(d => [d.time, d.value]),
    lineStyle: { color: s.color },
    itemStyle: { color: s.color },
    markArea: index === 0 ? {
      silent: true,
      itemStyle: {
        color: 'rgba(245, 108, 108, 0.15)', // red for peak
      },
      data: peakAreas,
    } : undefined,
  })) as echarts.SeriesOption[];

  // Add stable areas as separate series if needed
  if (stableAreas.length > 0) {
    seriesData.push({
      type: 'line',
      markArea: {
        silent: true,
        itemStyle: {
          color: 'rgba(103, 194, 58, 0.15)', // green for stable
        },
        data: stableAreas,
      },
      data: [],
    } as echarts.SeriesOption);
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!Array.isArray(params)) params = [params];
        const time = params[0]?.data?.[0] ?? params[0]?.value?.[0];
        let result = `时间: ${time}秒<br/>`;
        params.forEach((p: any) => {
          if (p.seriesName) {
            result += `${p.seriesName}: ${p.data?.[1] ?? p.value?.[1] ?? '-'}<br/>`;
          }
        });
        return result;
      },
    },
    grid: {
      left: 60,
      right: 40,
      bottom: 80,
      top: 40,
    },
    xAxis: {
      type: 'value',
      name: '相对时间(秒)',
      nameLocation: 'middle',
      nameGap: 30,
    },
    yAxis: {
      type: 'value',
    },
    dataZoom: [
      {
        type: 'slider',
        bottom: 20,
        height: 20,
      },
      {
        type: 'inside',
      },
    ],
    series: seriesData,
  };

  chart.setOption(option);

  // Hover event
  chart.on('axisSelect', (params: unknown) => {
    const p = params as { dataTime?: number };
    if (p.dataTime) {
      const values: Record<string, number> = {};
      props.series.forEach(s => {
        const point = s.data.find(d => d.time === p.dataTime);
        if (point) values[s.name] = point.value;
      });
      emit('hover-change', { time: p.dataTime, values });
    }
  });
};

watch([() => props.series, () => props.tags], () => {
  if (chart) initChart();
}, { deep: true });

onMounted(() => {
  initChart();
  window.addEventListener('resize', () => chart?.resize());
});

onUnmounted(() => {
  chart?.dispose();
  window.removeEventListener('resize', () => chart?.resize());
});
</script>

<template>
  <div class="compare-chart-panel" v-loading="loading">
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<style scoped>
.compare-chart-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.chart-container {
  height: 300px;
}
</style>