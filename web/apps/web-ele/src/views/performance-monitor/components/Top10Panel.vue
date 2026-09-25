<script setup lang="ts">
import type { PerformanceData } from '#/api/core/performance-monitor';

import { computed } from 'vue';

const props = withDefaults(defineProps<Props>(), {
  clickedTime: 0,
});

function sampleTimeSeconds(data: PerformanceData): number {
  return (data.elapsed_ms ?? data.relative_time * 1000) / 1000;
}

interface Props {
  data: PerformanceData[];
  clickedTime?: number;
  metricType: 'cpu' | 'gpu';
}

// 排名颜色：1-4 使用彩色，5-10 使用灰色
const rankColors: string[] = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c'];
const grayColor = '#606266';

function getRankColor(rank: number): string {
  if (rank <= 4) return rankColors[rank - 1] ?? grayColor;
  return grayColor;
}

// 根据点击时间获取对应数据点
const selectedDataPoint = computed(() => {
  if (props.data.length === 0) return null;

  // 如果有点击时间，找到对应数据点
  if (props.clickedTime > 0) {
    const point = props.data.find(
      (d) => sampleTimeSeconds(d) === props.clickedTime,
    );
    if (point) return point;
  }

  // 默认返回最后一个数据点
  return props.data[props.data.length - 1];
});

// 从数据点提取系统 TOP10 应用（按进程名合并汇总）
const top10Processes = computed(() => {
  const point = selectedDataPoint.value;
  if (!point) return [];

  // 根据 metricType 选择数据
  const top10Data =
    props.metricType === 'cpu' ? point.top10_cpu : point.top10_gpu;
  if (!top10Data) return [];

  // 按进程名合并汇总
  const processMap = new Map<string, number>();
  top10Data.forEach((p) => {
    const name = p.name.replace('.exe', '').replace('.EXE', '');
    const value = props.metricType === 'cpu' ? p.cpu || 0 : p.gpu || 0;
    const existing = processMap.get(name) || 0;
    processMap.set(name, existing + value);
  });

  // 转换为数组并排序，取前10
  return [...processMap.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);
});

// 计算最大值用于进度条
const maxValue = computed(() => {
  if (top10Processes.value.length === 0) return 100;
  return Math.max(...top10Processes.value.map((d) => d.value), 1);
});

// 时间戳格式化（完整日期时间）
const formattedTimestamp = computed(() => {
  if (!selectedDataPoint.value) return '';
  const date = new Date(selectedDataPoint.value.timestamp);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
});
</script>

<template>
  <div class="top10-panel">
    <div class="panel-header">
      <span class="panel-title">系统TOP10应用</span>
      <span class="panel-time">{{ formattedTimestamp }}</span>
    </div>
    <div v-if="top10Processes.length > 0" class="top10-list">
      <div
        v-for="(item, index) in top10Processes"
        :key="item.name"
        class="top10-item"
      >
        <span class="rank" :style="{ color: getRankColor(index + 1) }">{{
          index + 1
        }}</span>
        <div class="progress-bar-bg">
          <div
            class="progress-bar"
            :style="{
              width: `${(item.value / maxValue) * 100}%`,
              background: getRankColor(index + 1),
            }"
          ></div>
        </div>
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value" :style="{ color: getRankColor(index + 1) }">
          {{ item.value.toFixed(1) }}%
        </span>
      </div>
    </div>
    <div v-else class="no-data">
      <span>暂无数据</span>
    </div>
  </div>
</template>

<style scoped>
.top10-panel {
  width: 100%;
  padding: 16px;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgb(0 0 0 / 6%);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.panel-time {
  font-size: 12px;
  color: #666;
}

.top10-list {
  height: 260px;
  overflow-y: auto;
  font-size: 12px;
}

.top10-item {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 4px 8px;
  margin-bottom: 2px;
  background: #f9f9f9;
  border-radius: 4px;
}

.rank {
  width: 18px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
}

.progress-bar-bg {
  flex: 1;
  height: 5px;
  background: #e5e5e5;
  border-radius: 2px;
}

.progress-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.process-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
}

.process-value {
  min-width: 45px;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
  white-space: nowrap;
}

.no-data {
  padding: 40px 20px;
  color: #999;
  text-align: center;
}
</style>
