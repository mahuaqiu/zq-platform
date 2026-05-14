<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { ProcessData, ProcessInstance } from '#/api/core/performance-monitor';

// Tooltip 数据类型
interface TooltipData {
  timestamp: string;
  relativeTime: number;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  processes: ProcessData[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
}

interface Props {
  visible: boolean;
  position: { x: number; y: number };
  containerRect: DOMRect | null; // 图表容器位置，用于定位
  data: TooltipData | null;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
});

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'lock'): void;  // 锁定位置，停止跟随鼠标
  (e: 'unlock'): void; // 解锁位置
}>();

// 折叠/展开状态
const expanded = ref(false);

// 鼠标进入 tooltip 时锁定位置
function handleMouseEnter() {
  emit('lock');
}

// 鼠标离开 tooltip 时解锁位置
function handleMouseLeave() {
  emit('unlock');
}

// 关闭时重置状态
watch(
  () => props.visible,
  (newVal) => {
    if (!newVal) {
      expanded.value = false;
    }
  },
);

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
    default:
      return instance.cpu;
  }
}

// 格式化显示值
function formatValue(value: number, chartType: string): string {
  if (chartType === 'memory' || chartType === 'commitMemory') {
    return `${Math.round(value)} MB`;
  }
  return `${value.toFixed(1)}%`;
}

// 过滤 0 值实例，按使用率降序排列
const filteredProcesses = computed(() => {
  if (!props.data?.processes) return [];

  return props.data.processes
    .map((process) => ({
      name: process.name,
      instances: process.instances
        .filter(
          (instance) => getInstanceValue(instance, props.data!.chartType) > 0,
        )
        .sort(
          (a, b) =>
            getInstanceValue(b, props.data!.chartType) -
            getInstanceValue(a, props.data!.chartType),
        ),
    }))
    .filter((process) => process.instances.length > 0);
});

// 检查是否有非 0 数据
const hasValidProcessData = computed(() => {
  return filteredProcesses.value.some((p) => p.instances.length > 0);
});

// 统计总实例数
const totalInstances = computed(() => {
  return filteredProcesses.value.reduce((sum, p) => sum + p.instances.length, 0);
});

// 计算 tooltip 定位（确保不超出容器）
const tooltipPosition = computed(() => {
  if (!props.position || !props.containerRect) {
    return { left: 0, top: 0 };
  }

  const width = expanded.value ? 180 : 150;
  const height = expanded.value ? 250 : 150;
  const padding = 10;

  let left = props.position.x + padding;
  let top = props.position.y + padding;

  // 确保不超出右侧边界
  if (left + width > props.containerRect.width) {
    left = props.position.x - width - padding;
  }

  // 确保不超出底部边界
  if (top + height > props.containerRect.height) {
    top = props.position.y - height - padding;
  }

  // 确保不超出左侧和顶部
  left = Math.max(padding, left);
  top = Math.max(padding, top);

  return { left, top };
});
</script>

<template>
  <div
    v-if="visible && data"
    class="process-tooltip"
    :class="{ expanded }"
    :style="{
      left: tooltipPosition.left + 'px',
      top: tooltipPosition.top + 'px',
      width: expanded ? '180px' : '150px',
    }"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <!-- 时间显示 -->
    <div class="tooltip-header">
      <span class="time-display">🕐 {{ data.relativeTime }}s</span>
      <button v-if="expanded" class="close-btn" @click="emit('close')">
        ✕
      </button>
    </div>

    <!-- 主曲线数据 -->
    <div class="series-section">
      <div
        v-for="s in data.seriesData"
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

    <!-- 子进程区块（有数据时才显示） -->
    <div v-if="hasValidProcessData" class="process-section">
      <!-- 折叠状态 -->
      <div v-if="!expanded" class="process-summary">
        <div
          v-for="process in filteredProcesses"
          :key="process.name"
          class="process-name-row"
        >
          {{ process.name }} ({{ process.instances.length }}个实例)
        </div>
        <button class="expand-btn" @click="expanded = true">
          ▼ 查看详情
        </button>
      </div>

      <!-- 展开状态 -->
      <div v-else class="process-detail">
        <div class="detail-label">子进程明细：</div>
        <div class="process-list">
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
                {{ formatValue(getInstanceValue(instance, data.chartType), data.chartType) }}
              </span>
            </div>
          </div>
        </div>
        <div class="total-count">共{{ totalInstances }}个子进程实例</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.process-tooltip {
  position: absolute;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
  padding: 12px;
  z-index: 100;
  font-size: 13px;
  transition: width 0.2s ease;
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-weight: 600;
  color: #333;
}

.time-display {
  font-size: 14px;
}

.close-btn {
  background: #f5f5f5;
  border: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 14px;
  color: #666;
  cursor: pointer;
}

.series-section {
  margin-bottom: 10px;
}

.series-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
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

.process-section {
  border-top: 1px dashed #eee;
  padding-top: 10px;
  margin-top: 6px;
}

.process-summary {
  background: #f0f9ff;
  padding: 8px;
  border-radius: 8px;
}

.process-name-row {
  font-size: 12px;
  color: #409eff;
  font-weight: 500;
  margin-bottom: 4px;
}

.expand-btn {
  width: 100%;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  border: none;
  padding: 8px 0;
  font-size: 13px;
  color: white;
  border-radius: 8px;
  margin-top: 10px;
  font-weight: 500;
  cursor: pointer;
}

.process-detail {
  max-height: 120px;
}

.detail-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.process-list {
  overflow-y: auto;
  max-height: 80px;
}

.instance-row {
  display: flex;
  justify-content: space-between;
  background: #f9f9f9;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 11px;
  margin-bottom: 4px;
}

.instance-name {
  color: #333;
}

.instance-pid {
  color: #999;
  font-size: 10px;
}

.instance-value {
  color: #409eff;
  font-weight: 600;
}

.total-count {
  color: #999;
  font-size: 11px;
  text-align: center;
  margin-top: 4px;
}
</style>