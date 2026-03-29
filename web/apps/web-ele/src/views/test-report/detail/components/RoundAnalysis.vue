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
  background: #f5f7fa;
}

.round-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #333;
}

.round-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.round-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.round-value {
  font-size: 24px;
  font-weight: 600;
}

.round-label {
  font-size: 13px;
  color: #666;
}

.round-red {
  border-color: #ff4d4f;
}

.round-red .round-value {
  color: #ff4d4f;
}

.round-orange {
  border-color: #faad14;
}

.round-orange .round-value {
  color: #faad14;
}

.round-green {
  border-color: #52c41a;
}

.round-green .round-value {
  color: #52c41a;
}
</style>