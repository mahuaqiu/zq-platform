<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import * as echarts from 'echarts';
import type { MetricCardData } from '../types';

const props = defineProps<{
  data: MetricCardData;
}>();

const miniChartRef = ref<HTMLDivElement>();
let miniChart: echarts.ECharts | null = null;

function initMiniChart() {
  if (!miniChartRef.value) return;
  miniChart = echarts.init(miniChartRef.value);
  miniChart.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: {
      type: 'category',
      show: false,
      data: props.data.historyData.map((_, i) => i),
    },
    yAxis: { type: 'value', show: false },
    series: [
      {
        type: 'line',
        data: props.data.historyData,
        lineStyle: { color: props.data.color || '#409eff', width: 1.5 },
        smooth: true,
        symbol: 'none',
      },
    ],
  });
}

watch(
  () => props.data,
  () => {
    if (miniChart) {
      miniChart.setOption({
        series: [
          {
            data: props.data.historyData,
            lineStyle: { color: props.data.color || '#409eff', width: 1.5 },
          },
        ],
      });
    }
  },
  { deep: true },
);

onMounted(() => {
  initMiniChart();
});
</script>

<template>
  <div class="metric-card">
    <div class="metric-name">{{ data.name }}</div>
    <div class="metric-value" :style="{ color: data.color || '#409eff' }">
      {{ data.value.toFixed(1) }} {{ data.unit }}
    </div>
    <div ref="miniChartRef" class="mini-chart"></div>
  </div>
</template>

<style scoped>
.metric-card {
  background: #f8f9fa;
  border-radius: 4px;
  padding: 8px;
}
.metric-name {
  font-size: 10px;
  color: #999;
}
.metric-value {
  font-size: 14px;
  font-weight: 600;
  margin: 4px 0;
}
.mini-chart {
  height: 20px;
  width: 100%;
}
</style>