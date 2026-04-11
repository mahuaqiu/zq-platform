<script lang="ts" setup>
import type { StepDistributionItem } from '#/api/core/test-report';

import { computed } from 'vue';

const props = defineProps<{
  stepDistribution: StepDistributionItem[] | null;
}>();

// 计算最大值用于比例
const maxCount = computed(() => {
  if (!props.stepDistribution || props.stepDistribution.length === 0) return 1;
  return Math.max(...props.stepDistribution.map((s) => s.count));
});

// 颜色列表
const COLORS = ['#ff4d4f', '#faad14', '#1890ff', '#52c41a', '#722ed1', '#eb2f96'];
</script>

<template>
  <div class="step-distribution" v-if="stepDistribution && stepDistribution.length > 0">
    <div class="step-title">失败步骤分布（Top 20）</div>
    <div class="step-content">
      <div class="step-item" v-for="(item, index) in stepDistribution" :key="item.step">
        <div class="step-name">{{ item.step }}</div>
        <div class="step-bar-wrapper">
          <div
            class="step-bar"
            :style="{
              width: `${(item.count / maxCount) * 100}%`,
              background: COLORS[index % COLORS.length],
            }"
          ></div>
        </div>
        <div class="step-count">{{ item.count }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.step-distribution {
  padding: 16px;
  background: #fff;
}

.step-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.step-content {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.step-item:last-child {
  margin-bottom: 0;
}

.step-name {
  flex-shrink: 0;
  width: 140px;
  font-size: 13px;
  color: #333;
}

.step-bar-wrapper {
  flex: 1;
  height: 20px;
  margin: 0 8px;
}

.step-bar {
  min-width: 4px;
  height: 20px;
  border-radius: 2px;
}

.step-count {
  flex-shrink: 0;
  width: 30px;
  font-size: 13px;
  color: #666;
  text-align: right;
}
</style>