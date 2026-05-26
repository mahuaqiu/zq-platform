<script setup lang="ts">
interface Props {
  currentMetric: string;
  isLinuxDevice?: boolean;  // 是否为 Linux 设备
}

const props = defineProps<Props>();
const emit = defineEmits<{
  change: [metric: string];
  more: [];
}>();

// 固定显示的指标
// Linux 设备：不显示 GPU（无 GPU 数据）、不显示提交内存（Linux 不区分）、不显示进程句柄（无进程数据）
const mainMetrics = computed(() => {
  const baseMetrics = [
    { key: 'cpu_usage', label: 'CPU' },
    ...(props.isLinuxDevice ? [] : [{ key: 'gpu_usage', label: 'GPU' }]),
    { key: 'memory_usage', label: '内存' },
    ...(props.isLinuxDevice ? [] : [{ key: 'commit_memory', label: '提交内存' }]),
    ...(props.isLinuxDevice ? [] : [{ key: 'process_handles', label: '进程句柄' }]),
  ];
  return baseMetrics;
});

import { computed } from 'vue';

function handleMetricClick(metric: string) {
  emit('change', metric);
}

function handleMoreClick() {
  emit('more');
}
</script>

<template>
  <div class="metric-selector">
    <div class="metric-cards">
      <button
        v-for="metric in mainMetrics"
        :key="metric.key"
        :class="['metric-card', { active: currentMetric === metric.key }]"
        @click="handleMetricClick(metric.key)"
      >
        {{ metric.label }}
      </button>
      <button class="metric-card more-btn" @click="handleMoreClick">
        更多指标 ▼
      </button>
    </div>
  </div>
</template>

<style scoped>
.metric-selector {
  border-radius: 8px;
}

.metric-cards {
  display: flex;
  gap: 8px;
  align-items: center;
}

.metric-card {
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  background: #fff;
  border: 1px solid var(--el-color-primary);
  color: var(--el-color-primary);
  transition: all 0.3s ease;
}

.metric-card:hover:not(.active) {
  background: #ecf5ff;
}

.metric-card.active {
  background: var(--el-color-primary);
  color: white;
  border: none;
}

.more-btn {
  padding: 10px 16px;
}
</style>