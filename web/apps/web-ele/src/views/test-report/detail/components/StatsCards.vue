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
  if (!props.summary) return { text: '--', sub: '', cls: 'tr-gray' };
  const change = props.summary.compareChange;
  if (change === null) return { text: '--', sub: '首次执行', cls: 'tr-gray' };
  const text = change > 0 ? `↑${change}` : change < 0 ? `↓${Math.abs(change)}` : '→0';
  const sub = props.summary.lastFailTotal !== null ? `上次失败${props.summary.lastFailTotal}个` : '';
  const cls = change > 0 ? 'tr-red' : change < 0 ? 'tr-green' : 'tr-gray';
  return { text, sub, cls };
});
</script>

<template>
  <div class="stats-cards" v-loading="loading">
    <ElCard class="stats-card">
      <div class="stats-value tr-blue">{{ summary?.totalCases ?? '--' }}</div>
      <div class="stats-label">用例总数</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-cyan">{{ summary?.executeTotal ?? '--' }}</div>
      <div class="stats-label">执行总数</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-green">{{ summary?.passRate ?? '--' }}</div>
      <div class="stats-label">通过率</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-red">{{ summary?.failTotal ?? '--' }}</div>
      <div class="stats-label">失败总数</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value" :class="compareDisplay.cls">{{ compareDisplay.text }}</div>
      <div class="stats-label">同比上次执行</div>
      <div class="stats-sub" v-if="compareDisplay.sub">{{ compareDisplay.sub }}</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-orange">{{ summary?.failAlways ?? '--' }}</div>
      <div class="stats-label">每轮都失败</div>
      <div class="stats-sub">重点关注</div>
    </ElCard>
    <ElCard class="stats-card">
      <div class="stats-value tr-blue">{{ summary?.failUnstable ?? '--' }}</div>
      <div class="stats-label">不稳定用例</div>
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
  cursor: default;
}

.stats-card :deep(.el-card__body) {
  padding: 16px;
}

.stats-value {
  font-size: 28px;
  font-weight: 600;
}

.stats-label {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}

.stats-sub {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.tr-blue {
  color: #1890ff;
}

.tr-cyan {
  color: #13c2c2;
}

.tr-green {
  color: #52c41a;
}

.tr-red {
  color: #ff4d4f;
}

.tr-orange {
  color: #faad14;
}

.tr-gray {
  color: #999;
}
</style>