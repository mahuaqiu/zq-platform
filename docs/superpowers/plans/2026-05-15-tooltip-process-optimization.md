# Tooltip 子进程显示优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化性能监控 tooltip 显示，实现子进程折叠/展开、降序排序、过滤0值功能。

**Architecture:** 创建独立的 ProcessTooltip.vue 组件处理 tooltip 交互，修改 ChartPanel.vue 禁用原生 tooltip 并监听鼠标事件传递数据给外部组件。

**Tech Stack:** Vue 3 Composition API、ECharts 事件监听、Element Plus 弹层组件

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue` | 创建 | 外部 tooltip 组件，处理折叠/展开状态 |
| `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue` | 修改 | 禁用原 tooltip，添加 mouseover/mouseout 事件 |
| `web/apps/web-ele/src/views/performance-monitor/index.vue` | 修改 | 添加 ProcessTooltip 组件，传递 tooltip 数据 |

---

### Task 1: 创建 ProcessTooltip.vue 组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue`

- [ ] **Step 1: 创建组件文件并定义 Props 类型**

```vue
<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { PerformanceData, ProcessData, ProcessInstance } from '#/api/core/performance-monitor';
import type { ChartSeries } from '../types';

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
  containerRect: DOMRect | null;  // 图表容器位置，用于定位
  data: TooltipData | null;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
});

const emit = defineEmits<{
  (e: 'close'): void;
}>();

// 折叠/展开状态
const expanded = ref(false);

// 关闭时重置状态
watch(() => props.visible, (newVal) => {
  if (!newVal) {
    expanded.value = false;
  }
});
```

- [ ] **Step 2: 添加数据处理逻辑**

```typescript
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
    .map(process => ({
      name: process.name,
      instances: process.instances
        .filter(instance => getInstanceValue(instance, props.data!.chartType) > 0)
        .sort((a, b) =>
          getInstanceValue(b, props.data!.chartType) -
          getInstanceValue(a, props.data!.chartType)
        )
    }))
    .filter(process => process.instances.length > 0);
});

// 检查是否有非 0 数据
const hasValidProcessData = computed(() => {
  return filteredProcesses.value.some(p => p.instances.length > 0);
});

// 统计总实例数
const totalInstances = computed(() => {
  return filteredProcesses.value.reduce((sum, p) => sum + p.instances.length, 0);
});
```

- [ ] **Step 3: 添加定位计算逻辑**

```typescript
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
```

- [ ] **Step 4: 添加模板部分**

```vue
<template>
  <div
    v-if="visible && data"
    class="process-tooltip"
    :class="{ expanded }"
    :style="{
      left: tooltipPosition.left + 'px',
      top: tooltipPosition.top + 'px',
      width: expanded ? '180px' : '150px'
    }"
  >
    <!-- 时间显示 -->
    <div class="tooltip-header">
      <span class="time-display">🕐 {{ data.relativeTime }}s</span>
      <button v-if="expanded" class="close-btn" @click="emit('close')">✕</button>
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
```

- [ ] **Step 5: 添加样式部分**

```vue
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
```

- [ ] **Step 6: 提交代码**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue
git commit -m "feat: 创建 ProcessTooltip 组件实现折叠/展开功能"
```

---

### Task 2: 修改 ChartPanel.vue 禁用原 tooltip 并添加事件监听

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue`

- [ ] **Step 1: 定义新的 emit 事件和 Props**

在 `<script setup>` 顶部添加：

```typescript
// 定义 Events（新增 tooltip 事件）
const emit = defineEmits<{
  (e: 'point-click', data: { time: number; collectId: string }): void;
  (e: 'tag-delete', tagId: string): void;
  (e: 'tooltip-show', data: {
    position: { x: number; y: number };
    data: PerformanceData;
    seriesData: { name: string; value: number; color: string; unit: string }[];
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
    containerRect: DOMRect;
  }): void;
  (e: 'tooltip-hide'): void;
}>();
```

- [ ] **Step 2: 在 initChart 函数中添加 mouseover/mouseout 事件监听**

在 `initChart()` 函数的 `updateChart()` 调用之前添加：

```typescript
// 监听鼠标移动事件，传递数据给外部 tooltip
chartInstance.on('mousemove', (params: any) => {
  if (params.componentType === 'series') {
    const dataIndex = params.dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];

    // 构建主曲线数据
    const seriesData = props.series.map((s, idx) => ({
      name: s.name,
      value: s.data[dataIndex]?.value || 0,
      color: s.color,
      unit: s.unit || '%',
    }));

    emit('tooltip-show', {
      position: { x: params.event.offsetX, y: params.event.offsetY },
      data: rawDataPoint,
      seriesData,
      chartType: props.chartType,
      containerRect: chartRef.value!.getBoundingClientRect(),
    });
  }
});

// 监听鼠标离开事件
chartInstance.on('mouseout', () => {
  emit('tooltip-hide');
});
```

- [ ] **Step 3: 修改 updateChart 函数，简化 tooltip formatter**

移除原有的子进程显示逻辑，保留主曲线显示：

```typescript
tooltip: {
  trigger: 'axis',
  confine: true,
  formatter: (params: any) => {
    // 简化版本：只显示主曲线，子进程由外部组件处理
    const dataIndex = params[0].dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];

    let html = `<div style="font-size:12px;padding:4px 8px;">`;

    // 实际时间
    if (rawDataPoint?.timestamp) {
      html += `<div style="font-size:12px;margin-bottom:4px"><b style="color:#409eff">${formatDateTime(rawDataPoint.timestamp)}</b></div>`;
    }

    // 主曲线值
    html += `<div style="margin-top:6px">`;
    params.forEach((p: any, idx: number) => {
      const series = props.series[idx];
      const unit = series?.unit || '%';
      let displayValue = '-';
      if (p.value !== undefined) {
        if (unit === 'GB') {
          displayValue = p.value.toFixed(2) + ' GB';
        } else if (unit === 'MB') {
          displayValue = Math.round(p.value) + ' MB';
        } else {
          displayValue = p.value.toFixed(1) + '%';
        }
      }
      html += `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">`;
      html += `<div style="display:flex;align-items:center;gap:5px">`;
      html += `<div style="width:12px;height:12px;background:${p.color};border-radius:3px"></div>`;
      html += `<span style="font-size:13px;color:#666">${p.seriesName}</span>`;
      html += `</div>`;
      html += `<span style="font-size:14px;color:${p.color};font-weight:600">${displayValue}</span>`;
      html += `</div>`;
    });
    html += `</div>`;

    // 提示用户可以 hover 查看子进程
    if (rawDataPoint?.target_processes?.length) {
      html += `<div style="margin-top:6px;padding-top:6px;border-top:1px dashed #eee;font-size:11px;color:#999;text-align:center">hover 查看子进程明细</div>`;
    }

    html += `</div>`;
    return html;
  },
},
```

- [ ] **Step 4: 提交代码**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue
git commit -m "feat: ChartPanel 添加 mouseover/mouseout 事件监听，简化 tooltip"
```

---

### Task 3: 修改 index.vue 添加 ProcessTooltip 组件

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: 导入 ProcessTooltip 组件**

在 `<script setup>` 顶部导入部分添加：

```typescript
import ProcessTooltip from './components/ProcessTooltip.vue';
```

- [ ] **Step 2: 添加 tooltip 状态变量**

在状态变量区域添加：

```typescript
// Tooltip 状态
interface TooltipState {
  position: { x: number; y: number };
  data: PerformanceData;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
  containerRect: DOMRect;
  chartRef: HTMLDivElement;  // 用于定位
}

const tooltipState = ref<TooltipState | null>(null);
const tooltipChartRef = ref<HTMLDivElement | null>(null);
```

- [ ] **Step 3: 添加 tooltip 事件处理函数**

```typescript
// Tooltip 显示事件处理
function handleTooltipShow(data: TooltipState & { containerRect: DOMRect }) {
  tooltipState.value = {
    position: data.position,
    data: data.data,
    seriesData: data.seriesData,
    chartType: data.chartType,
    containerRect: data.containerRect,
    chartRef: tooltipChartRef.value!,
  };
}

// Tooltip 隐藏事件处理
function handleTooltipHide() {
  tooltipState.value = null;
}

// Tooltip 关闭事件处理
function handleTooltipClose() {
  tooltipState.value = null;
}
```

- [ ] **Step 4: 修改 ChartPanel 组件添加事件监听**

为每个 ChartPanel 添加事件监听：

```vue
<!-- CPU使用率图表 -->
<div ref="tooltipChartRef" class="chart-wrapper">
  <ChartPanel
    title="CPU使用率"
    :series="cpuChartSeries"
    :height="180"
    :raw-data="filteredPerformanceData"
    :markers="markers"
    chart-type="cpu"
    @point-click="handlePointClick"
    @tooltip-show="handleTooltipShow"
    @tooltip-hide="handleTooltipHide"
  />
  <ProcessTooltip
    v-if="tooltipState && tooltipChartRef"
    :visible="tooltipState !== null"
    :position="tooltipState.position"
    :containerRect="tooltipState.containerRect"
    :data="tooltipState"
    @close="handleTooltipClose"
  />
</div>
```

注意：ProcessTooltip 需要放在 ChartPanel 的容器内部，这样定位才能正确。

- [ ] **Step 5: 为所有图表添加相同的结构**

需要对 GPU、提交内存、进程内存图表都做同样的处理，每个图表需要独立的 ref：

```typescript
const tooltipCpuChartRef = ref<HTMLDivElement | null>(null);
const tooltipGpuChartRef = ref<HTMLDivElement | null>(null);
const tooltipCommitChartRef = ref<HTMLDivElement | null>(null);
const tooltipMemoryChartRef = ref<HTMLDivElement | null>(null);
const activeChartRef = ref<HTMLDivElement | null>(null);
```

修改事件处理函数：

```typescript
function handleTooltipShow(data: any, chartRef: HTMLDivElement) {
  tooltipState.value = data;
  activeChartRef.value = chartRef;
}
```

- [ ] **Step 6: 添加样式**

```vue
<style scoped>
.chart-wrapper {
  position: relative;
}
</style>
```

- [ ] **Step 7: 提交代码**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "feat: index.vue 添加 ProcessTooltip 组件和事件处理"
```

---

### Task 4: 测试验证

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd web
pnpm dev
```

- [ ] **Step 2: 验证功能**

手动验证以下功能：
1. 折叠状态显示进程名 + 实例数量
2. 点击"查看详情"展开显示 PID 和使用率
3. 子进程按使用率降序排列
4. 值为 0 的实例不显示
5. 全部为 0 时隐藏子进程区块
6. 点击关闭按钮回到折叠状态
7. tooltip 定位不超出图表区域

- [ ] **Step 3: 提交测试验证记录**

如功能正常，记录到设计文档：

```bash
git add docs/superpowers/specs/2026-05-15-tooltip-process-optimization.md
git commit -m "docs: 更新设计文档添加测试验证结果"
```

---

## 测试要点

1. 折叠/展开切换正常
2. 子进程按使用率降序排列（CPU/GPU/内存各自对应）
3. 值为 0 的实例不显示
4. 全部为 0 时隐藏整个子进程区块
5. tooltip 定位正确，不超出图表区域
6. 鼠标移出时 tooltip 消失
7. 多图表场景下 tooltip 显示在对应图表内