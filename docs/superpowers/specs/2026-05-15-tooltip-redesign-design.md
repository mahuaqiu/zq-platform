---
title: 性能监控 Tooltip 双区域显示设计
date: 2026-05-15
status: draft
---

# 性能监控 Tooltip 双区域显示设计

## 背景

当前性能监控图表的 tooltip 存在严重的交互问题：

**问题描述**：
- Tooltip 跟随鼠标移动太快，用户无法将鼠标移到 tooltip 上进行交互
- 点击"查看详情"按钮查看子进程数据变得不可能
- 已有的锁定机制（鼠标进入 tooltip 时停止跟随）无法解决根本问题，因为鼠标无法追上 tooltip

**根本原因**：
- Tooltip 紧贴鼠标位置，鼠标移动时 tooltip 立即跟随
- 用户无法在 tooltip 移动过程中将鼠标移入 tooltip 区域触发锁定

## 设计目标

**核心目标**：解决 tooltip 跟随鼠标太快导致的无法交互问题

**用户体验目标**：
1. Hover 时能看到基本信息（时间、主曲线数值、进程摘要）
2. Click 时能在固定位置查看完整的子进程详情
3. 大面板位置稳定，可以自由浏览子进程数据
4. 关闭面板的操作清晰便捷

## 技术方案：双区域显示

### 方案概述

采用双区域显示策略，分离 hover 和 click 的交互：

- **Hover → 小 Tooltip**：跟随鼠标显示简化信息，不做复杂交互
- **Click → 大面板**：固定位置显示完整详情，支持复杂交互

### 方案选择理由

**对比其他方案**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 延迟隐藏 + 固定距离 | 实现简单 | 仍需要追上 tooltip | 不够根本 |
| **双区域显示** | **彻底分离交互** | **布局调整** | **推荐** |
| 完全固定 tooltip | 不跟随鼠标 | 无法定位数据点 | 过于简化 |

**选择双区域显示的理由**：
- Hover 和 Click 是两种不同的交互意图，应该用不同的交互方式响应
- Hover 用于快速预览，应该轻量、跟随、不停留
- Click 用于深度查看，应该固定、完整、可操作
- 分离两者可以避免冲突，彻底解决"追不上"的问题

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│ 图表容器 (chart-wrapper)                             │
│ ┌───────────────────────────┬─────────────────────┐ │
│ │ 图表区域 (chart-area)      │ 面板区域 (panel-area)│ │
│ │                            │                     │ │
│ │  [曲线图]                  │  [子进程详情面板]  │ │
│ │                            │                     │ │
│ │  - hover: 小tooltip跟随    │  - 点击数据点后     │ │
│ │    鼠标显示基本信息         │    在此显示详情     │ │
│ │                            │                     │ │
│ │  - click: 激活右侧面板     │  - 固定320px宽     │ │
│ │                            │  - 最大400px高      │ │
│ └───────────────────────────┴─────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 核心组件划分

1. **ChartPanel.vue**（改造现有）
   - 继续处理 hover 事件，显示小 tooltip
   - 新增 click 事件处理，传递点击的数据点信息
   - 禁用原 ECharts tooltip，完全由外部组件控制

2. **MiniTooltip.vue**（新建，替代 ProcessTooltip 的 hover 部分）
   - 跟随鼠标显示，内容简化
   - 只显示基本信息，不做复杂交互
   - 离开图表时立即隐藏

3. **ProcessDetailPanel.vue**（新建，替代 ProcessTooltip 的 click 部分）
   - 固定位置在图表右侧
   - 显示完整的子进程详细数据
   - 支持关闭按钮、点击外部关闭、点击其他点切换

4. **index.vue**（父组件）
   - 管理两种 tooltip 的状态
   - 协调 ChartPanel 和两个 tooltip 组件的交互
   - 处理全局点击事件（点击外部关闭面板）

## 组件详细设计

### MiniTooltip.vue（小 tooltip）

**触发方式**：鼠标 hover 在图表数据点上

**位置策略**：
- **跟随鼠标但保持固定偏移距离**：tooltip 跟随鼠标移动，但始终保持固定距离（鼠标右侧 30px，下方 10px）
- 这样可以确保 tooltip 总是可见，不会出现"追不上"的问题
- Mini tooltip 不需要复杂交互，只是快速预览信息，所以跟随鼠标是合理的
- 离开图表数据点区域时立即隐藏

**内容显示**：

```
┌─────────────────────────┐
│ 2026-05-15 14:30:45     │  ← 实际时间
│ ────────────────────── │
│ □ 系统    45.2%         │  ← 主曲线数值（带颜色方块）
│ ■ 进程    30.1%         │
│ ────────────────────── │
│ chrome.exe (3实例)      │  ← 进程名摘要（进程名 + 实例数）
│ firefox.exe (2实例)     │
│ ────────────────────── │
│ 点击查看子进程详情      │  ← 点击提示（引导用户点击）
└─────────────────────────┘
```

**样式规格**：
- 白色背景，圆角 12px，阴影
- 字体大小：13px
- 宽度：自适应内容，约 160-180px
- 最大高度：150px，超出部分省略
- 鼠标离开图表时立即消失（无延迟）

**技术实现要点**：
- Mini tooltip 跟随鼠标移动，每次 mousemove 都更新位置（保持固定偏移距离）
- 不使用锁定机制（Mini tooltip 不需要交互，只是预览信息）
- 无展开/折叠功能（简化）
- 离开图表时立即消失（无延迟）

---

### ProcessDetailPanel.vue（大面板）

**触发方式**：点击图表数据点

**位置策略**：
- 固定显示在图表容器右侧的 `panel-area` 区域
- 每个图表容器都预留右侧空间（320px）
- 面板在该区域内显示，不影响图表宽度

**内容显示**：

```
┌───────────────────────────────────┐ × │
│ 时间: 2026-05-15 14:30:45          │   │
│ 相对时间: 90s                      │   │
│ ───────────────────────────────── │   │
│ 主曲线数值：                        │   │
│  □ 系统 CPU    45.2%               │   │
│  ■ 进程 CPU    30.1%               │   │
│ ───────────────────────────────── │   │
│ 子进程详情：                        │   │
│  chrome.exe (PID:1234)     15.2%  │   │
│  chrome.exe (PID:5678)     10.3%  │   │
│  chrome.exe (PID:9012)      4.6%  │   │
│  firefox.exe (PID:2345)     8.1%  │   │
│  node.exe (PID:7890)        2.3%  │   │
│  ...                               │   │
│ ───────────────────────────────── │   │
│ 共 5 个子进程实例                   │   │
└───────────────────────────────────┘   │
```

**样式规格**：
- 白色背景，圆角 8px，阴影
- 字体大小：13px（标题），11px（列表）
- 宽度：320px
- 高度：自适应内容，最大 400px，超出部分滚动
- 右上角关闭按钮（×）

**交互行为**：
- 点击图表其他数据点：切换显示新数据（不关闭）
- 点击关闭按钮：关闭面板
- 点击面板外部（图表或其他区域）：关闭面板
- 再次点击同一个数据点：关闭面板（toggle 行为）

**技术实现要点**：
- 子进程列表按使用率降序排列
- 过滤值为 0 的实例
- 支持滚动查看更多数据
- 淡入淡出过渡动画

## 数据流与状态管理

### 状态设计（index.vue）

```typescript
// 小 tooltip 状态（hover 触发）
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

### 事件流程

**Hover 流程（小 tooltip）**：

```
ChartPanel (mousemove on series)
    ↓ emit('mini-tooltip-show', data)  ← 每次 mousemove 都触发，更新位置
index.vue
    ↓ 更新 miniTooltipState
MiniTooltip.vue
    ↓ 接收 props，跟随鼠标显示（保持固定偏移距离）

ChartPanel (mouseout from series)
    ↓ emit('mini-tooltip-hide')
index.vue
    ↓ 清空 miniTooltipState
MiniTooltip.vue
    ↓ 立即隐藏
```

**说明**：Mini tooltip 跟随鼠标移动，但不做复杂交互，所以"追不上"的问题不会影响用户体验。

**Click 流程（大面板）**：

```
ChartPanel (click on series)
    ↓ emit('detail-click', { data, seriesData, chartType, chartKey })
index.vue
    ↓ 更新 detailPanelState + activeChartKey
ProcessDetailPanel.vue
    ↓ 接收 props，在右侧显示大面板

用户操作：
    - 点击其他数据点 → 更新 detailPanelState（切换数据）
    - 再次点击同一点 → 清空 detailPanelState（关闭面板）
    - 点击关闭按钮 → 清空 detailPanelState
    - 点击外部 → 清空 detailPanelState
```

### 关闭逻辑实现

```typescript
// index.vue

// 点击图表数据点
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

// 点击关闭按钮
function handlePanelClose() {
  detailPanelState.value = null;
  activeChartKey.value = null;
}

// 点击外部关闭（全局监听）
onMounted(() => {
  document.addEventListener('click', handleGlobalClick);
});

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick);
});

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

## 布局与样式设计

### 页面布局调整

**当前布局**：

```
┌──────────────────────────────────────┐
│ 控制栏（设备选择、按钮等）              │
├──────────────────────────────────────┤
│ 图表区域（CPU、GPU、内存等）           │
│ 图表宽度：100%容器宽度                 │
└──────────────────────────────────────┘
```

**改造后布局**：

```
┌──────────────────────────────────────┐
│ 控制栏（设备选择、按钮等）              │
├──────────────────────────────────────┤
│ 图表容器 (chart-wrapper)              │
│ ┌─────────────────────┬────────────┐ │
│ │ 图表区域 (chart-area)│ 面板区域   │ │
│ │ 宽度: calc(100%-336px)│ 宽度:320px│ │
│ └─────────────────────┴────────────┘ │
└──────────────────────────────────────┘
```

### CSS 布局实现

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
}

/* 右侧面板区域固定宽度 */
.panel-area {
  width: 320px;
  min-height: 180px;  /* 与图表高度匹配 */
  position: relative;
}

/* 大面板样式 */
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
```

### 过渡动画

**小 tooltip**：无过渡动画，立即显示/隐藏

**大面板**：淡入淡出动画

```css
/* 面板淡入淡出 */
.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
```

### 响应式处理

当屏幕宽度不足时，面板宽度减小：

```css
/* 响应式调整 */
@media (max-width: 1200px) {
  .panel-area {
    width: 280px;
  }
}

@media (max-width: 992px) {
  .panel-area {
    width: 240px;
  }
  .process-detail-panel {
    font-size: 12px;
  }
}
```

### Z-index 层级规划

```
层级规划：
- 图表区域：z-index: 1
- 小 tooltip：z-index: 100（浮动在最上层）
- 大面板：z-index: 50（低于小 tooltip）
- 关闭按钮：z-index: 51（面板内部）
```

## 实现要点

### ChartPanel.vue 改造

1. **禁用原 ECharts tooltip**：

```typescript
tooltip: {
  show: false  // 完全禁用原 tooltip
}
```

2. **新增事件监听**：

```typescript
// Hover 事件：emit 小 tooltip 数据
chartInstance.on('mouseover', (params: any) => {
  if (params.componentType === 'series') {
    const dataIndex = params.dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];

    emit('mini-tooltip-show', {
      position: { x: params.event.offsetX, y: params.event.offsetY },
      data: rawDataPoint,
      seriesData: props.series.map(s => ({
        name: s.name,
        value: s.data[dataIndex]?.value || 0,
        color: s.color,
        unit: s.unit || '%'
      })),
      chartType: props.chartType,
      containerRect: chartRef.value!.getBoundingClientRect()
    });
  }
});

// Click 事件：emit 大面板数据
chartInstance.on('click', (params: any) => {
  if (params.componentType === 'series') {
    const dataIndex = params.dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];

    emit('detail-click', {
      data: rawDataPoint,
      seriesData: props.series.map(s => ({
        name: s.name,
        value: s.data[dataIndex]?.value || 0,
        color: s.color,
        unit: s.unit || '%'
      })),
      chartType: props.chartType,
      chartKey: props.chartType  // 用 chartType 作为标识
    });
  }
});
```

### MiniTooltip.vue 实现

**Props 定义**：

```typescript
interface Props {
  visible: boolean;
  position: { x: number; y: number };
  containerRect: DOMRect | null;
  data: PerformanceData | undefined;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
}
```

**定位策略**：

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

**进程摘要显示**：

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

### ProcessDetailPanel.vue 实现

**Props 定义**：

```typescript
interface Props {
  visible: boolean;
  data: PerformanceData | null;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
}
```

**数据处理**：

```typescript
// 过滤 0 值实例，按使用率降序排列
const filteredProcesses = computed(() => {
  if (!props.data?.target_processes) return [];

  const getValue = (instance: ProcessInstance) => {
    switch (props.chartType) {
      case 'cpu': return instance.cpu;
      case 'gpu': return instance.gpu || 0;
      case 'memory': return instance.memory || 0;
      case 'commitMemory': return instance.committed_memory || 0;
      default: return instance.cpu;
    }
  };

  return props.data.target_processes
    .map(process => ({
      name: process.name,
      instances: process.instances
        .filter(instance => getValue(instance) > 0)
        .sort((a, b) => getValue(b) - getValue(a))
    }))
    .filter(process => process.instances.length > 0);
});

// 统计总实例数
const totalInstances = computed(() => {
  return filteredProcesses.value.reduce((sum, p) => sum + p.instances.length, 0);
});
```

**关闭按钮实现**：

```vue
<template>
  <div v-if="visible && data" class="process-detail-panel">
    <div class="panel-header">
      <h3>子进程详情</h3>
      <button class="close-btn" @click="emit('close')">×</button>
    </div>
    <!-- ... 内容 ... -->
  </div>
</template>
```

## 测试要点

1. **小 tooltip 测试**：
   - Hover 时显示小 tooltip，显示内容正确
   - 鼠标离开图表时立即隐藏
   - 定位正确，不超出图表区域
   - 进程摘要显示正确（进程名 + 实例数）

2. **大面板测试**：
   - Click 时显示大面板，显示内容完整
   - 子进程按使用率降序排列
   - 值为 0 的实例不显示
   - 滚动功能正常
   - 关闭按钮、点击外部关闭、点击其他点切换都正常
   - 再次点击同一点能关闭面板（toggle）

3. **交互流程测试**：
   - Hover → Click 流程顺畅
   - 小 tooltip 和大面板不冲突
   - 多图表场景下状态管理正确

4. **布局测试**：
   - 图表宽度正确（calc(100% - 336px)）
   - 面板宽度正确（320px）
   - 响应式调整正常
   - 过渡动画流畅

5. **性能测试**：
   - 频繁 hover/click 不影响性能
   - 面板滚动流畅

## 实施计划

**Phase 0: 现有代码分析**
- 分析 `ProcessTooltip.vue` 当前实现和依赖关系
- 确认哪些功能需要保留（子进程显示、排序、过滤）
- 确认哪些功能需要删除（锁定机制、展开/折叠）
- 确认迁移不会遗漏功能

**Phase 1：布局调整**
- 调整 `chart-wrapper` 布局，增加右侧面板区域
- 调整图表宽度，确保图表显示正常

**Phase 2：ChartPanel 改造**
- 禁用原 ECharts tooltip
- 新增 `mini-tooltip-show`、`mini-tooltip-hide`、`detail-click` 事件

**Phase 3：创建 MiniTooltip.vue**
- 实现小 tooltip 组件
- 实现跟随鼠标的固定偏移距离定位
- 实现进程摘要显示

**Phase 4：创建 ProcessDetailPanel.vue**
- 实现大面板组件
- 实现完整子进程详情显示
- 实现关闭逻辑

**Phase 5：父组件协调**
- 在 `index.vue` 中管理状态
- 实现全局点击事件监听
- 协调所有组件交互

**Phase 6：清理旧代码**
- 删除 `ProcessTooltip.vue`（已拆分为两个组件）
- 删除 tooltip 锁定机制相关代码
- 清理不再使用的状态变量

## 风险与注意事项

1. **布局影响**：
   - 图表宽度减小可能影响数据显示
   - 需要测试不同数据量下的图表表现
   - 响应式布局需要充分考虑

2. **性能考虑**：
   - 频繁的 hover 事件可能影响性能
   - 可以考虑添加 debounce 或 throttle
   - 面板滚动需要限制最大高度

3. **兼容性**：
   - 需要确保不影响其他模块
   - 需要测试多图表场景
   - 需要测试不同屏幕尺寸

4. **用户体验**：
   - 需要明确引导用户"点击查看详情"
   - 关闭按钮位置要明显
   - 过渡动画要流畅但不影响响应速度

## 总结

本设计通过双区域显示策略，彻底分离 hover 和 click 两种交互方式，解决了当前 tooltip 跟随鼠标太快导致无法交互的根本问题。

**关键创新点**：
1. Hover 时只显示简化的基本信息，不做复杂交互
2. Click 时在固定位置显示完整详情，支持复杂操作
3. 每个图表容器预留右侧空间，面板位置稳定不遮挡图表

**预期效果**：
- 用户可以轻松查看子进程详细数据
- 交互流程清晰：hover 预览 → click 深入查看
- 不再存在"追不上 tooltip"的问题