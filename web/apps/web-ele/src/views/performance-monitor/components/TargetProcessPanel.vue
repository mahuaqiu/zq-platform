<script setup lang="ts">
import { computed } from 'vue';
import type { PerformanceData, ProcessData, ProcessInstance } from '#/api/core/performance-monitor';

interface Props {
  data: PerformanceData[];
  clickedTime?: number;
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'hwinfo' | 'handles';
}

const props = withDefaults(defineProps<Props>(), {
  clickedTime: 0,
});

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

// 根据点击时间获取对应数据点
const selectedDataPoint = computed(() => {
  if (!props.data.length) return null;

  // 如果有点击时间，找到对应数据点
  if (props.clickedTime > 0) {
    const point = props.data.find(d => d.relative_time === props.clickedTime);
    if (point) return point;
  }

  // 默认返回最后一个数据点
  return props.data[props.data.length - 1];
});

// 过滤有效进程实例，按使用率降序排列
const filteredProcesses = computed(() => {
  const point = selectedDataPoint.value;
  if (!point?.target_processes) return [];

  return point.target_processes
    .map((process: ProcessData) => ({
      name: process.name,
      instances: process.instances
        .filter((instance: ProcessInstance) => getInstanceValue(instance, props.chartType) > 0)
        .sort((a: ProcessInstance, b: ProcessInstance) =>
          getInstanceValue(b, props.chartType) - getInstanceValue(a, props.chartType)
        ),
    }))
    .filter((process) => process.instances.length > 0);
});

// 统计总实例数
const totalInstances = computed(() => {
  return filteredProcesses.value.reduce((sum, p) => sum + p.instances.length, 0);
});

// 时间戳格式化（完整日期时间）
const formattedTimestamp = computed(() => {
  if (!selectedDataPoint.value) return '';
  const date = new Date(selectedDataPoint.value.timestamp);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
});
</script>

<template>
  <div class="target-process-panel">
    <div class="panel-header">
      <span class="panel-title">目标进程明细</span>
      <span class="panel-time">{{ formattedTimestamp }}</span>
    </div>

    <!-- 子进程详情 -->
    <div v-if="filteredProcesses.length > 0" class="panel-processes">
      <div class="processes-label">子进程详情（{{ totalInstances }}）：</div>
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
            <span class="instance-name">{{ process.name.replace('.exe', '').replace('.EXE', '') }} (PID:{{ instance.pid }})</span>
            <span class="instance-value">
              {{ formatValue(getInstanceValue(instance, chartType), chartType) }}
            </span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="no-data">
      <span>暂无目标进程数据</span>
    </div>
  </div>
</template>

<style scoped>
.target-process-panel {
  width: 100%;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e5e5e5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.panel-time {
  font-size: 12px;
  color: #666;
}

.panel-processes {
  font-size: 12px;
}

.processes-label {
  margin-bottom: 8px;
  font-size: 12px;
  color: #999;
}

.processes-list {
  max-height: 260px;
  overflow-y: auto;
}

.process-group {
  margin-bottom: 6px;
}

.instance-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  margin-bottom: 4px;
  font-size: 12px;
  background: #f9f9f9;
  border-radius: 6px;
}

.instance-name {
  color: #333;
}

.instance-value {
  font-weight: 600;
  font-size: 13px;
  color: #409eff;
}

.no-data {
  padding: 40px 20px;
  text-align: center;
  color: #999;
}
</style>