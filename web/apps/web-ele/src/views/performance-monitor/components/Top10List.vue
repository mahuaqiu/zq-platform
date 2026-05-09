<script setup lang="ts">
import { ref, watch } from 'vue';
import type { PerformanceData } from '../types';

interface Top10ItemInternal {
  name: string;
  value: number;
  percent: number;
}

const props = defineProps<{
  data: PerformanceData[];
  clickedTime?: number;
}>();

const currentTime = ref<number>(0);
const top5 = ref<Top10ItemInternal[]>([]);
const top6to10 = ref<Top10ItemInternal[]>([]);

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

  if (closestData?.top10_cpu) {
    const maxCpu = Math.max(...closestData.top10_cpu.map((p) => p.cpu || 0));
    const items = closestData.top10_cpu.map((p) => ({
      name: p.name,
      value: p.cpu || 0,
      percent: maxCpu > 0 ? ((p.cpu || 0) / maxCpu) * 100 : 0,
    }));
    top5.value = items.slice(0, 5);
    top6to10.value = items.slice(5, 10);
  }
}

function getBarColor(idx: number): string {
  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399'];
  return colors[idx] || '#909399';
}
</script>

<template>
  <div class="top10-list">
    <div class="top10-header">
      <span class="top10-title">进程 TOP10 排名</span>
      <span class="top10-time">时刻: {{ currentTime }}s</span>
    </div>
    <div class="top10-content">
      <div class="top10-column">
        <div v-for="(item, idx) in top5" :key="idx" class="top10-item">
          <span class="process-name">{{ item.name }}</span>
          <div class="bar-container">
            <div
              class="bar-fill"
              :style="{ width: item.percent + '%', background: getBarColor(idx) }"
            >
              <span class="bar-value">{{ item.value.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>
      <div class="top10-column">
        <div v-for="(item, idx) in top6to10" :key="idx" class="top10-item small">
          <span class="process-name">{{ item.name }}</span>
          <div class="bar-container">
            <div class="bar-fill" :style="{ width: item.percent + '%', background: '#909399' }"></div>
          </div>
          <span class="bar-value-right">{{ item.value.toFixed(1) }}%</span>
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}
.top10-column {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.top10-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.process-name {
  width: 90px;
  font-size: 12px;
  color: #333;
  font-weight: bold;
}
.top10-item.small .process-name {
  color: #666;
  font-weight: normal;
}
.bar-container {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 4px;
}
.top10-item.small .bar-container {
  height: 16px;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 5px;
}
.bar-value {
  color: white;
  font-size: 11px;
  font-weight: bold;
}
.bar-value-right {
  font-size: 11px;
  color: #999;
  width: 45px;
  text-align: right;
}
</style>