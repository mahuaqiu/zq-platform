# 性能监控页面重新设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构性能监控页面为单图表主导布局，新增指标选择器、重新设计时间导航条、优化目标进程明细和TOP10面板

**Architecture:** 采用 Vue 3 组合式 API，组件职责分离，状态集中在主页面管理，子组件通过 props/events 通信

**Tech Stack:** Vue 3 + Element Plus + ECharts + TypeScript

---

## 文件结构

### 新增文件
- `web/apps/web-ele/src/views/performance-monitor/components/MetricSelector.vue` - 指标选择卡片组件
- `web/apps/web-ele/src/views/performance-monitor/components/MetricSearchPopup.vue` - 更多指标搜索弹窗
- `web/apps/web-ele/src/views/performance-monitor/components/Top10Panel.vue` - TOP10进程面板（替代原Top10List）

### 修改文件
- `web/apps/web-ele/src/views/performance-monitor/index.vue` - 主页面布局重构
- `web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue` - 时间导航条重新设计
- `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue` - 图表高度调整
- `web/apps/web-ele/src/views/performance-monitor/components/ProcessDetailPanel.vue` - 固定宽度500px

### 移除文件
- `web/apps/web-ele/src/views/performance-monitor/components/AdvancedMetrics.vue` - 高级指标区域（不再使用）
- `web/apps/web-ele/src/views/performance-monitor/components/Top10List.vue` - 被Top10Panel替代

---

## Task 1: 创建 MetricSelector 组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/MetricSelector.vue`

- [ ] **Step 1: 创建 MetricSelector 组件基础结构**

```vue
<script setup lang="ts">
import { ref } from 'vue';

interface Props {
  currentMetric: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  change: [metric: string];
}>();

// 固定显示的4个指标
const mainMetrics = [
  { key: 'cpu', label: 'CPU' },
  { key: 'gpu', label: 'GPU' },
  { key: 'memory', label: '内存' },
  { key: 'commitMemory', label: '提交内存' },
];

// 更多指标弹窗显示状态
const showMorePopup = ref(false);

function handleMetricClick(metric: string) {
  emit('change', metric);
}

function handleMoreClick() {
  showMorePopup.value = true;
}
</script>

<template>
  <div class="metric-selector">
    <div class="metric-cards">
      <div
        v-for="metric in mainMetrics"
        :key="metric.key"
        :class="['metric-card', { active: currentMetric === metric.key }]"
        @click="handleMetricClick(metric.key)"
      >
        {{ metric.label }}
      </div>
      <div class="metric-card more-btn" @click="handleMoreClick">
        更多指标 ▼
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-selector {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}

.metric-cards {
  display: flex;
  gap: 8px;
  align-items: center;
}

.metric-card {
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  background: #fff;
  border: 1px solid #409eff;
  color: #409eff;
}

.metric-card.active {
  background: #409eff;
  color: white;
  border: none;
}

.more-btn {
  padding: 10px 16px;
}
</style>
```

- [ ] **Step 2: Commit MetricSelector 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/MetricSelector.vue
git commit -m "feat: 新增 MetricSelector 指标选择卡片组件"
```

---

## Task 2: 创建 MetricSearchPopup 组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/MetricSearchPopup.vue`

- [ ] **Step 1: 创建 MetricSearchPopup 组件**

```vue
<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { Close } from '@element-plus/icons-vue';

interface Props {
  visible: boolean;
  metrics: { key: string; label: string }[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:visible': [value: boolean];
  select: [metric: string];
}>();

const searchKeyword = ref('');
const recentSearches = ref<string[]>([]); // 最近搜索的3个

// 过滤后的结果
const filteredMetrics = computed(() => {
  if (!searchKeyword.value.trim()) return props.metrics;
  const keyword = searchKeyword.value.trim().toLowerCase();
  return props.metrics.filter(m => 
    m.key.toLowerCase().includes(keyword) || 
    m.label.toLowerCase().includes(keyword)
  );
});

function handleClose() {
  emit('update:visible', false);
}

function handleSelect(metric: string) {
  // 记录到最近搜索
  const recent = recentSearches.value.filter(m => m !== metric);
  recentSearches.value = [metric, ...recent].slice(0, 3);
  emit('select', metric);
  emit('update:visible', false);
}

function handleRecentClick(metric: string) {
  handleSelect(metric);
}
</script>

<template>
  <div v-if="visible" class="metric-search-popup">
    <div class="popup-header">
      <span class="popup-title">选择指标</span>
      <el-icon class="close-icon" @click="handleClose"><Close /></el-icon>
    </div>
    
    <div class="popup-search">
      <input
        v-model="searchKeyword"
        class="search-input"
        placeholder="搜索指标名称..."
      />
    </div>
    
    <div class="popup-recent">
      <span class="recent-label">最近搜索:</span>
      <div class="recent-tags">
        <span
          v-for="metric in recentSearches"
          :key="metric"
          class="recent-tag"
          @click="handleRecentClick(metric)"
        >
          {{ metrics.find(m => m.key === metric)?.label || metric }}
        </span>
      </div>
    </div>
    
    <div class="popup-results">
      <span class="results-label">搜索结果:</span>
      <div class="results-list">
        <div
          v-for="metric in filteredMetrics"
          :key="metric.key"
          class="result-item"
          @click="handleSelect(metric.key)"
        >
          <span class="result-label">{{ metric.label }}</span>
          <span class="result-key">{{ metric.key }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-search-popup {
  position: absolute;
  top: 50px;
  left: 340px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  padding: 16px;
  width: 350px;
  z-index: 100;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.popup-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.close-icon {
  color: #999;
  cursor: pointer;
  font-size: 18px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
}

.search-input:focus {
  border-color: #409eff;
}

.popup-recent {
  margin-bottom: 12px;
}

.recent-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
  display: block;
}

.recent-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.recent-tag {
  padding: 4px 10px;
  background: #e6f7ff;
  color: #409eff;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

.popup-results {
  border-top: 1px solid #eee;
  padding-top: 12px;
}

.results-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
  display: block;
}

.results-list {
  max-height: 180px;
  overflow-y: auto;
}

.result-item {
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
}

.result-item:hover {
  background: #f5f5f5;
}

.result-label {
  color: #333;
}

.result-key {
  color: #999;
  font-size: 11px;
}
</style>
```

- [ ] **Step 2: Commit MetricSearchPopup 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/MetricSearchPopup.vue
git commit -m "feat: 新增 MetricSearchPopup 更多指标搜索弹窗组件"
```

---

## Task 3: 重构 TimeNavigator 组件

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue`

- [ ] **Step 1: 阅读现有 TimeNavigator 组件**

先阅读现有组件了解当前实现。

- [ ] **Step 2: 重构 TimeNavigator 添加快速按钮和拖动导航条**

需要修改组件以支持：
- 左侧快速选择按钮（全部、5分钟、30分钟、60分钟）
- 右侧可拖动导航条
- 时间标签动态切换（>=10%分开显示，<10%合并显示）

- [ ] **Step 3: Commit TimeNavigator 重构**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue
git commit -m "feat: 重构 TimeNavigator 添加快速按钮和动态时间标签"
```

---

## Task 4: 创建 Top10Panel 组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/Top10Panel.vue`

- [ ] **Step 1: 创建 Top10Panel 组件**

固定宽度500px，显示完整10个进程排名，根据当前时间点显示数据。

```vue
<script setup lang="ts">
import { computed } from 'vue';

interface ProcessItem {
  name: string;
  value: number;
}

interface Props {
  data: ProcessItem[];
  timestamp: string;
  metric: 'cpu' | 'gpu';
}

const props = defineProps<Props>();

// 排名颜色
const rankColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399'];
const grayColors = ['#606266', '#606266', '#606266', '#606266', '#606266'];

function getRankColor(rank: number): string {
  if (rank <= 4) return rankColors[rank - 1];
  return grayColors[rank - 5];
}

// 计算最大值用于进度条
const maxValue = computed(() => {
  if (!props.data.length) return 100;
  return Math.max(...props.data.map(d => d.value));
});
</script>

<template>
  <div class="top10-panel">
    <div class="panel-header">
      <span class="panel-title">系统TOP10进程</span>
      <span class="panel-time">{{ timestamp }}</span>
    </div>
    <div class="top10-list">
      <div v-for="(item, index) in data" :key="item.name" class="top10-item">
        <span class="rank" :style="{ color: getRankColor(index + 1) }">{{ index + 1 }}</span>
        <div class="progress-bar-bg">
          <div 
            class="progress-bar" 
            :style="{ 
              width: `${(item.value / maxValue) * 100}%`,
              background: getRankColor(index + 1)
            }"
          ></div>
        </div>
        <span class="process-name">{{ item.name }}</span>
        <span class="process-value" :style="{ color: getRankColor(index + 1) }">{{ item.value }}%</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.top10-panel {
  width: 500px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
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

.top10-list {
  font-size: 11px;
}

.top10-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.rank {
  width: 16px;
}

.progress-bar-bg {
  flex: 1;
  height: 6px;
  background: #f5f5f5;
  border-radius: 2px;
}

.progress-bar {
  height: 100%;
  border-radius: 2px;
}

.process-name {
  font-weight: 500;
}

.process-value {
  white-space: nowrap;
}
</style>
```

- [ ] **Step 2: Commit Top10Panel 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/Top10Panel.vue
git commit -m "feat: 新增 Top10Panel 组件，固定500px宽度显示完整10个进程"
```

---

## Task 5: 修改 ProcessDetailPanel 组件

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/ProcessDetailPanel.vue`

- [ ] **Step 1: 阅读现有 ProcessDetailPanel**

- [ ] **Step 2: 修改为固定宽度500px**

修改组件样式，将宽度固定为500px，移除指标类型后缀（标题改为"目标进程明细"）。

- [ ] **Step 3: Commit ProcessDetailPanel 修改**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ProcessDetailPanel.vue
git commit -m "feat: ProcessDetailPanel 固定宽度500px，标题改为目标进程明细"
```

---

## Task 6: 修改 ChartPanel 组件高度

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue`

- [ ] **Step 1: 阅读现有 ChartPanel**

- [ ] **Step 2: 调整图表高度为310px-320px**

修改默认高度参数。

- [ ] **Step 3: Commit ChartPanel 修改**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/ChartPanel.vue
git commit -m "feat: ChartPanel 图表高度调整为310px"
```

---

## Task 7: 重构主页面 index.vue

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/index.vue`

这是核心重构任务，需要：
1. 引入新组件（MetricSelector、MetricSearchPopup、Top10Panel）
2. 添加 currentMetric 状态管理
3. 修改布局为单图表主导
4. 实现悬停联动逻辑
5. 移除 AdvancedMetrics

- [ ] **Step 1: 添加 currentMetric 状态和指标切换逻辑**

```typescript
// 当前选中指标
const currentMetric = ref<string>('cpu');

// 指标切换处理
function handleMetricChange(metric: string) {
  currentMetric.value = metric;
}

// 更多指标弹窗显示
const showMorePopup = ref(false);

// 所有可用指标（包括hwinfo_raw传感器）
const allMetrics = computed(() => {
  // 基础4个指标
  const base = [
    { key: 'cpu', label: 'CPU使用率' },
    { key: 'gpu', label: 'GPU使用率' },
    { key: 'memory', label: '进程内存' },
    { key: 'commitMemory', label: '提交内存' },
  ];
  // 后续从 hwinfo_raw 数据中动态添加
  return base;
});
```

- [ ] **Step 2: 根据当前指标计算图表数据**

```typescript
// 当前图表系列数据
const currentChartSeries = computed(() => {
  switch (currentMetric.value) {
    case 'cpu':
      return cpuChartSeries.value;
    case 'gpu':
      return gpuChartSeries.value;
    case 'memory':
      return memoryChartSeries.value;
    case 'commitMemory':
      return commitMemoryChartSeries.value;
    default:
      // hwinfo_raw 指标
      return [];
  }
});

// 当前图表标题
const currentChartTitle = computed(() => {
  const metric = allMetrics.value.find(m => m.key === currentMetric.value);
  return metric?.label || currentMetric.value;
});
```

- [ ] **Step 3: TOP10面板显示条件**

```typescript
// 是否显示TOP10面板
const showTop10Panel = computed(() => {
  return currentMetric.value === 'cpu' || currentMetric.value === 'gpu';
});

// 当前TOP10数据
const currentTop10Data = computed(() => {
  if (!showTop10Panel.value) return [];
  
  const latest = currentMetrics.value;
  if (!latest) return [];
  
  if (currentMetric.value === 'cpu') {
    return latest.top10_cpu?.map(p => ({ name: p.name, value: p.cpu || 0 })) || [];
  } else {
    return latest.top10_gpu?.map(p => ({ name: p.name, value: p.gpu || 0 })) || [];
  }
});
```

- [ ] **Step 4: 悬停时间点同步逻辑**

```typescript
// 悬停时间点（用于同步所有面板）
const hoverTimestamp = ref<string | null>(null);
const hoverDataPoint = ref<PerformanceData | null>(null);

// 图表悬停处理
function handleChartHover(data: { timestamp: string; dataPoint: PerformanceData }) {
  hoverTimestamp.value = data.timestamp;
  hoverDataPoint.value = data.dataPoint;
}

// 图表离开处理
function handleChartLeave() {
  hoverTimestamp.value = null;
  hoverDataPoint.value = null;
}
```

- [ ] **Step 5: 修改模板布局**

```vue
<template>
  <div class="performance-monitor">
    <!-- 顶部控制栏 -->
    <div class="control-bar">...</div>

    <!-- 指标选择器 -->
    <MetricSelector
      :currentMetric="currentMetric"
      @change="handleMetricChange"
      @more="showMorePopup = true"
    />
    <MetricSearchPopup
      v-model:visible="showMorePopup"
      :metrics="allMetrics"
      @select="handleMetricChange"
    />

    <!-- 时间导航条 -->
    <TimeNavigator ... />

    <!-- 主图表区域 -->
    <div class="chart-area">
      <ChartPanel
        :title="currentChartTitle"
        :series="currentChartSeries"
        :height="310"
        ...
        @hover="handleChartHover"
        @leave="handleChartLeave"
      />
    </div>

    <!-- 底部面板区域 -->
    <div class="bottom-panels">
      <!-- 目标进程明细 -->
      <ProcessDetailPanel
        :metric="currentMetric"
        :data="hoverDataPoint || currentMetrics"
        :timestamp="hoverTimestamp || currentTimestamp"
      />

      <!-- TOP10（仅CPU/GPU显示） -->
      <Top10Panel
        v-if="showTop10Panel"
        :data="currentTop10Data"
        :timestamp="hoverTimestamp || currentTimestamp"
        :metric="currentMetric"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 6: Commit 主页面重构**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "feat: 重构性能监控主页面为单图表主导布局"
```

---

## Task 8: 移除旧组件和代码

- [ ] **Step 1: 移除 AdvancedMetrics 引用**

从 index.vue 中移除 AdvancedMetrics 的导入和使用。

- [ ] **Step 2: 移除 Top10List 引用**

从 index.vue 中移除 Top10List 的导入和使用（已被 Top10Panel 替代）。

- [ ] **Step 3: Commit 清理**

```bash
git add web/apps/web-ele/src/views/performance-monitor/index.vue
git commit -m "refactor: 移除 AdvancedMetrics 和 Top10List 的使用"
```

---

## Task 9: 测试和验证

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd web
pnpm dev
```

- [ ] **Step 2: 手动测试页面功能**

验证：
- 指标卡片切换正常
- 时间导航条拖动正常
- 悬停联动同步正常
- TOP10面板仅在CPU/GPU显示
- 目标进程明细固定500px宽度

- [ ] **Step 3: Commit 测试完成标记**

```bash
git commit --allow-empty -m "test: 性能监控页面重构功能验证完成"
```

---

## Task 10: 最终提交

- [ ] **Step 1: 检查所有改动**

```bash
git status
git diff
```

- [ ] **Step 2: 创建最终提交**

```bash
git add -A
git commit -m "feat: 性能监控页面重新设计完成

- 新增 MetricSelector 指标选择卡片组件
- 新增 MetricSearchPopup 更多指标搜索弹窗
- 新增 Top10Panel TOP10进程面板（固定500px）
- 重构 TimeNavigator 时间导航条
- 修改 ProcessDetailPanel 固定宽度500px
- 修改 ChartPanel 图表高度310px
- 重构 index.vue 为单图表主导布局
- 移除 AdvancedMetrics 高级指标区域
- 实现悬停联动同步逻辑"
```

---

## 成功标准

- 页面布局清晰，单图表主导
- 指标切换流畅，数据同步正确
- 悬停联动实时响应
- 时间导航条美观易用，时间标签不重叠
- TOP10完整显示10个进程
- 目标进程明细和TOP10固定500px宽度