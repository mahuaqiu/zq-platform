<template>
  <div class="metric-card">
    <div class="metric-name">{{ data.name }}</div>
    <div class="metric-value" :style="{ color: data.color || '#409eff' }">
      {{ formatValue(data.value, data.unit) }} {{ data.unit }}
    </div>
    <div ref="miniChartRef" class="mini-chart"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import * as echarts from 'echarts';
import type { MetricCardData } from '../types';

const props = defineProps<{
  data: MetricCardData;
}>();

const miniChartRef = ref<HTMLDivElement>();
let miniChart: echarts.ECharts | null = null;

// 格式化数值
function formatValue(value: number, unit: string): string {
  if (unit === '' || unit === 'W') {
    // 整数显示
    return Math.round(value).toString();
  }
  // 其他保留一位小数
  return value.toFixed(1);
}

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
  line-height: 1.2;
}
.mini-chart {
  height: 20px;
  width: 100%;
}
</style>