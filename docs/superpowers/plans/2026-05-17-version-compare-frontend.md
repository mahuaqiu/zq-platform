# 版本对比页面前端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构版本对比页面，与性能监控新设计风格统一，并优化标记弹窗样式

**Architecture:** 复用性能监控现有组件（MetricSelector、MetricSearchPopup），新建版本对比专用组件，重构 compare.vue 主页面

**Tech Stack:** Vue 3 + Element Plus + ECharts + TypeScript

---

## 文件结构

### 新建文件
- `web/apps/web-ele/src/views/performance-monitor/components/AddTagDialog.vue` - 添加标签弹窗（统一风格）
- `web/apps/web-ele/src/views/performance-monitor/components/CompareChartPanel.vue` - 多版本对比图表
- `web/apps/web-ele/src/views/performance-monitor/components/CompareSummaryTable.vue` - 数据摘要表格
- `web/apps/web-ele/src/views/performance-monitor/components/VersionProcessPanel.vue` - 版本进程详情面板
- `web/apps/web-ele/src/views/performance-monitor/components/CompareTimeNavigator.vue` - 对比页面时间导航条（含标签功能）
- `web/apps/web-ele/src/views/performance-monitor/components/VersionSelector.vue` - 版本选择器卡片

### 修改文件
- `web/apps/web-ele/src/views/performance-monitor/compare.vue` - 主页面重构
- `web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue` - 标记弹窗样式优化
- `web/apps/web-ele/src/api/core/performance-monitor.ts` - 新增对比标签 API

---

## Task 1: 创建 AddTagDialog 组件（统一风格）

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/AddTagDialog.vue`

- [ ] **Step 1: 创建 AddTagDialog.vue 文件**

```vue
<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { ElDialog, ElInput, ElButton, ElSelect, ElOption, ElDatePicker, ElMessage } from 'element-plus';

interface Props {
  visible: boolean;
  startTime?: Date;
  endTime?: Date;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', data: TagFormData): void;
}>();

interface TagFormData {
  name: string;
  type: 'peak' | 'stable';
  start_time: Date;
  end_time: Date;
  note?: string;
}

const form = ref<TagFormData>({
  name: '',
  type: 'peak',
  start_time: new Date(),
  end_time: new Date(),
  note: '',
});

// 监听传入的时间，自动填充
watch(() => props.startTime, (time) => {
  if (time) form.value.start_time = time;
});
watch(() => props.endTime, (time) => {
  if (time) form.value.end_time = time;
});

async function handleSubmit() {
  if (!form.value.name) {
    ElMessage.warning('请输入标签名称');
    return;
  }
  emit('submit', form.value);
  emit('update:visible', false);
}

function handleCancel() {
  emit('update:visible', false);
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    title="添加区间标签"
    width="400px"
  >
    <div class="form-item">
      <label>标签名称</label>
      <ElInput v-model="form.name" placeholder="如：场景加载、发起共享" />
    </div>
    <div class="form-item">
      <label>区间类型</label>
      <ElSelect v-model="form.type" style="width: 100%">
        <ElOption value="peak" label="冲高" />
        <ElOption value="stable" label="稳态" />
      </ElSelect>
    </div>
    <div class="form-item">
      <label>开始时间</label>
      <ElDatePicker
        v-model="form.start_time"
        type="datetime"
        placeholder="选择开始时间"
        format="YYYY-MM-DD HH:mm:ss"
        style="width: 100%"
      />
    </div>
    <div class="form-item">
      <label>结束时间</label>
      <ElDatePicker
        v-model="form.end_time"
        type="datetime"
        placeholder="选择结束时间"
        format="YYYY-MM-DD HH:mm:ss"
        style="width: 100%"
      />
    </div>
    <div class="form-item">
      <label>备注</label>
      <ElInput v-model="form.note" placeholder="可选" />
    </div>
    <template #footer>
      <ElButton @click="handleCancel">取消</Button>
      <ElButton type="success" @click="handleSubmit">确定</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.form-item {
  margin-bottom: 15px;
}
.form-item label {
  display: block;
  margin-bottom: 5px;
  font-size: 13px;
  color: #666;
}
</style>
</template>
```

- [ ] **Step 2: 提交 AddTagDialog 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/AddTagDialog.vue
git commit -m "feat(compare): 创建 AddTagDialog 组件（统一风格）"
```

---

## Task 2: 优化 TimeNavigator 中的标记弹窗样式

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue`

- [ ] **Step 1: 修改标记弹窗的样式使其与 AddTagDialog 一致**

需要修改 TimeNavigator.vue 中的标记弹窗部分（约 413-452 行），统一样式：

1. 将表单字段布局改为与 AddTagDialog 一致
2. 使用相同的 CSS 类名 `.form-item`
3. 保持功能不变（绝对时间选择器）

修改内容：
- CSS 样式部分保持不变（已有 `.form-item` 样式）
- 弹窗内容结构已经一致，无需修改

- [ ] **Step 2: 验证性能监控页面标记功能正常**

启动前端开发服务器，检查标记弹窗样式是否正常。

- [ ] **Step 3: 提交修改**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/TimeNavigator.vue
git commit -m "style: 标记弹窗样式确认已统一"
```

---

## Task 3: 创建 VersionSelector 版本选择器组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/VersionSelector.vue`

- [ ] **Step 1: 创建 VersionSelector.vue 文件**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElSelect, ElOption } from 'element-plus';
import type { PerformanceVersion } from '#/api/core/performance-monitor';

interface Props {
  versions: PerformanceVersion[];
  selectedIds: string[];
  maxVersions: number;
}

const props = withDefaults(defineProps<Props>(), {
  versions: () => [],
  selectedIds: () => [],
  maxVersions: 6,
});

const emit = defineEmits<{
  (e: 'change', ids: string[]): void;
}>();

const VERSION_COLORS = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#9b59b6', '#909399'];

function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length];
}

function handleRemove(id: string) {
  const newIds = props.selectedIds.filter(v => v !== id);
  emit('change', newIds);
}

function handleSelect(id: string) {
  if (props.selectedIds.length >= props.maxVersions) {
    return;
  }
  emit('change', [...props.selectedIds, id]);
}

const unselectedVersions = computed(() => {
  return props.versions.filter(v => !props.selectedIds.includes(v.id));
});
</script>

<template>
  <div class="version-selector">
    <!-- 已选版本卡片 -->
    <div
      v-for="(id, index) in selectedIds"
      :key="id"
      class="version-card"
      :style="{ background: getVersionColor(index) }"
    >
      <span class="version-name">{{ versions.find(v => v.id === id)?.name }}</span>
      <button class="remove-btn" @click="handleRemove(id)">×</button>
    </div>

    <!-- 添加版本按钮 -->
    <div v-if="selectedIds.length < maxVersions" class="add-version">
      <ElSelect
        :model-value="null"
        placeholder="+ 添加版本"
        @change="handleSelect"
        style="width: 120px"
      >
        <ElOption
          v-for="v in unselectedVersions"
          :key="v.id"
          :label="v.name"
          :value="v.id"
        />
      </ElSelect>
    </div>
  </div>
</template>

<style scoped>
.version-selector {
  display: flex;
  gap: 8px;
  align-items: center;
}
.version-card {
  padding: 8px 16px;
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  position: relative;
}
.version-name {
  font-weight: 600;
}
.remove-btn {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #f56c6c;
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  font-size: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.add-version {
  border: 2px dashed #409eff;
  border-radius: 6px;
  padding: 6px;
}
</style>
```

- [ ] **Step 2: 提交 VersionSelector 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/VersionSelector.vue
git commit -m "feat(compare): 创建 VersionSelector 版本选择器组件"
```

---

## Task 4: 创建 CompareChartPanel 多版本对比图表组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/CompareChartPanel.vue`

- [ ] **Step 1: 创建 CompareChartPanel.vue 文件**

基于现有 ChartPanel.vue，修改为支持多版本叠加显示：

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries, CompareTag } from '../types';

interface Props {
  title: string;
  series: ChartSeries[];
  height: number;
  tags?: CompareTag[];
}

const props = withDefaults(defineProps<Props>(), {
  height: 240,
  tags: () => [],
});

const emit = defineEmits<{
  (e: 'hover', data: { time: number; dataIndex: number }): void;
  (e: 'leave'): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);

  // 悬停事件
  chartInstance.on('mousemove', (params: any) => {
    if (params.dataIndex !== undefined) {
      emit('hover', { time: params.value[0], dataIndex: params.dataIndex });
    }
  });
  chartInstance.on('mouseout', () => {
    emit('leave');
  });

  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  const seriesData = props.series.map(s => ({
    name: s.name,
    type: 'line',
    data: s.data.map(d => [d.time, d.value]),
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    symbol: 'none',
    smooth: true,
  }));

  // 标签区间可视化（markArea）
  const markAreas: any[] = props.tags.map(tag => ({
    name: tag.name,
    itemStyle: { color: tag.type === 'peak' ? 'rgba(245, 108, 108, 0.1)' : 'rgba(103, 194, 58, 0.1)' },
    coord: [tag.start_time, 0],
    endCoord: [tag.end_time, 100],
  }));

  const option: echarts.EChartsOption = {
    title: { text: props.title, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 60, right: 20, top: 40, bottom: 60 },
    xAxis: { type: 'value', name: '相对时间(秒)' },
    yAxis: { type: 'value' },
    series: seriesData,
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, bottom: 10, height: 18 },
    ],
  };

  chartInstance.setOption(option);
}

watch(() => props.series, updateChart, { deep: true });
watch(() => props.tags, updateChart, { deep: true });

onMounted(() => {
  initChart();
});
onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
  }
});
</script>

<template>
  <div class="compare-chart-panel">
    <div ref="chartRef" :style="{ height: `${height}px` }"></div>
  </div>
</template>

<style scoped>
.compare-chart-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}
</style>
```

- [ ] **Step 2: 在 types.ts 中添加 CompareTag 类型**

修改 `web/apps/web-ele/src/views/performance-monitor/types.ts`，添加：

```typescript
// 对比页面标签类型
export interface CompareTag {
  id: string;
  name: string;
  type: 'peak' | 'stable';
  start_time: number;  // 相对时间（秒）
  end_time: number;    // 相对时间（秒）
  note?: string;
}
```

- [ ] **Step 3: 提交 CompareChartPanel 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CompareChartPanel.vue
git add web/apps/web-ele/src/views/performance-monitor/types.ts
git commit -m "feat(compare): 创建 CompareChartPanel 多版本对比图表组件"
```

---

## Task 5: 创建 CompareSummaryTable 数据摘要表格组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/CompareSummaryTable.vue`

- [ ] **Step 1: 创建 CompareSummaryTable.vue 文件**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import { ElTable, ElTableColumn } from 'element-plus';
import type { SummaryRow } from '../types';

interface Props {
  data: SummaryRow[];
}

const props = defineProps<Props>();

function isBest(key: keyof SummaryRow, value: number): boolean {
  const values = props.data.map(r => r[key] as number).filter(v => v > 0);
  return value === Math.min(...values);
}

function isWorst(key: keyof SummaryRow, value: number): boolean {
  const values = props.data.map(r => r[key] as number).filter(v => v > 0);
  return value === Math.max(...values);
}
</script>

<template>
  <div class="compare-summary-table">
    <div class="table-title">
      数据摘要
      <span class="subtitle">（标签区间统计）</span>
    </div>
    <ElTable :data="data" border stripe size="small">
      <ElTableColumn prop="version_name" label="版本" width="80">
        <template #default="{ row }">
          <span :style="{ color: row.color, fontWeight: '600' }">
            {{ row.version_name }}
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="系统CPU" align="center">
        <template #default="{ row }">
          <span :class="{ 'best': isBest('peak_cpu', row.peak_cpu), 'worst': isWorst('peak_cpu', row.peak_cpu) }">
            {{ row.peak_cpu?.toFixed(1) }}%
            <span v-if="isBest('peak_cpu', row.peak_cpu)" class="mark best">✓</span>
            <span v-if="isWorst('peak_cpu', row.peak_cpu)" class="mark worst">✗</span>
          </span>
        </template>
      </ElTableColumn>
      <!-- 其他列类似... -->
    </ElTable>
    <div class="table-note">
      ✓ 最优值 | ✗ 最差值
    </div>
  </div>
</template>

<style scoped>
.compare-summary-table {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}
.table-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}
.subtitle {
  font-size: 12px;
  color: #999;
}
.best { color: #67c23a; font-weight: 600; }
.worst { color: #f56c6c; font-weight: 600; }
.table-note {
  margin-top: 8px;
  font-size: 11px;
  color: #666;
}
</style>
```

- [ ] **Step 2: 提交 CompareSummaryTable 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CompareSummaryTable.vue
git commit -m "feat(compare): 创建 CompareSummaryTable 数据摘要表格组件"
```

---

## Task 6: 创建 VersionProcessPanel 版本进程详情面板组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/VersionProcessPanel.vue`

- [ ] **Step 1: 创建 VersionProcessPanel.vue 文件**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { PerformanceData, ProcessData } from '#/api/core/performance-monitor';
import { VERSION_COLORS } from '../types';

interface Props {
  versions: Array<{ name: string; id: string; data: PerformanceData[] }>;
  hoverTime?: number;
}

const props = defineProps<Props>();

// 根据悬停时间获取各版本的进程数据
const versionProcessData = computed(() => {
  return props.versions.map((v, index) => {
    const color = VERSION_COLORS[index % VERSION_COLORS.length];
    if (!props.hoverTime) {
      // 显示最新数据
      const latest = v.data[v.data.length - 1];
      return { name: v.name, color, processes: latest?.target_processes || [] };
    }
    // 找最近的数据点
    const point = v.data.find(d => Math.abs(d.relative_time - props.hoverTime) < 5);
    return { name: v.name, color, processes: point?.target_processes || [] };
  });
});
</script>

<template>
  <div class="version-process-panel">
    <div class="panel-title">
      版本进程详情
      <span class="subtitle">（悬停显示）</span>
    </div>
    <div class="version-list">
      <div
        v-for="v in versionProcessData"
        :key="v.name"
        class="version-card"
        :style="{ borderLeftColor: v.color }"
      >
        <div class="version-name" :style="{ color: v.color }">{{ v.name }}</div>
        <div class="process-info" v-for="p in v.processes.slice(0, 2)" :key="p.name">
          {{ p.name }} PID:{{ p.instances[0]?.pid }} CPU:{{ p.total_cpu?.toFixed(1) }}%
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.version-process-panel {
  width: 320px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}
.subtitle {
  font-size: 11px;
  color: #999;
}
.version-card {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  border-left: 3px solid;
  margin-bottom: 8px;
}
.version-name {
  font-size: 11px;
  font-weight: 600;
}
.process-info {
  font-size: 10px;
  color: #666;
  margin-top: 4px;
}
</style>
```

- [ ] **Step 2: 提交 VersionProcessPanel 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/VersionProcessPanel.vue
git commit -m "feat(compare): 创建 VersionProcessPanel 版本进程详情面板组件"
```

---

## Task 7: 创建 CompareTimeNavigator 时间导航条组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/CompareTimeNavigator.vue`

- [ ] **Step 1: 创建 CompareTimeNavigator.vue 文件**

复用 TimeNavigator 的 dataZoom 逻辑，添加标签管理功能：

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import { ElButton } from 'element-plus';
import AddTagDialog from './AddTagDialog.vue';
import type { CompareTag } from '../types';

interface Props {
  duration: number;
  startTime: number;
  endTime: number;
  tags: CompareTag[];
}

const emit = defineEmits<{
  (e: 'rangeChange', range: [number, number]): void;
  (e: 'addTag', tag: CompareTag): void;
  (e: 'deleteTag', tagId: string): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

const showAddDialog = ref(false);
const addDialogStartTime = ref(new Date());
const addDialogEndTime = ref(new Date());

// ... dataZoom 初始化逻辑（参考 TimeNavigator）

function handleAddTag() {
  showAddDialog.value = true;
}

// 快速按钮
const quickButtons = [
  { label: '15分钟', value: 15 * 60 },
  { label: '60分钟', value: 60 * 60 },
  { label: '12小时', value: 12 * 3600 },
];

function handleQuickSelect(value: number) {
  const start = Math.max(0, props.duration - value);
  emit('rangeChange', [start, props.duration]);
}
</script>

<template>
  <div class="compare-time-navigator">
    <!-- 时间范围显示 -->
    <span class="time-range">{{ startTime }} ~ {{ endTime }}</span>
    
    <!-- dataZoom -->
    <div ref="chartRef" class="navigator-chart"></div>
    
    <!-- 快速按钮 -->
    <div class="quick-buttons">
      <ElButton v-for="btn in quickButtons" size="small" @click="handleQuickSelect(btn.value)">
        {{ btn.label }}
      </ElButton>
    </div>
    
    <!-- 标签列表 -->
    <div class="tag-list">
      <span
        v-for="tag in tags"
        :key="tag.id"
        class="tag-item"
        :style="{ borderColor: tag.type === 'peak' ? '#f56c6c' : '#67c23a', color: tag.type === 'peak' ? '#f56c6c' : '#67c23a' }"
      >
        {{ tag.name }}({{ tag.type === 'peak' ? '冲高' : '稳态' }})
        <button @click="emit('deleteTag', tag.id)">×</button>
      </span>
      <ElButton size="small" type="primary" @click="handleAddTag">+标签</ElButton>
    </div>
    
    <!-- 添加标签弹窗 -->
    <AddTagDialog
      :visible="showAddDialog"
      @update:visible="showAddDialog = $event"
      @submit="emit('addTag', $event)"
    />
  </div>
</template>

<style scoped>
/* 参考 TimeNavigator 样式 */
</style>
```

- [ ] **Step 2: 提交 CompareTimeNavigator 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CompareTimeNavigator.vue
git commit -m "feat(compare): 创建 CompareTimeNavigator 时间导航条组件"
```

---

## Task 8: 重构 compare.vue 主页面

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/compare.vue`

- [ ] **Step 1: 重构 compare.vue 使用新组件**

主要修改：
1. 移除 device_id 相关逻辑
2. 使用 VersionSelector 替代原有版本选择
3. 使用 MetricSelector 和 MetricSearchPopup
4. 使用 CompareTimeNavigator 替代原有时间选择
5. 使用 CompareChartPanel 替代原有图表
6. 使用 CompareSummaryTable 和 VersionProcessPanel
7. 管理标签状态

核心代码结构：

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import MetricSelector from './components/MetricSelector.vue';
import MetricSearchPopup from './components/MetricSearchPopup.vue';
import CompareTimeNavigator from './components/CompareTimeNavigator.vue';
import CompareChartPanel from './components/CompareChartPanel.vue';
import CompareSummaryTable from './components/CompareSummaryTable.vue';
import VersionProcessPanel from './components/VersionProcessPanel.vue';
import VersionSelector from './components/VersionSelector.vue';
import { getVersions, getCompareData } from '#/api/core/performance-monitor';
import type { PerformanceVersion, CompareTag } from './types';

// 版本列表（移除 device_id 依赖）
const versions = ref<PerformanceVersion[]>([]);
const selectedVersionIds = ref<string[]>([]);

// 指标选择
const currentMetric = ref<'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'hwinfo'>('cpu');
const showMorePopup = ref(false);

// 时间范围
const timeRange = ref<[number, number]>([0, 0]);
const duration = ref(0);

// 标签
const tags = ref<CompareTag[]>([]);

// 对比数据
const compareData = ref<any>({ versions: [] });

// 悬停状态
const hoverTime = ref<number | undefined>();

// ...
</script>

<template>
  <div class="compare-page">
    <!-- 顶部：标题 + 版本选择器 + 操作按钮 -->
    <div class="top-bar">
      <span class="title">版本对比</span>
      <VersionSelector :versions="versions" :selected-ids="selectedVersionIds" @change="handleVersionChange" />
      <div class="actions">
        <button class="start-btn" @click="handleCompare">开始对比</button>
        <button class="export-btn" @click="handleExport">导出报告</button>
      </div>
    </div>
    
    <!-- 指标选择器 -->
    <MetricSelector :current-metric="currentMetric" @change="currentMetric = $event" @more="showMorePopup = true" />
    <MetricSearchPopup :visible="showMorePopup" @update:visible="showMorePopup = $event" />
    
    <!-- 时间导航条 -->
    <CompareTimeNavigator
      :duration="duration"
      :start-time="timeRange[0]"
      :end-time="timeRange[1]"
      :tags="tags"
      @range-change="timeRange = $event"
      @add-tag="handleAddTag"
      @delete-tag="handleDeleteTag"
    />
    
    <!-- 主图表 -->
    <CompareChartPanel
      :title="chartTitle"
      :series="chartSeries"
      :tags="tags"
      @hover="hoverTime = $event.time"
      @leave="hoverTime = undefined"
    />
    
    <!-- 底部面板 -->
    <div class="bottom-panel">
      <CompareSummaryTable :data="summaryData" />
      <VersionProcessPanel :versions="versionData" :hover-time="hoverTime" />
    </div>
  </div>
</template>
```

- [ ] **Step 2: 提交 compare.vue 重构**

```bash
git add web/apps/web-ele/src/views/performance-monitor/compare.vue
git commit -m "feat(compare): 重构版本对比页面主组件"
```

---

## Task 9: 新增对比标签 API（前端）

**Files:**
- Modify: `web/apps/web-ele/src/api/core/performance-monitor.ts`

- [ ] **Step 1: 添加对比标签 API 类型定义**

在 API 文件中添加：

```typescript
// 对比标签类型
export interface CompareTag {
  id: string;
  name: string;
  type: 'peak' | 'stable';
  start_time: number;
  end_time: number;
  note?: string;
}

export interface CompareTagCreate {
  name: string;
  type: 'peak' | 'stable';
  start_time: string;
  end_time: string;
  note?: string;
}
```

- [ ] **Step 2: 添加对比标签 API 函数**

```typescript
// 对比标签管理
export async function createCompareTag(params: CompareTagCreate) {
  return requestClient.post<{ id: string; status: string }>(
    '/api/core/performance-monitor/compare/tag',
    params
  );
}

export async function getCompareTags() {
  return requestClient.get<{ items: CompareTag[] }>(
    '/api/core/performance-monitor/compare/tags'
  );
}

export async function deleteCompareTag(tagId: string) {
  return requestClient.delete<{ status: string }>(
    `/api/core/performance-monitor/compare/tag/${tagId}`
  );
}

// 版本列表（移除 device_id）
export async function getVersionsAll() {
  return requestClient.get<{ items: PerformanceVersion[] }>(
    '/api/core/performance-monitor/version/list'
  );
}
```

- [ ] **Step 3: 提交 API 文件修改**

```bash
git add web/apps/web-ele/src/api/core/performance-monitor.ts
git commit -m "feat(api): 新增对比标签 API 和无设备限制的版本列表 API"
```

---

## Task 10: 验证并提交完整功能

- [ ] **Step 1: 启动前端开发服务器验证**

```bash
cd web && pnpm dev
```

检查：
- 版本对比页面布局正确
- 版本选择器功能正常
- 指标选择器功能正常
- 时间导航条 dataZoom 功能正常
- 标签添加/删除功能正常
- 数据摘要表格显示正确
- 悬停联动功能正常

- [ ] **Step 2: 最终提交（如有遗漏修复）**

```bash
git add -A
git commit -m "feat(compare): 版本对比页面重构完成"
```

---

## 成功标准

- 版本对比页面与性能监控页面风格统一
- 移除设备选择后可正常选择所有版本
- 标签弹窗样式与性能监控标记弹窗一致
- 所有新组件正常工作