<script setup lang="ts">
import { computed } from 'vue';
import type { PerformanceData, ProcessInstance } from '#/api/core/performance-monitor';

// Props 定义
interface Props {
  visible: boolean;
  data: PerformanceData | null;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
  clickPosition?: { x: number; y: number } | null;  // 点击位置
  containerWidth?: number;  // 图表容器宽度
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  clickPosition: null,
  containerWidth: 800,
});

const emit = defineEmits<{
  (e: 'close'): void;
}>();

// 根据图表类型获取实例值
function getInstanceValue(instance: ProcessInstance, chartType: string): number {
  switch (chartType) {
    case 'cpu':
      return instance.cpu;
    case 'gpu':
      return instance.gpu || 0;
    case 'memory':
      return instance.memory || 0;
    case 'commitMemory':
      return instance.committed_memory || 0;
    case 'handles':
      return instance.handles || 0;
    default:
      return instance.cpu;
  }
}

// 格式化显示值
function formatValue(value: number, chartType: string): string {
  if (chartType === 'memory' || chartType === 'commitMemory') {
    return `${Math.round(value)} MB`;
  }
  if (chartType === 'handles') {
    return `${Math.round(value)} 个`;
  }
  return `${value.toFixed(1)}%`;
}

// 过滤 0 值实例，按使用率降序排列
const filteredProcesses = computed(() => {
  if (!props.data?.target_processes) return [];

  return props.data.target_processes
    .map((process) => ({
      name: process.name,
      instances: process.instances
        .filter(
          (instance) => getInstanceValue(instance, props.chartType) > 0,
        )
        .sort(
          (a, b) =>
            getInstanceValue(b, props.chartType) -
            getInstanceValue(a, props.chartType),
        ),
    }))
    .filter((process) => process.instances.length > 0);
});

// 统计总实例数
const totalInstances = computed(() => {
  return filteredProcesses.value.reduce((sum, p) => sum + p.instances.length, 0);
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

// 面板位置计算（fixed 定位，基于点击位置）
const panelPosition = computed(() => {
  const panelWidth = 500;
  const panelHeight = 180;

  // 如果没有点击位置和容器宽度，默认显示在屏幕中央
  if (!props.clickPosition || !props.containerWidth) {
    return {
      left: '50%',
      transform: 'translateX(-50%)',
      top: 'auto',
      bottom: '20px'
    };
  }

  // 基于 containerRect 计算视窗位置
  // 这里我们假设 containerRect 在 miniTooltipState 中传递
  // 简化处理：根据点击位置在图表中的位置判断左右
  const clickX = props.clickPosition.x;
  const chartWidth = props.containerWidth;

  // 右侧点位显示在左边
  if (chartWidth - clickX < panelWidth + 20) {
    return {
      left: '20px',
      right: 'auto',
      top: 'auto',
      bottom: '20px',
      transform: 'none'
    };
  }

  // 默认显示在右边
  return {
    left: 'auto',
    right: '20px',
    top: 'auto',
    bottom: '20px',
    transform: 'none'
  };
});
</script>

<template>
  <div
    v-if="visible && data"
    class="process-detail-panel"
    :style="panelPosition"
  >
    <!-- 头部 -->
    <div class="panel-header">
      <h3 class="panel-title">目标进程明细</h3>
      <button class="close-btn" @click="emit('close')">×</button>
    </div>

    <!-- 时间信息 -->
    <div class="panel-time">
      <div class="time-row">时间: {{ formatDateTime(data.timestamp) }}</div>
    </div>

    <!-- 主曲线数值 -->
    <div class="panel-series">
      <div class="series-label">主曲线数值：</div>
      <div
        v-for="s in seriesData"
        :key="s.name"
        class="series-row"
      >
        <div class="series-name">
          <span class="color-dot" :style="{ background: s.color }"></span>
          <span>{{ s.name }} {{ chartType === 'memory' || chartType === 'commitMemory' ? 'Memory' : 'CPU' }}</span>
        </div>
        <span class="series-value" :style="{ color: s.color }">
          {{ s.value.toFixed(1) }}{{ s.unit }}
        </span>
      </div>
    </div>

    <!-- 子进程详情 -->
    <div v-if="filteredProcesses.length > 0" class="panel-processes">
      <div class="processes-label">子进程详情：</div>
      <div class="processes-list">
        <div
          v-for="process in filteredProcesses"
          :key="process.name"
          class="process-group"
        >
          <div
            v-for="instance in process.instances"
            :key="instance.pid"
            class="instance-row"
          >
            <span class="instance-name">{{ process.name }}</span>
            <span class="instance-pid">(PID:{{ instance.pid }})</span>
            <span class="instance-value">
              {{ formatValue(getInstanceValue(instance, chartType), chartType) }}
            </span>
          </div>
        </div>
      </div>
      <div class="total-count">共 {{ totalInstances }} 个子进程实例</div>
    </div>
  </div>
</template>

<style scoped>
.process-detail-panel {
  position: fixed;
  z-index: 1000;
  width: 500px;
  height: 180px;  /* 固定高度，不用 max-height */
  padding: 16px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgb(0 0 0 / 15%);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.close-btn {
  z-index: 51;
  width: 24px;
  height: 24px;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  background: #f5f5f5;
  border: none;
  border-radius: 50%;
}

.close-btn:hover {
  background: #e8e8e8;
}

.panel-time {
  margin-bottom: 10px;
}

.time-row {
  margin-bottom: 4px;
  font-size: 13px;
  color: #666;
}

.panel-series {
  padding-top: 10px;
  margin-bottom: 10px;
  border-top: 1px dashed #eee;
}

.series-label {
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.series-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
}

.series-name {
  display: flex;
  gap: 5px;
  align-items: center;
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

.panel-processes {
  padding-top: 10px;
  border-top: 1px dashed #eee;
}

.processes-label {
  margin-bottom: 8px;
  font-size: 12px;
  color: #999;
}

.processes-list {
  max-height: 200px;
  overflow-y: auto;
}

.instance-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  margin-bottom: 4px;
  font-size: 11px;
  background: #f9f9f9;
  border-radius: 6px;
}

.instance-name {
  color: #333;
}

.instance-pid {
  font-size: 10px;
  color: #999;
}

.instance-value {
  font-weight: 600;
  color: #409eff;
}

.total-count {
  margin-top: 8px;
  font-size: 11px;
  color: #999;
  text-align: center;
}

/* 过渡动画 */
.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
</style>