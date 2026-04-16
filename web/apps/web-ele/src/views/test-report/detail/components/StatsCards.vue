<script lang="ts" setup>
import type { TestReportSummary } from '#/api/core/test-report';

import { computed } from 'vue';

import { ElCard } from 'element-plus';

const props = defineProps<{
  summary: TestReportSummary | null;
  loading?: boolean;
}>();

// 格式化同比变化
const compareDisplay = computed(() => {
  if (!props.summary) return { text: '--', sub: '', cls: 'stat-gray' };
  const change = props.summary.compareChange;
  if (change === null) return { text: '--', sub: '首次执行', cls: 'stat-gray' };
  const text = change > 0 ? `↑${change}` : change < 0 ? `↓${Math.abs(change)}` : '→0';
  const sub = props.summary.lastFailTotal !== null ? `上次失败${props.summary.lastFailTotal}个` : '';
  const cls = change > 0 ? 'stat-red' : change < 0 ? 'stat-green' : 'stat-gray';
  return { text, sub, cls };
});
</script>

<template>
  <div class="stats-cards" v-loading="loading">
    <ElCard class="stats-card">
      <div class="stats-label">用例总数</div>
      <div class="stats-value stat-blue">{{ summary?.totalCases ?? '--' }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-label">执行总数</div>
      <div class="stats-value stat-blue">{{ summary?.executeTotal ?? '--' }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-label">通过率</div>
      <div class="stats-value stat-green">{{ summary?.passRate ?? '--' }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-label">失败总数</div>
      <div class="stats-value stat-red">{{ summary?.failTotal ?? '--' }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-label">同比上次执行</div>
      <div class="stats-value" :class="compareDisplay.cls">{{ compareDisplay.text }}</div>
      <div class="stats-sub" v-if="compareDisplay.sub">{{ compareDisplay.sub }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-label">每轮都失败</div>
      <div class="stats-value stat-orange">{{ summary?.failAlways ?? '--' }}</div>
      <div class="stats-sub">重点关注</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-label">不稳定用例</div>
      <div class="stats-value stat-blue">{{ summary?.failUnstable ?? '--' }}</div>
      <div class="stats-sub">重试后通过</div>
    </ElCard>
  </div>
</template>

<style scoped>
.stats-cards {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: #fff;
}

.stats-card {
  flex: 1;
  text-align: center;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border: 1px solid #e8e8e8;
}

.stats-card :deep(.el-card__body) {
  padding: 20px;
}

.stats-value {
  font-size: 32px;
  font-weight: 600;
}

.stats-label {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 600;
  color: #111;
}

.stats-sub {
  margin-top: 2px;
  font-size: 11px;
  color: #111;
}

.stat-blue {
  color: #3b82f6;
}

.stat-green {
  color: #22c55e;
}

.stat-red {
  color: #ef4444;
}

.stat-orange {
  color: #f59e0b;
}

.stat-gray {
  color: #999;
}
</style>