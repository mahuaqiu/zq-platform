<script setup lang="ts">
import { computed } from 'vue';
import type { PerformanceData } from '#/api/core/performance-monitor';

// Props 定义
interface Props {
  visible: boolean;
  position: { x: number; y: number };
  containerRect: DOMRect | null;
  data: PerformanceData | undefined;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
});

// 跟随鼠标，保持固定偏移距离（30px 右侧，10px 下方）
const tooltipPosition = computed(() => {
  if (!props.position || !props.containerRect) {
    return { left: 0, top: 0 };
  }

  const width = 180;
  const height = 150;
  const offsetX = 30;  // 水平偏移距离
  const offsetY = 10;  // 垂直偏移距离

  // 基于鼠标位置计算 tooltip 位置（保持固定偏移距离）
  let left = props.position.x + offsetX;
  let top = props.position.y + offsetY;

  // 确保不超出右侧边界
  if (left + width > props.containerRect.width) {
    left = props.position.x - width - offsetX;  // 如果超出右侧，显示在鼠标左侧
  }

  // 确保不超出底部边界
  if (top + height > props.containerRect.height) {
    top = props.position.y - height - offsetY;  // 如果超出底部，显示在鼠标上方
  }

  // 确保不超出左侧和顶部
  left = Math.max(0, left);
  top = Math.max(0, top);

  return { left, top };
});

// 显示进程名 + 实例数（最多显示 3 个进程）
const processSummary = computed(() => {
  if (!props.data?.target_processes) return [];

  return props.data.target_processes
    .filter(p => p.instances && p.instances.length > 0)
    .slice(0, 3)
    .map(p => ({
      name: p.name,
      instanceCount: p.instances.length
    }));
});

// 格式化时间戳
function formatDateTime(timestamp: string): string {
  const date = new Date(timestamp);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}
</script>

<template>
  <div
    v-if="visible && data"
    class="mini-tooltip"
    :style="{
      left: tooltipPosition.left + 'px',
      top: tooltipPosition.top + 'px',
    }"
  >
    <!-- 时间显示 -->
    <div class="tooltip-time">
      {{ formatDateTime(data.timestamp) }}
    </div>

    <!-- 主曲线数据 -->
    <div class="tooltip-series">
      <div
        v-for="s in seriesData"
        :key="s.name"
        class="series-row"
      >
        <div class="series-name">
          <span class="color-dot" :style="{ background: s.color }"></span>
          <span>{{ s.name }}</span>
        </div>
        <span class="series-value" :style="{ color: s.color }">
          {{ s.value.toFixed(1) }}{{ s.unit }}
        </span>
      </div>
    </div>

    <!-- 进程摘要 -->
    <div v-if="processSummary.length > 0" class="tooltip-processes">
      <div
        v-for="p in processSummary"
        :key="p.name"
        class="process-row"
      >
        {{ p.name }} ({{ p.instanceCount }}实例)
      </div>
    </div>

    <!-- 点击提示 -->
    <div class="tooltip-hint">
      点击查看子进程详情
    </div>
  </div>
</template>

<style scoped>
.mini-tooltip {
  position: absolute;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
  padding: 12px;
  z-index: 100;
  font-size: 13px;
  min-width: 160px;
  max-width: 180px;
  max-height: 150px;
  overflow: hidden;
}

.tooltip-time {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.tooltip-series {
  margin-bottom: 8px;
}

.series-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.series-name {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #666;
}

.color-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.series-value {
  font-size: 14px;
  font-weight: 600;
}

.tooltip-processes {
  border-top: 1px dashed #eee;
  padding-top: 8px;
  margin-bottom: 8px;
}

.process-row {
  font-size: 12px;
  color: #409eff;
  font-weight: 500;
  margin-bottom: 4px;
}

.tooltip-hint {
  border-top: 1px dashed #eee;
  padding-top: 8px;
  font-size: 11px;
  color: #999;
  text-align: center;
}
</style>