<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries } from '../types';

// 定义 Props 类型
interface ChartTag {
  name: string;
  start: number;
  duration: number;
  type: string;
  color: string;
}

interface Props {
  title: string;
  series: ChartSeries[];
  showTop10?: boolean;
  height?: number;
  timeRange?: [number, number];
  tags?: ChartTag[];
}

const props = defineProps<Props>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

const chartHeight = computed(() => props.height || 200);

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);
  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  const xAxisData = props.series[0]?.data.map((d) => d.time) || [];

  const seriesConfig = props.series.map((s) => ({
    name: s.name,
    type: 'line',
    data: s.data.map((d) => d.value),
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    smooth: true,
    symbol: 'none',
  }));

  // 标签区间标记
  const markAreas: any[] = [];
  if (props.tags) {
    props.tags.forEach((tag) => {
      markAreas.push([
        {
          xAxis: tag.start,
          itemStyle: {
            color:
              tag.type === 'peak'
                ? 'rgba(103,194,126,0.15)'
                : 'rgba(245,108,108,0.15)',
          },
        },
        { xAxis: tag.start + tag.duration },
      ]);
    });
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const time = params[0].axisValue;
        let html = `<div>相对时间: ${time}秒</div>`;
        params.forEach((p: any) => {
          html += `<div>${p.seriesName}: ${p.value?.toFixed(1)}%</div>`;
        });
        return html;
      },
    },
    legend: {
      show: props.series.length > 1,
      top: 0,
      right: 10,
      data: props.series.map((s) => s.name),
    },
    grid: {
      left: 50,
      right: 20,
      top: 30,
      bottom: 30,
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: { formatter: (v: number) => `${v}s` },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%' },
    },
    series: seriesConfig,
  };

  chartInstance.setOption(option);
}

watch(() => props.series, updateChart, { deep: true });
watch(() => props.timeRange, updateChart);

onMounted(() => {
  initChart();
});
</script>

<template>
  <div class="chart-panel">
    <div class="chart-title">{{ title }}</div>
    <div
      ref="chartRef"
      class="chart-container"
      :style="{ height: chartHeight + 'px' }"
    ></div>
  </div>
</template>

<style scoped>
.chart-panel {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.chart-container {
  width: 100%;
}
</style>