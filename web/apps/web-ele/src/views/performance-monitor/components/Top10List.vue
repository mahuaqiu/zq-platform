<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import type { PerformanceData } from '../types';

interface Top10ItemInternal {
  name: string;
  value: number;
  trendData: number[]; // 迷你趋势线数据
}

const props = defineProps<{
  data: PerformanceData[];
  clickedTime?: number;
  type?: 'cpu' | 'gpu'; // 区分CPU TOP10和GPU TOP10
}>();

const currentTime = ref<number>(0);
const top3 = ref<Top10ItemInternal[]>([]);
const top4to10 = ref<Top10ItemInternal[]>([]);
const miniChartRefs = ref<Map<string, HTMLDivElement>>(new Map());
const miniCharts = ref<Map<string, echarts.ECharts>>(new Map());

// 监听点击时刻变化
watch(
  () => props.clickedTime,
  (time) => {
    if (time !== undefined) {
      currentTime.value = time;
      updateTop10Data(time);
    }
  },
  { immediate: true }
);

function updateTop10Data(time: number) {
  // 找到最接近的数据
  const closestData =
    props.data.find((d) => d.relative_time === time) ||
    props.data.reduce(
      (prev, curr) =>
        Math.abs(curr.relative_time - time) < Math.abs(prev.relative_time - time) ? curr : prev,
      props.data[0]
    );

  const top10List = props.type === 'gpu' ? closestData?.top10_gpu : closestData?.top10_cpu;
  const valueKey = props.type === 'gpu' ? 'gpu' : 'cpu';

  if (top10List) {
    // 计算每个进程的历史趋势数据
    const items = top10List.slice(0, 10).map((p) => {
      const processName = p.name;
      // 从历史数据中提取该进程的趋势
      const trendData = props.data.map((d) => {
        const topList = props.type === 'gpu' ? d.top10_gpu : d.top10_cpu;
        const process = topList?.find((proc) => proc.name === processName);
        return process?.[valueKey] || 0;
      });

      return {
        name: processName,
        value: p[valueKey] || 0,
        trendData,
      };
    });

    top3.value = items.slice(0, 3);
    top4to10.value = items.slice(3, 10);

    // 渲染迷你趋势线
    nextTick(() => {
      renderMiniCharts();
    });
  }
}

function renderMiniCharts() {
  top3.value.forEach((item) => {
    const chartDiv = miniChartRefs.value.get(item.name);
    if (!chartDiv) return;

    // 清理已有实例
    const existingChart = miniCharts.value.get(item.name);
    if (existingChart) {
      existingChart.dispose();
    }

    // 创建迷你趋势图
    const chart = echarts.init(chartDiv);
    chart.setOption({
      grid: { left: 0, right: 0, top: 0, bottom: 0 },
      xAxis: { type: 'category', show: false, data: item.trendData.map((_, i) => i) },
      yAxis: { type: 'value', show: false },
      series: [{
        type: 'line',
        data: item.trendData,
        lineStyle: { color: '#409eff', width: 1.5 },
        smooth: true,
        symbol: 'none',
      }],
    });

    miniCharts.value.set(item.name, chart);
  });
}

function getItemColor(idx: number): string {
  const colors = ['#409eff', '#67c23a', '#e6a23c'];
  return colors[idx] || '#909399';
}

onMounted(() => {
  window.addEventListener('resize', () => {
    miniCharts.value.forEach(chart => chart.resize());
  });
});
</script>

<template>
  <div class="top10-list">
    <div class="top10-header">
      <span class="top10-title">{{ type === 'gpu' ? 'GPU' : 'CPU' }} TOP10 进程</span>
      <span class="top10-time">时刻: {{ currentTime }}s</span>
    </div>
    <div class="top10-content">
      <!-- TOP3 迷你趋势线 -->
      <div class="top3-section">
        <div v-for="(item, idx) in top3" :key="idx" class="top3-item" :style="{ background: idx === 0 ? '#f0f9eb' : idx === 1 ? '#fef0f0' : '#fdf6ec' }">
          <div class="mini-trend" :ref="(el) => { if (el) miniChartRefs.set(item.name, el as HTMLDivElement) }"></div>
          <span class="process-name">{{ item.name }}</span>
          <span class="process-value" :style="{ color: getItemColor(idx) }">{{ item.value.toFixed(1) }}%</span>
        </div>
      </div>

      <!-- TOP4-10 列表 -->
      <div class="top4to10-section">
        <div v-for="(item, idx) in top4to10" :key="idx" class="top4to10-item">
          <span class="rank">{{ idx + 4 }}</span>
          <span class="process-name">{{ item.name }}</span>
          <span class="process-value">{{ item.value.toFixed(1) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top10-list {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}
.top10-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.top10-title {
  font-size: 15px;
  font-weight: 700;
  color: #333;
}
.top10-time {
  font-size: 12px;
  color: #666;
}
.top10-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.top3-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.top3-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 4px;
}
.mini-trend {
  width: 40px;
  height: 16px;
}
.process-name {
  flex: 1;
  font-size: 12px;
  color: #333;
  font-weight: bold;
}
.process-value {
  font-size: 13px;
  font-weight: 600;
}
.top4to10-section {
  border-top: 1px dashed #eee;
  padding-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.top4to10-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.rank {
  width: 18px;
  color: #999;
  font-weight: bold;
}
.top4to10-item .process-name {
  flex: 1;
  color: #666;
  font-weight: normal;
}
.top4to10-item .process-value {
  color: #999;
  font-size: 12px;
}
</style>