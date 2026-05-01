<script setup lang="ts">
import { computed } from 'vue';
import type { Top10Item } from '../types';

const props = defineProps<{
  title: string;
  items: Top10Item[];
}>();

// TOP3 显示迷你趋势线
const top3 = computed(() => props.items.slice(0, 3));
// 其他显示列表
const others = computed(() => props.items.slice(3, 10));

function getBgColor(index: number): string {
  if (index === 0) return '#f0f9eb';
  if (index === 1) return '#fef0f0';
  return '#fdf6ec';
}
</script>

<template>
  <div class="top10-list">
    <div class="top10-title">{{ title }}</div>
    <div class="top10-content">
      <!-- TOP3 迷你趋势线 -->
      <div
        v-for="(item, index) in top3"
        :key="index"
        class="top10-item top-item"
        :style="{ background: getBgColor(index) }"
      >
        <div class="mini-trend">
          <svg class="mini-svg" viewBox="0 0 40 16">
            <polyline
              :points="
                item.trendData
                  .map((v, i) => `${i * 4},${16 - Math.min(v, 16)}`)
                  .join(' ')
              "
              :stroke="item.color"
              stroke-width="1.5"
              fill="none"
            />
          </svg>
        </div>
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value" :style="{ color: item.color }">
          {{ item.value.toFixed(1) }}%
        </span>
      </div>

      <!-- TOP4-10 列表 -->
      <div
        v-for="(item, index) in others"
        :key="index + 3"
        class="top10-item other-item"
      >
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value">{{ item.value.toFixed(1) }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top10-list {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
}
.top10-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}
.top10-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.top10-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 4px;
}
.top-item {
  font-size: 11px;
}
.mini-trend {
  width: 40px;
  height: 16px;
}
.mini-svg {
  width: 100%;
  height: 100%;
}
.process-name {
  flex: 1;
  font-size: 11px;
  color: #333;
}
.process-value {
  font-size: 12px;
  font-weight: 600;
}
.other-item {
  background: transparent;
  border-top: 1px dashed #eee;
  padding: 4px 0;
  font-size: 10px;
  color: #666;
  justify-content: space-between;
}
</style>