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
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
});

// fixed 定位，基于视窗位置（containerRect + 鼠标相对位置）
// 边界检测：超出屏幕右侧时显示在左边
const tooltipPosition = computed(() => {
  if (!props.position || !props.containerRect) {
    return { left: 0, top: 0 };
  }

  // Tooltip 宽度约 280px（增加宽度避免换行）
  const tooltipWidth = 280;
  const screenWidth = window.innerWidth;

  // 默认显示在鼠标右侧
  let left = props.containerRect.left + props.position.x + 30;

  // 边界检测：如果超出屏幕右侧，则显示在鼠标左侧
  if (left + tooltipWidth > screenWidth - 10) {
    left = props.containerRect.left + props.position.x - tooltipWidth - 30;
  }

  const top = props.containerRect.top + props.position.y + 10;

  return { left, top };
});

// 显示进程名 + 实例数（最多 3 个）- HWiNFO 指标不显示进程数据
const processSummary = computed(() => {
  if (props.data?.target_processes && props.chartType !== 'hwinfo') {
    return props.data.target_processes
      .filter(p => p.instances && p.instances.length > 0)
      .slice(0, 3)
      .map(p => ({
        name: p.name,
        instanceCount: p.instances.length
      }));
  }
  return [];
});

// 格式化时间戳
function formatDateTime(timestamp: string): string {
  if (!timestamp) return '';

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
    <!-- 时间 -->
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
          {{ s.unit === '个' ? Math.round(s.value) : s.value.toFixed(1) }}{{ s.unit }}
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
  </div>
</template>

<style scoped>
.mini-tooltip {
  position: fixed;  /* 相对于视窗定位 */
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
  padding: 12px;
  z-index: 1000;
  font-size: 13px;
  min-width: 200px;
  max-width: 280px;  /* 增加宽度避免换行 */
  max-height: 150px;
  overflow: hidden;
  pointer-events: none;  /* 点击穿透 */
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
</style>