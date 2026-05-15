<script setup lang="ts">
import { computed } from 'vue';

interface ProcessItem {
  name: string;
  value: number;
}

interface Props {
  data: ProcessItem[];
  timestamp: string;
  metric: 'cpu' | 'gpu';
}

const props = defineProps<Props>();

// 排名颜色：1-4 使用彩色，5-10 使用灰色
const rankColors: string[] = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c'];
const grayColor = '#606266';

function getRankColor(rank: number): string {
  if (rank <= 4) return rankColors[rank - 1];
  return grayColor;
}

// 计算最大值用于进度条
const maxValue = computed(() => {
  if (!props.data.length) return 100;
  return Math.max(...props.data.map(d => d.value), 1);
});
</script>

<template>
  <div class="top10-panel">
    <div class="panel-header">
      <span class="panel-title">系统TOP10进程</span>
      <span class="panel-time">{{ timestamp }}</span>
    </div>
    <div class="top10-list">
      <div v-for="(item, index) in data" :key="item.name" class="top10-item">
        <span class="rank" :style="{ color: getRankColor(index + 1) }">{{ index + 1 }}</span>
        <div class="progress-bar-bg">
          <div
            class="progress-bar"
            :style="{
              width: `${(item.value / maxValue) * 100}%`,
              background: getRankColor(index + 1)
            }"
          ></div>
        </div>
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value" :style="{ color: getRankColor(index + 1) }">
          {{ item.value.toFixed(1) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top10-panel {
  width: 500px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e5e5e5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.panel-time {
  font-size: 12px;
  color: #666;
}

.top10-list {
  font-size: 11px;
}

.top10-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.rank {
  width: 16px;
  font-weight: 600;
  text-align: center;
}

.progress-bar-bg {
  flex: 1;
  height: 6px;
  background: #f5f5f5;
  border-radius: 2px;
}

.progress-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.process-name {
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}

.process-value {
  white-space: nowrap;
  min-width: 40px;
  text-align: right;
}
</style>