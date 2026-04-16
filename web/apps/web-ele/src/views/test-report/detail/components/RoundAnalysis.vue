<script lang="ts" setup>
import type { RoundStatItem } from '#/api/core/test-report';

import { computed } from 'vue';

const props = defineProps<{
  roundStats: RoundStatItem[] | null;
}>();

// 获取颜色类
function getRoundClass(index: number, total: number) {
  if (index === 0) return 'round-red';
  if (index === total - 1) return 'round-green';
  return 'round-orange';
}
</script>

<template>
  <div class="round-analysis" v-if="roundStats && roundStats.length > 0">
    <div class="round-title">轮次分析</div>
    <div class="round-cards">
      <div
        v-for="(item, index) in roundStats"
        :key="item.round"
        class="round-card"
        :class="getRoundClass(index, roundStats.length)"
      >
        <div class="round-value">{{ item.failCount }}</div>
        <div class="round-label">第{{ item.round }}轮失败</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.round-analysis {
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.round-title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #111;
}

.round-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.round-card {
  padding: 16px 24px;
  background: #fff;
  border-radius: 8px;
  text-align: center;
}

.round-value {
  font-size: 24px;
  font-weight: 600;
}

.round-label {
  font-size: 13px;
  color: #666;
}

/* 第一轮失败 - 红色背景 */
.round-red {
  background: #fee2e2;
  border: 1px solid #fecaca;
}

.round-red .round-value {
  color: #ef4444;
}

/* 中间轮次 - 橙色背景 */
.round-orange {
  background: #fef3c7;
  border: 1px solid #fcd34d;
}

.round-orange .round-value {
  color: #f59e0b;
}

/* 最后一轮 - 绿色背景 */
.round-green {
  background: #dcfce7;
  border: 1px solid #86efac;
}

.round-green .round-value {
  color: #22c55e;
}
</style>