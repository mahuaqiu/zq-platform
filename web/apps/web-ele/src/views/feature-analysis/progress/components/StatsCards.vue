<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';

import type { PieChartDataItem } from '#/api/core/feature-analysis';
import {
  getTestStatusChartApi,
} from '#/api/core/feature-analysis';

defineOptions({ name: 'StatsCards' });

const props = defineProps<{
  version?: string;
}>();

const loading = ref(false);

// 统计数据
const stats = ref({
  total: 0,
  completed: 0,
  testing: 0,
  notStarted: 0,
});

// 加载统计数据
async function loadStats() {
  loading.value = true;
  try {
    const res = await getTestStatusChartApi(props.version);
    const data = res.seriesData || [];

    // 解析数据
    stats.value.total = data.reduce((sum: number, item: PieChartDataItem) => sum + item.value, 0);
    stats.value.completed = data.find((item: PieChartDataItem) => item.name === '已完成')?.value || 0;
    stats.value.testing = data.find((item: PieChartDataItem) => item.name === '测试中')?.value || 0;
    stats.value.notStarted = data.find((item: PieChartDataItem) => item.name === '未开始')?.value || 0;
  } catch (error) {
    console.error('加载统计数据失败:', error);
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.version,
  () => {
    loadStats();
  }
);

onMounted(() => {
  loadStats();
});
</script>

<template>
  <div v-loading="loading" class="stats-row">
    <div class="stat-card">
      <div class="stat-value">{{ stats.total }}</div>
      <div class="stat-label">特性总数</div>
    </div>
    <div class="stat-card success">
      <div class="stat-value">{{ stats.completed }}</div>
      <div class="stat-label">已完成</div>
    </div>
    <div class="stat-card warning">
      <div class="stat-value">{{ stats.testing }}</div>
      <div class="stat-label">测试中</div>
    </div>
    <div class="stat-card danger">
      <div class="stat-value">{{ stats.notStarted }}</div>
      <div class="stat-label">未开始</div>
    </div>
  </div>
</template>

<style scoped>
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  flex: 1;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 16px;
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1890ff;
}

.stat-label {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}

.stat-card.success .stat-value {
  color: #52c41a;
}

.stat-card.warning .stat-value {
  color: #faad14;
}

.stat-card.danger .stat-value {
  color: #ff4d4f;
}
</style>