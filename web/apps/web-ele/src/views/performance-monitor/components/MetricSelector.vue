<script setup lang="ts">
interface Props {
  currentMetric: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  change: [metric: string];
  more: [];
}>();

// 固定显示的4个指标
const mainMetrics = [
  { key: 'cpu', label: 'CPU' },
  { key: 'gpu', label: 'GPU' },
  { key: 'memory', label: '内存' },
  { key: 'commitMemory', label: '提交内存' },
];

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
  background: #fff;
  border-radius: 8px;
  padding: 12px;
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