<template>
  <div class="metric-card">
    <div class="metric-name">{{ data.name }}</div>
    <div class="metric-value" :style="{ color: data.color || '#409eff' }">
      {{ formatValue(data.value, data.name) }}
    </div>
    <div ref="miniChartRef" class="mini-chart"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { MetricCardData } from '../types';

const props = defineProps<{
  data: MetricCardData;
}>();

const miniChartRef = ref<HTMLDivElement>();
let miniChart: echarts.ECharts | null = null;

// 智能格式化数值，根据指标名称自动选择单位
function formatValue(value: number, name: string): string {
  // 网络速度：上报单位是 KB/s，直接显示 KB/s
  if (name === '上传速度' || name === '下载速度') {
    return `${Math.round(value)} KB/s`;
  }

  // 温度：整数显示
  if (name === 'CPU温度') {
    return `${Math.round(value)} °C`;
  }

  // 功耗、进程句柄：整数显示
  if (name === '功耗' || name === '进程句柄') {
    return `${Math.round(value)}`;
  }

  // CPU速度：保留一位小数
  if (name === 'CPU速度') {
    return `${value.toFixed(1)} GHz`;
  }

  // 默认：保留一位小数
  return value.toFixed(1);
}

function initMiniChart() {
  if (!miniChartRef.value) return;
  miniChart = echarts.init(miniChartRef.value);
  updateChart();
}

function updateChart() {
  if (!miniChart) return;

  const chartData = props.data.historyData || [];
  if (chartData.length === 0) return;

  miniChart.setOption({
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: {
      type: 'category',
      show: false,
      data: chartData.map((_, i) => i), // 根据数据长度动态生成X轴
    },
    yAxis: { type: 'value', show: false },
    series: [
      {
        type: 'line',
        data: chartData,
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
    updateChart();
  },
  { deep: true },
);

onMounted(() => {
  initMiniChart();
});

onUnmounted(() => {
  if (miniChart) {
    miniChart.dispose();
    miniChart = null;
  }
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