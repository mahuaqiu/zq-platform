# 性能监控 Tooltip 双区域显示实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将性能监控图表的tooltip改造为双区域显示：hover时显示小tooltip跟随鼠标，click时在图表右侧显示固定大面板，彻底解决tooltip跟随鼠标太快导致无法交互的问题。

**Architecture:** 采用双区域显示策略，分离hover和click交互。创建MiniTooltip.vue（小tooltip）和ProcessDetailPanel.vue（大面板）两个新组件，改造ChartPanel.vue禁用原tooltip并新增事件，在index.vue中协调状态管理。图表容器使用flex布局，右侧预留320px空间显示大面板。

**Tech Stack:** Vue 3 Composition API, TypeScript, ECharts, Element Plus

---

## 文件结构

**创建新文件：**
- `web/apps/web-ele/src/views/performance-monitor/components/MiniTooltip.vue` - 小tooltip组件，hover时跟随鼠标显示基本信息
- `web/apps/web-ele/src/views/performance-monitor/components/ProcessDetailPanel.vue` - 大面板组件，click时在右侧固定显示完整子进程详情

**修改现有文件：**
- `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue:431-482` - 禁用原ECharts tooltip，新增mini-tooltip-show、mini-tooltip-hide、detail-click事件
- `web/apps/web-ele/src/views/performance-monitor/index.vue:100-714` - 管理两种tooltip状态，协调组件交互，处理全局点击事件，调整布局结构

**删除文件：**
- `web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue` - 已拆分为MiniTooltip和ProcessDetailPanel

---

## Task 1: 现有代码分析

**目的:** 分析ProcessTooltip.vue当前实现，确认功能迁移方案

**Files:**
- Read: `web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue`
- Read: `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue:36-48,119-145`
- Read: `web/apps/web-ele/src/views/performance-monitor/index.vue:100-115,677-713`

- [ ] **Step 1: 分析ProcessTooltip.vue功能**

读取ProcessTooltip.vue完整内容，分析其功能：
- Props定义（visible, position, data等）
- 锁定机制（handleMouseEnter/handleMouseLeave）
- 折叠/展开功能（expanded状态）
- 子进程数据过滤和排序逻辑
- 进程值格式化逻辑

记录需要保留的功能：
- 子进程数据过滤（过滤0值实例）
- 子进程按使用率降序排列
- 进程值格式化（根据chartType）

记录需要删除的功能：
- 锁定机制（handleMouseEnter/handleMouseLeave emit）
- 折叠/展开功能（expanded状态，查看详情按钮）

- [ ] **Step 2: 分析ChartPanel.vue事件机制**

读取ChartPanel.vue的以下部分：
- Events定义（36-48行）- 查看现有tooltip相关events
- tooltip-show事件处理（119-145行）- 查看当前emit的数据结构
- mouseout事件处理（143-145行）

记录需要改造的部分：
- 需要禁用原ECharts tooltip（tooltip.show: false）
- 需要将tooltip-show改名为mini-tooltip-show
- 需要新增detail-click事件

- [ ] **Step 3: 分析index.vue状态管理**

读取index.vue的以下部分：
- Tooltip状态定义（100-115行）- tooltipState, tooltipLockedPosition, activeChartKey
- Tooltip事件处理函数（677-713行）- handleTooltipShow, handleTooltipHide, handleTooltipClose, handleTooltipLock, handleTooltipUnlock

记录需要改造的部分：
- 需要拆分tooltipState为miniTooltipState和detailPanelState
- 需要删除tooltipLockedPosition（锁定机制）
- 需要删除handleTooltipLock/handleTooltipUnlock函数
- 需要新增handleDetailClick, handlePanelClose, handleGlobalClick函数
- 需要新增全局点击事件监听

- [ ] **Step 4: 确认数据类型定义**

确认PerformanceData类型是否包含所需字段：
- target_processes（子进程列表）
- relative_time（相对时间）
- timestamp（实际时间）
- 进程实例包含pid、cpu、gpu、memory、committed_memory字段

确认ProcessInstance类型定义：
- pid: number
- cpu: number
- gpu?: number
- memory?: number
- committed_memory?: number

记录数据类型信息，后续实现时需要引用。

---

## Task 2: 创建MiniTooltip.vue组件

**目的:** 创建小tooltip组件，hover时跟随鼠标显示基本信息

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/MiniTooltip.vue`

- [ ] **Step 1: 创建MiniTooltip.vue基础结构**

```vue
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

// 后续添加computed和template...
</script>

<template>
  <!-- 待实现 -->
</template>

<style scoped>
/* 待实现 */
</style>
```

- [ ] **Step 2: 实现定位逻辑**

添加tooltipPosition computed：

```typescript
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
```

- [ ] **Step 3: 实现进程摘要逻辑**

添加processSummary computed：

```typescript
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
```

- [ ] **Step 4: 实现时间格式化**

添加formatDateTime函数：

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
```

- [ ] **Step 5: 实现模板内容**

实现template：

```vue
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
```

- [ ] **Step 6: 实现样式**

实现style：

```css
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
```

- [ ] **Step 7: 提交MiniTooltip组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/MiniTooltip.vue
git commit -m "feat: 创建MiniTooltip组件实现hover显示基本信息"
```

---

## Task 3: 创建ProcessDetailPanel.vue组件

**目的:** 创建大面板组件，click时在右侧固定显示完整子进程详情

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/ProcessDetailPanel.vue`

- [ ] **Step 1: 创建ProcessDetailPanel.vue基础结构**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { PerformanceData, ProcessInstance } from '#/api/core/performance-monitor';

// Props 定义
interface Props {
  visible: boolean;
  data: PerformanceData | null;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
});

const emit = defineEmits<{
  (e: 'close'): void;
}>();

// 后续添加computed和template...
</script>

<template>
  <!-- 待实现 -->
</template>

<style scoped>
/* 待实现 */
</style>
```

- [ ] **Step 2: 实现数据过滤和排序逻辑**

添加filteredProcesses和totalInstances computed：

```typescript
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
```

- [ ] **Step 3: 实现时间格式化**

添加formatDateTime函数：

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
```

- [ ] **Step 4: 实现模板内容**

实现template：

```vue
<template>
  <Transition name="panel">
    <div
      v-if="visible && data"
      class="process-detail-panel"
    >
      <!-- 头部 -->
      <div class="panel-header">
        <h3 class="panel-title">子进程详情</h3>
        <button class="close-btn" @click="emit('close')">×</button>
      </div>

      <!-- 时间信息 -->
      <div class="panel-time">
        <div class="time-row">时间: {{ formatDateTime(data.timestamp) }}</div>
        <div class="time-row">相对时间: {{ data.relative_time }}s</div>
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
  </Transition>
</template>
```

- [ ] **Step 5: 实现样式**

实现style：

```css
<style scoped>
.process-detail-panel {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  max-height: 400px;
  overflow-y: auto;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  padding: 16px;
  z-index: 50;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
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
  z-index: 51;
}

.close-btn:hover {
  background: #e8e8e8;
}

.panel-time {
  margin-bottom: 10px;
}

.time-row {
  font-size: 13px;
  color: #666;
  margin-bottom: 4px;
}

.panel-series {
  border-top: 1px dashed #eee;
  padding-top: 10px;
  margin-bottom: 10px;
}

.series-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
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

.panel-processes {
  border-top: 1px dashed #eee;
  padding-top: 10px;
}

.processes-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.processes-list {
  max-height: 200px;
  overflow-y: auto;
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
  margin-top: 8px;
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
```

- [ ] **Step 6: 提交ProcessDetailPanel组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ProcessDetailPanel.vue
git commit -m "feat: 创建ProcessDetailPanel组件实现click显示完整子进程详情"
```

---

## Task 4: 改造ChartPanel.vue

**目的:** 禁用原ECharts tooltip，新增mini-tooltip-show、mini-tooltip-hide、detail-click事件

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue`

- [ ] **Step 1: 修改Events定义**

修改ChartPanel.vue的Events定义部分（36-48行），将tooltip-show改名为mini-tooltip-show，新增detail-click事件：

```typescript
// 定义 Events
const emit = defineEmits<{
  (e: 'point-click', data: { time: number; collectId: string }): void;
  (e: 'tag-delete', tagId: string): void;
  (e: 'mini-tooltip-show', data: {
    position: { x: number; y: number };
    data: PerformanceData | undefined;
    seriesData: { name: string; value: number; color: string; unit: string }[];
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
    containerRect: DOMRect;
  }): void;
  (e: 'mini-tooltip-hide'): void;
  (e: 'detail-click', data: {
    data: PerformanceData | undefined;
    seriesData: { name: string; value: number; color: string; unit: string }[];
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
    chartKey: string;
  }): void;
}>();
```

- [ ] **Step 2: 禁用原ECharts tooltip**

修改updateChart函数中的tooltip配置（约345-393行），禁用原tooltip：

```typescript
const option = {
  tooltip: {
    show: false  // 完全禁用原 tooltip
  },
  // ... 其他配置保持不变
};
```

- [ ] **Step 3: 修改initChart函数中的事件监听**

修改initChart函数中的事件监听部分（约119-145行），将tooltip-show改名为mini-tooltip-show，新增detail-click事件：

```typescript
// 监听鼠标移动事件，传递数据给外部 mini tooltip
chartInstance.on('mousemove', (params: any) => {
  if (params.componentType === 'series') {
    const dataIndex = params.dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];

    // 构建主曲线数据
    const seriesData = props.series.map((s) => ({
      name: s.name,
      value: s.data[dataIndex]?.value || 0,
      color: s.color,
      unit: s.unit || '%',
    }));

    emit('mini-tooltip-show', {
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
  emit('mini-tooltip-hide');
});

// 监听点击事件，传递数据给外部 detail panel
chartInstance.on('click', (params: any) => {
  if (params.componentType === 'series') {
    const dataIndex = params.dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];

    // 构建主曲线数据
    const seriesData = props.series.map((s) => ({
      name: s.name,
      value: s.data[dataIndex]?.value || 0,
      color: s.color,
      unit: s.unit || '%',
    }));

    emit('detail-click', {
      data: rawDataPoint,
      seriesData,
      chartType: props.chartType,
      chartKey: props.chartType,  // 用 chartType 作为标识
    });
  }
});
```

- [ ] **Step 4: 提交ChartPanel改造**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue
git commit -m "refactor: ChartPanel禁用原tooltip，新增mini-tooltip和detail-click事件"
```

---

## Task 5: 改造index.vue状态管理

**目的:** 管理两种tooltip状态，协调组件交互，处理全局点击事件

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: 修改Tooltip状态定义**

修改index.vue的Tooltip状态定义部分（约100-115行），拆分tooltipState为miniTooltipState和detailPanelState，删除tooltipLockedPosition：

```typescript
// 小 Tooltip 状态（hover 触发）
interface MiniTooltipState {
  position: { x: number; y: number };
  data: PerformanceData | undefined;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
  containerRect: DOMRect;
}
const miniTooltipState = ref<MiniTooltipState | null>(null);

// 大面板状态（click 触发）
interface DetailPanelState {
  data: PerformanceData;  // 点击的数据点完整数据
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
  chartKey: string;  // 标识是哪个图表（cpu/gpu/memory/commitMemory）
}
const detailPanelState = ref<DetailPanelState | null>(null);
const activeChartKey = ref<string | null>(null);  // 当前激活的图表
```

删除：
```typescript
// 删除以下代码
const tooltipLockedPosition = ref<{ x: number; y: number } | null>(null);
```

- [ ] **Step 2: 修改Tooltip事件处理函数**

修改index.vue的Tooltip事件处理函数部分（约677-713行），删除旧函数，添加新函数：

```typescript
// 小 Tooltip 显示事件处理
function handleMiniTooltipShow(data: MiniTooltipState, chartKey: string) {
  miniTooltipState.value = data;
}

// 小 Tooltip 隐藏事件处理
function handleMiniTooltipHide() {
  miniTooltipState.value = null;
}

// 大面板点击事件处理
function handleDetailClick(data: DetailPanelState, chartKey: string) {
  // 如果点击的是同一个数据点，关闭面板（toggle）
  if (detailPanelState.value?.data.relative_time === data.data.relative_time
      && activeChartKey.value === chartKey) {
    detailPanelState.value = null;
    activeChartKey.value = null;
  } else {
    // 否则，切换显示新数据
    detailPanelState.value = data;
    activeChartKey.value = chartKey;
  }
}

// 大面板关闭事件处理
function handlePanelClose() {
  detailPanelState.value = null;
  activeChartKey.value = null;
}
```

删除：
```typescript
// 删除以下函数
function handleTooltipShow(data: TooltipState, chartKey: string) { ... }
function handleTooltipHide() { ... }
function handleTooltipClose() { ... }
function handleTooltipLock() { ... }
function handleTooltipUnlock() { ... }
```

- [ ] **Step 3: 添加全局点击事件监听**

在onMounted和onUnmounted部分添加全局点击事件监听：

```typescript
onMounted(() => {
  // ... 原有代码
  document.addEventListener('click', handleGlobalClick);
});

onUnmounted(() => {
  // ... 原有代码
  document.removeEventListener('click', handleGlobalClick);
});

// 全局点击事件处理
function handleGlobalClick(e: MouseEvent) {
  // 如果面板显示，且点击的不是图表区域或面板区域
  const target = e.target as HTMLElement;
  if (detailPanelState.value) {
    const isClickInChart = target.closest('.chart-area');
    const isClickInPanel = target.closest('.process-detail-panel');
    if (!isClickInChart && !isClickInPanel) {
      detailPanelState.value = null;
      activeChartKey.value = null;
    }
  }
}
```

- [ ] **Step 4: 提交index.vue状态管理改造**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "refactor: index.vue拆分tooltip状态，新增全局点击事件监听"
```

---

## Task 6: 改造index.vue布局和组件引用

**目的:** 调整布局结构，引入MiniTooltip和ProcessDetailPanel组件

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

- [ ] **Step 1: 导入新组件**

在script setup部分导入新组件：

```typescript
import MiniTooltip from './components/MiniTooltip.vue';
import ProcessDetailPanel from './components/ProcessDetailPanel.vue';
```

删除ProcessTooltip导入：
```typescript
// 删除以下导入
import ProcessTooltip from './components/ProcessTooltip.vue';
```

- [ ] **Step 2: 修改template布局结构**

修改template中的图表容器布局（约796-895行），每个图表容器改为flex布局：

找到CPU图表部分（约796-812行），修改为：

```vue
<!-- CPU使用率图表 -->
<div class="chart-wrapper">
  <div class="chart-area">
    <ChartPanel
      title="CPU使用率"
      :series="cpuChartSeries"
      :height="180"
      :raw-data="filteredPerformanceData"
      :markers="markers"
      chart-type="cpu"
      @point-click="handlePointClick"
      @mini-tooltip-show="(data) => handleMiniTooltipShow(data, 'cpu')"
      @mini-tooltip-hide="handleMiniTooltipHide"
      @detail-click="(data) => handleDetailClick(data, 'cpu')"
    />
    <MiniTooltip
      v-if="miniTooltipState && activeChartKey === 'cpu'"
      :visible="miniTooltipState !== null"
      :position="miniTooltipState.position"
      :containerRect="miniTooltipState.containerRect"
      :data="miniTooltipState.data"
      :seriesData="miniTooltipState.seriesData"
      :chartType="miniTooltipState.chartType"
    />
  </div>
  <div class="panel-area">
    <ProcessDetailPanel
      v-if="detailPanelState && activeChartKey === 'cpu'"
      :visible="detailPanelState !== null"
      :data="detailPanelState.data"
      :seriesData="detailPanelState.seriesData"
      :chartType="detailPanelState.chartType"
      @close="handlePanelClose"
    />
  </div>
</div>
```

同样的修改应用到GPU图表、提交内存图表、内存图表（约815-895行）。

- [ ] **Step 3: 添加布局样式**

在style部分添加新的布局样式：

```css
/* 图表容器使用 flex 布局 */
.chart-wrapper {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

/* 图表区域自适应宽度 */
.chart-area {
  flex: 1;
  min-width: 0;  /* 防止 flex 溢出 */
  position: relative;
}

/* 右侧面板区域固定宽度 */
.panel-area {
  width: 320px;
  min-height: 180px;  /* 与图表高度匹配 */
  position: relative;
}
```

- [ ] **Step 4: 提交布局改造**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "refactor: index.vue调整布局为flex结构，引入新tooltip组件"
```

---

## Task 7: 清理旧代码

**目的:** 删除ProcessTooltip.vue和tooltip锁定机制相关代码

**Files:**
- Delete: `web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue`

- [ ] **Step 1: 删除ProcessTooltip.vue**

```bash
rm web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue
git add web/apps/web-ele/src/views/performance-monitor/components/ProcessTooltip.vue
```

- [ ] **Step 2: 确认index.vue无ProcessTooltip引用**

确认index.vue中没有以下代码：
- ProcessTooltip组件导入
- tooltipLockedPosition状态变量
- handleTooltipLock/handleTooltipUnlock函数
- ProcessTooltip组件在template中的使用

如有残留，手动清理。

- [ ] **Step 3: 提交清理**

```bash
git commit -m "refactor: 删除ProcessTooltip.vue和tooltip锁定机制代码"
```

---

## Task 8: 测试与验证

**目的:** 测试双区域tooltip功能是否正常工作

**Files:**
- Test: 浏览器测试

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd web
pnpm dev
```

访问性能监控页面，确认页面正常加载。

- [ ] **Step 2: 测试小tooltip功能**

测试hover功能：
1. 鼠标hover在图表数据点上
2. 确认小tooltip显示（跟随鼠标，保持固定偏移距离）
3. 确认显示内容：实际时间、主曲线数值、进程摘要、点击提示
4. 鼠标离开图表，确认tooltip立即隐藏

如功能不正常，检查MiniTooltip组件和事件传递。

- [ ] **Step 3: 测试大面板功能**

测试click功能：
1. 点击图表数据点
2. 确认大面板显示在图表右侧
3. 确认显示内容：时间、主曲线数值、子进程详情（按使用率降序）
4. 确认值为0的实例不显示
5. 点击关闭按钮，确认面板关闭
6. 点击面板外部，确认面板关闭
7. 点击其他数据点，确认面板切换显示新数据
8. 再次点击同一个数据点，确认面板关闭（toggle）

如功能不正常，检查ProcessDetailPanel组件和状态管理。

- [ ] **Step 4: 测试布局**

测试布局：
1. 确认图表宽度正确（自适应，右侧留320px空间）
2. 确认面板宽度正确（320px）
3. 确认面板不遮挡图表
4. 调整浏览器窗口大小，确认响应式布局正常
5. 确认多个图表同时显示面板时布局正常

如布局有问题，检查CSS样式。

- [ ] **Step 5: 测试交互流程**

测试完整交互流程：
1. Hover图表查看基本信息
2. Click数据点查看完整详情
3. 浏览子进程数据
4. 关闭面板
5. Hover其他图表
6. Click其他图表数据点

确认流程顺畅，无明显卡顿或延迟。

- [ ] **Step 6: 提交测试验证**

如所有测试通过，提交最终版本：

```bash
git status
git log --oneline -10
```

确认所有提交记录正确。

---

## Task 9: 文档更新

**目的:** 更新设计文档状态为completed

**Files:**
- Modify: `docs/superpowers/specs/2026-05-15-tooltip-redesign-design.md`

- [ ] **Step 1: 更新设计文档状态**

修改设计文档头部：

```markdown
---
title: 性能监控 Tooltip 双区域显示设计
date: 2026-05-15
status: completed
---
```

- [ ] **Step 2: 提交文档更新**

```bash
git add docs/superpowers/specs/2026-05-15-tooltip-redesign-design.md
git commit -m "docs: 更新tooltip双区域显示设计文档状态为completed"
```

---

## 注意事项

1. **布局影响测试**：图表宽度减小可能影响数据显示，需要在不同数据量下测试图表表现
2. **性能考虑**：频繁的hover事件可能影响性能，可以考虑添加debounce（但设计文档中未要求）
3. **多图表场景**：需要测试多个图表同时显示面板时的状态管理
4. **响应式布局**：需要测试不同屏幕尺寸下的布局表现
5. **过渡动画**：大面板的淡入淡出动画要流畅但不影响响应速度

---

## 总结

本计划通过9个Task，将性能监控tooltip改造为双区域显示：
- Task 1-3: 创建新组件（MiniTooltip, ProcessDetailPanel）
- Task 4-5: 改造现有组件（ChartPanel, index.vue）
- Task 6-7: 调整布局和清理旧代码
- Task 8: 测试验证
- Task 9: 文档更新

预期完成后，用户可以：
- Hover时快速预览基本信息（小tooltip跟随鼠标）
- Click时深入查看完整详情（大面板固定在右侧）
- 不再存在"追不上tooltip"的问题