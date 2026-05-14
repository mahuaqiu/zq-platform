---
title: Tooltip 子进程显示优化设计
date: 2026-05-15
status: draft
---

# Tooltip 子进程显示优化设计

## 背景

性能监控图表的 tooltip 目前直接显示所有子进程明细，存在以下问题：
1. 子进程列表全部展开，数据量大时显示过多
2. 子进程没有按使用率排序
3. 值为 0 的数据也会显示
4. 缺少设计文档中规划的"查看详情"折叠/展开功能

## 需求

### 功能需求
1. **排序**：子进程列表按使用率降序排列
2. **折叠/展开**：hover 显示折叠状态，点击"查看详情"展开明细
3. **过滤 0 值**：值为 0 的实例不显示，全部为 0 时隐藏整个子进程区块
4. **PID 显示**：展开状态显示每个实例的 PID

### UI 需求
- 折叠状态：显示进程名 + 实例数量（如 "chrome.exe (3个实例)"）
- 展开状态：显示每个实例的 PID + 使用率
- 折叠宽度 ~150px，展开宽度 ~180px

## 技术方案

### 方案选择：外部 Vue tooltip 组件

由于 ECharts tooltip formatter 是静态 HTML，不支持点击事件交互，采用外部 Vue tooltip 组件方案：
- 监听 ECharts 的 `mouseover` 和 `mouseout` 事件
- Vue 组件内部处理折叠/展开状态切换
- 支持复杂交互（动画、滚动、点击事件）

### 架构设计

```
ChartPanel.vue
  ├── ECharts 图表实例
  │   └── 监听 mouseover/mouseout 事件
  │   └── emit tooltip-data 事件
  │
  └── ProcessTooltip.vue（新增）
      ├── 接收 tooltip 数据
      ├── 处理折叠/展开状态
      ├── 渲染 tooltip 内容
      └── 定位在鼠标附近
```

## 实现细节

### 1. ProcessTooltip.vue 组件

**Props：**
```typescript
interface Props {
  visible: boolean;           // 是否显示
  position: { x: number; y: number };  // 定位
  data: {
    timestamp: string;        // 时间戳
    series: SeriesData[];     // 主曲线数据（系统/进程）
    processes: ProcessData[]; // 子进程数据
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
  };
}
```

**状态：**
```typescript
const expanded = ref(false);  // 折叠/展开状态
```

**数据处理：**
```typescript
// 过滤 0 值实例，按使用率降序排列
const filteredProcesses = computed(() => {
  return props.data.processes
    .map(process => ({
      name: process.name,
      instances: process.instances
        .filter(instance => getValue(instance) > 0)  // 过滤 0 值
        .sort((a, b) => getValue(b) - getValue(a))   // 降序排列
    }))
    .filter(process => process.instances.length > 0);  // 过滤空进程
});

// 检查是否有非 0 数据
const hasValidData = computed(() => {
  return filteredProcesses.value.some(p => p.instances.length > 0);
});
```

### 2. ChartPanel.vue 修改

**移除原 tooltip formatter 中的子进程显示逻辑，改为 emit 事件：**

```typescript
chartInstance.on('mouseover', (params: any) => {
  if (params.componentType === 'series') {
    const dataIndex = params.dataIndex;
    const rawDataPoint = props.rawData?.[dataIndex];
    emit('tooltip-show', {
      position: { x: params.event.offsetX, y: params.event.offsetY },
      data: rawDataPoint,
      series: params,
      chartType: props.chartType
    });
  }
});

chartInstance.on('mouseout', () => {
  emit('tooltip-hide');
});
```

**禁用原 ECharts tooltip：**
```typescript
tooltip: {
  show: false  // 禁用原 tooltip
}
```

### 3. 父组件调用

```vue
<ChartPanel
  @tooltip-show="tooltipData = $event"
  @tooltip-hide="tooltipData = null"
/>
<ProcessTooltip
  :visible="tooltipData !== null"
  :position="tooltipData?.position"
  :data="tooltipData?.data"
/>
```

## UI 设计

### 折叠状态

```
┌─────────────────────┐
│ 🕐 90s              │
│                     │
│ ■ 系统    45.2%     │
│ ■ 进程    28.5%     │
│                     │
│ chrome.exe (3个实例)│
│                     │
│ [▼ 查看详情]        │
└─────────────────────┘
```

### 展开状态

```
┌─────────────────────────────┐
│ 🕐 90s              [✕]     │
│                             │
│ ■ 系统    45.2%             │
│ ■ 进程    28.5%             │
│                             │
│ 子进程明细：                 │
│ ┌─────────────────────────┐ │
│ │ chrome.exe (PID:1234) 12.5% │ │
│ │ chrome.exe (PID:5678) 10.3% │ │
│ │ chrome.exe (PID:9012)  5.7% │ │
│ └─────────────────────────┘ │
│ 共3个子进程实例              │
└─────────────────────────────┘
```

## 测试要点

1. 折叠/展开切换正常
2. 子进程按使用率降序排列
3. 值为 0 的实例不显示
4. 全部为 0 时隐藏子进程区块
5. tooltip 定位正确，不超出图表区域
6. 鼠标移出时 tooltip 消失
7. 多图表场景下 tooltip 不冲突