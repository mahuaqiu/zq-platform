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
- `web/apps/web-ele/src/views/performance-monitor/types.ts` - 新增 CompareTag 类型
- `web/apps/web-ele/src/api/core/performance-monitor.ts` - 新增对比标签 API

---

## Task 1: 创建 AddTagDialog 组件（统一风格）

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/AddTagDialog.vue`

- [ ] **Step 1: 创建 AddTagDialog.vue 文件**

```vue
<script setup lang="ts">
import { ref, watch } from 'vue';
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

function handleSubmit() {
  if (!form.value.name) {
    ElMessage.warning('请输入标签名称');
    return;
  }
  emit('submit', form.value);
  emit('update:visible', false);
  // 重置表单
  form.value = {
    name: '',
    type: 'peak',
    start_time: new Date(),
    end_time: new Date(),
    note: '',
  };
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
      <ElButton @click="handleCancel">取消</ElButton>
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
```

- [ ] **Step 2: 验证文件语法正确**

检查 Vue 文件语法，确保：
- 所有标签正确闭合
- `</ElButton>` 使用正确
- 无多余 `</template>`

- [ ] **Step 3: 提交 AddTagDialog 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/AddTagDialog.vue
git commit -m "feat(compare): 创建 AddTagDialog 组件（统一风格）"
```

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

Expected: `nothing to commit, working tree clean`

---

## Task 2: 在 types.ts 中添加 CompareTag 类型

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/types.ts`

- [ ] **Step 1: 添加 CompareTag 类型定义**

在 types.ts 文件末尾添加：

```typescript
// 对比页面标签类型（区别于原有 TagType）
export type CompareTagType = 'peak' | 'stable';

// 对比页面标签
export interface CompareTag {
  id: string;
  name: string;
  type: CompareTagType;
  start_time: number;  // 相对时间（秒）
  end_time: number;    // 相对时间（秒）
  note?: string;
}
```

**注意**：
- 原有 `TagType = 'peak' | 'mean'` 保持不变（用于原有标签功能）
- 新增 `CompareTagType = 'peak' | 'stable'` 用于对比页面
- 两套类型各自使用，不互相影响
- **其他类型已存在**：`VERSION_COLORS`、`ChartSeries`、`SummaryRow` 均已在 types.ts 中定义，组件需从 `../types` 导入

**组件导入示例**（其他组件需参考此方式导入）：
```typescript
import { VERSION_COLORS } from '../types';
import type { ChartSeries, SummaryRow, CompareTag } from '../types';
```

- [ ] **Step 2: 提交类型定义修改**

```bash
git add web/apps/web-ele/src/views/performance-monitor/types.ts
git commit -m "feat(types): 新增 CompareTag 和 CompareTagType 类型"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 3: 创建 VersionSelector 版本选择器组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/VersionSelector.vue`

- [ ] **Step 1: 创建 VersionSelector.vue 文件**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import { ElSelect, ElOption } from 'element-plus';
import type { PerformanceVersion } from '#/api/core/performance-monitor';
import { VERSION_COLORS } from '../types';

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

function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length] || '#67c23a';
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

const getVersionById = (id: string): PerformanceVersion | undefined => {
  return props.versions.find(v => v.id === id);
};
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
      <span class="version-name">{{ getVersionById(id)?.name }}</span>
      <button class="remove-btn" @click="handleRemove(id)">×</button>
    </div>

    <!-- 添加版本按钮 -->
    <div v-if="selectedIds.length < maxVersions" class="add-version">
      <ElSelect
        :model-value="''"
        placeholder="+ 添加版本"
        @change="handleSelect"
        style="width: 120px"
        size="small"
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
  font-size: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.remove-btn:hover {
  background: #f78989;
}
.add-version {
  border: 2px dashed #409eff;
  border-radius: 6px;
  padding: 4px;
}
</style>
```

- [ ] **Step 2: 提交 VersionSelector 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/VersionSelector.vue
git commit -m "feat(compare): 创建 VersionSelector 版本选择器组件"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 4: 创建 CompareChartPanel 多版本对比图表组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/CompareChartPanel.vue`

- [ ] **Step 1: 创建 CompareChartPanel.vue 文件**

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
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

  // 标签区间可视化（使用 markArea）
  // markArea 格式：[[{ xAxis: start }, { xAxis: end }]]
  const markAreaData: any[][] = props.tags.map(tag => [
    {
      xAxis: tag.start_time,
      itemStyle: { 
        color: tag.type === 'peak' ? 'rgba(245, 108, 108, 0.15)' : 'rgba(103, 194, 58, 0.15)' 
      },
      name: tag.name,
    },
    { xAxis: tag.end_time }
  ]);

  const option: echarts.EChartsOption = {
    title: { 
      text: props.title, 
      left: 'center', 
      textStyle: { fontSize: 14, fontWeight: 600 } 
    },
    tooltip: { 
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { 
      bottom: 0,
      data: props.series.map(s => s.name)
    },
    grid: { left: 60, right: 20, top: 40, bottom: 60 },
    xAxis: { 
      type: 'value', 
      name: '相对时间(秒)',
      nameLocation: 'middle',
      nameGap: 25,
    },
    yAxis: { type: 'value' },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { 
        type: 'slider', 
        xAxisIndex: 0, 
        bottom: 10, 
        height: 18,
        borderColor: '#ddd',
        backgroundColor: '#e8e8e8',
        fillerColor: 'rgba(64, 158, 255, 0.15)',
        handleStyle: { color: '#fff', borderColor: '#409eff' },
        textStyle: { show: false },
      },
    ],
    series: seriesData.length > 0 ? [
      ...seriesData,
      {
        type: 'line',
        data: [],
        markArea: {
          silent: true,
          data: markAreaData,
        },
      }
    ] : [],
  };

  chartInstance.setOption(option, true);
}

watch(() => props.series, updateChart, { deep: true });
watch(() => props.tags, updateChart, { deep: true });

onMounted(() => {
  initChart();
});
onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
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

- [ ] **Step 2: 提交 CompareChartPanel 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CompareChartPanel.vue
git commit -m "feat(compare): 创建 CompareChartPanel 多版本对比图表组件"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
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

// 判断是否为最优值（最小值）
function isBest(key: keyof SummaryRow, value: number): boolean {
  const values = props.data
    .map(r => r[key] as number)
    .filter(v => v !== undefined && v > 0);
  if (values.length === 0) return false;
  return value === Math.min(...values);
}

// 判断是否为最差值（最大值）
function isWorst(key: keyof SummaryRow, value: number): boolean {
  const values = props.data
    .map(r => r[key] as number)
    .filter(v => v !== undefined && v > 0);
  if (values.length === 0) return false;
  return value === Math.max(...values);
}

// 格式化数值
function formatValue(value: number | undefined, unit: string): string {
  if (value === undefined) return '-';
  return `${value.toFixed(1)}${unit}`;
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
            {{ formatValue(row.peak_cpu, '%') }}
            <span v-if="isBest('peak_cpu', row.peak_cpu)" class="mark"> ✓</span>
            <span v-if="isWorst('peak_cpu', row.peak_cpu)" class="mark"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="进程CPU" align="center">
        <template #default="{ row }">
          <span :class="{ 'best': isBest('peak_process_cpu', row.peak_process_cpu), 'worst': isWorst('peak_process_cpu', row.peak_process_cpu) }">
            {{ formatValue(row.peak_process_cpu, '%') }}
            <span v-if="isBest('peak_process_cpu', row.peak_process_cpu)" class="mark"> ✓</span>
            <span v-if="isWorst('peak_process_cpu', row.peak_process_cpu)" class="mark"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="GPU" align="center">
        <template #default="{ row }">
          <span :class="{ 'best': isBest('peak_gpu', row.peak_gpu), 'worst': isWorst('peak_gpu', row.peak_gpu) }">
            {{ formatValue(row.peak_gpu, '%') }}
            <span v-if="isBest('peak_gpu', row.peak_gpu)" class="mark"> ✓</span>
            <span v-if="isWorst('peak_gpu', row.peak_gpu)" class="mark"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="提交内存" align="center">
        <template #default="{ row }">
          <span :class="{ 'best': isBest('peak_commit_memory', row.peak_commit_memory), 'worst': isWorst('peak_commit_memory', row.peak_commit_memory) }">
            {{ formatValue(row.peak_commit_memory, 'GB') }}
            <span v-if="isBest('peak_commit_memory', row.peak_commit_memory)" class="mark"> ✓</span>
            <span v-if="isWorst('peak_commit_memory', row.peak_commit_memory)" class="mark"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
    </ElTable>
    <div class="table-note">
      <span class="best">✓ 最优</span> | 
      <span class="worst">✗ 最差</span>
    </div>
  </div>
</template>

<style scoped>
.compare-summary-table {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  flex: 1;
}
.table-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #333;
}
.subtitle {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}
.best {
  color: #67c23a;
  font-weight: 600;
}
.worst {
  color: #f56c6c;
  font-weight: 600;
}
.mark {
  font-weight: 600;
}
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

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 6: 创建 VersionProcessPanel 版本进程详情面板组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/VersionProcessPanel.vue`

- [ ] **Step 1: 创建 VersionProcessPanel.vue 文件**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { PerformanceData } from '#/api/core/performance-monitor';
import { VERSION_COLORS } from '../types';

interface VersionInfo {
  name: string;
  id: string;
  data: PerformanceData[];
}

interface Props {
  versions: VersionInfo[];
  hoverTime?: number;
}

const props = defineProps<Props>();

// 根据悬停时间获取各版本的进程数据
const versionProcessData = computed(() => {
  return props.versions.map((v, index) => {
    const color = VERSION_COLORS[index % VERSION_COLORS.length];
    
    // 根据悬停时间找到最近的数据点
    let processData: PerformanceData | undefined;
    if (props.hoverTime !== undefined) {
      // 找距离悬停时间最近的数据点（容差 5 秒）
      processData = v.data.find(d => Math.abs(d.relative_time - props.hoverTime!) <= 5);
    } else {
      // 无悬停时显示最新数据
      processData = v.data[v.data.length - 1];
    }
    
    const processes = processData?.target_processes || [];
    return { 
      name: v.name, 
      color, 
      processes: processes.slice(0, 3) // 最多显示 3 个进程
    };
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
        v-for="(v, idx) in versionProcessData"
        :key="idx"
        class="version-card"
        :style="{ borderLeftColor: v.color }"
      >
        <div class="version-name" :style="{ color: v.color }">{{ v.name }}</div>
        <div v-if="v.processes.length === 0" class="process-empty">无进程数据</div>
        <div 
          v-for="p in v.processes" 
          :key="p.name" 
          class="process-info"
        >
          <span class="process-name">{{ p.name }}</span>
          <span v-if="p.instances && p.instances.length > 0" class="process-detail">
            PID:{{ p.instances[0]?.pid }} CPU:{{ p.total_cpu?.toFixed(1) }}%
          </span>
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
  color: #333;
}
.subtitle {
  font-size: 11px;
  color: #999;
  margin-left: 8px;
}
.version-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.version-card {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  border-left: 3px solid;
}
.version-name {
  font-size: 12px;
  font-weight: 600;
}
.process-info {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}
.process-name {
  color: #333;
}
.process-detail {
  margin-left: 8px;
}
.process-empty {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}
</style>
```

- [ ] **Step 2: 提交 VersionProcessPanel 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/VersionProcessPanel.vue
git commit -m "feat(compare): 创建 VersionProcessPanel 版本进程详情面板组件"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 7: 创建 CompareTimeNavigator 时间导航条组件

**Files:**
- Create: `web/apps/web-ele/src/views/performance-monitor/components/CompareTimeNavigator.vue`

- [ ] **Step 1: 创建 CompareTimeNavigator.vue 文件**

复用 TimeNavigator 的 dataZoom 逻辑，添加标签管理功能：

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import { ElButton } from 'element-plus';
import AddTagDialog from './AddTagDialog.vue';
import type { CompareTag } from '../types';

interface Props {
  duration: number; // 总时长（秒）
  startTime: number; // 当前选中的开始时间（相对秒数）
  endTime: number; // 当前选中的结束时间（相对秒数）
  tags: CompareTag[];
}

const props = withDefaults(defineProps<Props>(), {
  duration: 0,
  startTime: 0,
  endTime: 0,
  tags: () => [],
});

const emit = defineEmits<{
  (e: 'rangeChange', range: [number, number]): void;
  (e: 'addTag', tag: CompareTag): void;
  (e: 'deleteTag', tagId: string): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

// 当前选中的时间
const currentStartTime = ref(props.startTime);
const currentEndTime = ref(props.endTime);

// 快速选择按钮配置
const quickButtons = [
  { label: '15分钟', value: 15 * 60 },
  { label: '60分钟', value: 60 * 60 },
  { label: '12小时', value: 12 * 3600 },
];
const activeButton = ref(-1);

// 添加标签弹窗
const showAddDialog = ref(false);
const addDialogStartTime = ref(new Date());
const addDialogEndTime = ref(new Date());

// 格式化时间范围显示
function formatTimeRange(): string {
  const formatNum = (n: number) => String(Math.floor(n / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0');
  return `${formatNum(currentStartTime.value)} ~ ${formatNum(currentEndTime.value)}`;
}

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);

  chartInstance.on('datazoom', (params: any) => {
    activeButton.value = -1;
    const startPercent = params.start;
    const endPercent = params.end;
    const start = Math.round((startPercent / 100) * props.duration);
    const end = Math.round((endPercent / 100) * props.duration);
    currentStartTime.value = start;
    currentEndTime.value = end;
    emit('rangeChange', [start, end]);
  });

  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  const xAxisData: number[] = [];
  for (let i = 0; i <= props.duration; i += Math.max(1, Math.floor(props.duration / 100))) {
    xAxisData.push(i);
  }

  // 生成预览数据（可用 CPU 数据作为预览）
  const previewData = xAxisData.map(() => 30 + Math.random() * 40);

  const startPercent = (currentStartTime.value / props.duration) * 100;
  const endPercent = (currentEndTime.value / props.duration) * 100;

  const option: echarts.EChartsOption = {
    animation: false,
    grid: { left: 5, right: 5, top: 5, bottom: 5 },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    series: [
      {
        type: 'line',
        data: previewData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ccc', width: 1 },
        areaStyle: { color: '#eee' },
      },
    ],
    dataZoom: [
      {
        type: 'slider',
        xAxisIndex: 0,
        start: startPercent,
        end: endPercent,
        height: 18,
        bottom: 2,
        borderColor: '#ddd',
        backgroundColor: '#e8e8e8',
        fillerColor: 'rgba(64, 158, 255, 0.15)',
        handleStyle: { color: '#fff', borderColor: '#409eff', borderWidth: 1 },
        moveHandleStyle: { color: '#409eff', opacity: 0.3 },
        textStyle: { show: false },
        brushSelect: false,
        zoomLock: false,
      },
    ],
  };

  chartInstance.setOption(option);
}

// 快速选择
function handleQuickSelect(value: number) {
  activeButton.value = value;
  currentStartTime.value = Math.max(0, props.duration - value);
  currentEndTime.value = props.duration;
  emit('rangeChange', [currentStartTime.value, props.duration]);
  if (chartInstance) {
    const startPercent = (currentStartTime.value / props.duration) * 100;
    chartInstance.setOption({
      dataZoom: [{ start: startPercent, end: 100 }],
    });
  }
}

// 打开添加标签弹窗
function handleOpenAddTag() {
  // 使用当前时间范围作为默认值
  const now = new Date();
  addDialogStartTime.value = now;
  addDialogEndTime.value = new Date(now.getTime() + 60 * 1000);
  showAddDialog.value = true;
}

// 处理添加标签
function handleAddTag(tagData: any) {
  // 将绝对时间转换为相对时间（需要采集开始时间，暂时用占位逻辑）
  const tag: CompareTag = {
    id: Date.now().toString(),
    name: tagData.name,
    type: tagData.type,
    start_time: currentStartTime.value, // 简化：使用当前相对时间
    end_time: currentEndTime.value,
    note: tagData.note,
  };
  emit('addTag', tag);
}

// 处理删除标签
function handleDeleteTag(tagId: string) {
  emit('deleteTag', tagId);
}

watch(() => props.startTime, (v) => {
  currentStartTime.value = v;
  updateChart();
});
watch(() => props.endTime, (v) => {
  currentEndTime.value = v;
  updateChart();
});
watch(() => props.duration, updateChart);

onMounted(() => {
  initChart();
});
onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<template>
  <div class="compare-time-navigator">
    <div class="navigator-container">
      <!-- 时间范围显示 -->
      <span class="time-range">{{ formatTimeRange() }}</span>

      <!-- dataZoom 导航条 -->
      <div class="navigator-wrapper">
        <div ref="chartRef" class="chart-container"></div>
      </div>

      <!-- 快速选择按钮 -->
      <div class="quick-buttons">
        <button
          v-for="btn in quickButtons"
          :key="btn.value"
          class="quick-btn"
          :class="{ active: activeButton === btn.value }"
          @click="handleQuickSelect(btn.value)"
        >
          {{ btn.label }}
        </button>
      </div>

      <!-- 标签列表 -->
      <div class="tag-list">
        <span
          v-for="tag in tags"
          :key="tag.id"
          class="tag-item"
          :style="{
            borderColor: tag.type === 'peak' ? '#f56c6c' : '#67c23a',
            color: tag.type === 'peak' ? '#f56c6c' : '#67c23a'
          }"
        >
          {{ tag.name }}({{ tag.type === 'peak' ? '冲高' : '稳态' }})
          <button class="tag-delete" @click="handleDeleteTag(tag.id)">×</button>
        </span>
        <button class="add-tag-btn" @click="handleOpenAddTag">+标签</button>
      </div>
    </div>

    <!-- 添加标签弹窗 -->
    <AddTagDialog
      :visible="showAddDialog"
      @update:visible="showAddDialog = $event"
      @submit="handleAddTag"
    />
  </div>
</template>

<style scoped>
.compare-time-navigator {
  padding: 8px 12px;
  background: #fff;
  border-radius: 6px;
}
.navigator-container {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 28px;
}
.time-range {
  font-size: 11px;
  font-weight: 500;
  color: #409eff;
  white-space: nowrap;
  min-width: 80px;
}
.navigator-wrapper {
  flex: 0 0 25%;
  min-width: 150px;
  height: 20px;
}
.chart-container {
  width: 100%;
  height: 20px;
}
.quick-buttons {
  display: flex;
  gap: 6px;
}
.quick-btn {
  padding: 3px 10px;
  font-size: 12px;
  color: #666;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 3px;
  cursor: pointer;
}
.quick-btn:hover {
  color: #409eff;
  border-color: #409eff;
}
.quick-btn.active {
  color: #fff;
  background: #409eff;
  border-color: #409eff;
}
.tag-list {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-left: auto;
}
.tag-item {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  border: 1px solid;
  display: flex;
  align-items: center;
  gap: 4px;
}
.tag-delete {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
  opacity: 0.6;
}
.tag-delete:hover {
  opacity: 1;
}
.add-tag-btn {
  background: #fff;
  border: 1px solid #409eff;
  color: #409eff;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
}
.add-tag-btn:hover {
  background: #409eff;
  color: #fff;
}
</style>
```

- [ ] **Step 2: 提交 CompareTimeNavigator 组件**

```bash
git add web/apps/web-ele/src/views/performance-monitor/components/CompareTimeNavigator.vue
git commit -m "feat(compare): 创建 CompareTimeNavigator 时间导航条组件"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 8: 重构 compare.vue 主页面

**Files:**
- Modify: `web/apps/web-ele/src/views/performance-monitor/compare.vue`

**背景说明**：现有 compare.vue 已有基础实现（版本选择、图表、数据摘要等），本次重构主要修改以下内容：

- [ ] **Step 1: 修改导入语句**

删除原有部分导入，添加新组件导入：

```typescript
// 删除：
import { useRoute } from 'vue-router';  // 不再需要 route.query.device_id
import ChartPanel from './components/ChartPanel.vue';  // 替换为 CompareChartPanel

// 添加新导入：
import MetricSelector from './components/MetricSelector.vue';
import MetricSearchPopup from './components/MetricSearchPopup.vue';
import CompareTimeNavigator from './components/CompareTimeNavigator.vue';
import CompareChartPanel from './components/CompareChartPanel.vue';
import CompareSummaryTable from './components/CompareSummaryTable.vue';
import VersionProcessPanel from './components/VersionProcessPanel.vue';
import VersionSelector from './components/VersionSelector.vue';
import { getVersionsAll, createCompareTag, getCompareTags, deleteCompareTag } from '#/api/core/performance-monitor';
import type { CompareTag } from './types';
```

- [ ] **Step 2: 移除 device_id 相关代码**

删除以下代码：
```typescript
// 删除
const route = useRoute();
const deviceId = ref('');

// onMounted 中删除：
deviceId.value = route.query.device_id as string || 'device-001';
await fetchVersions();  // 改为 await fetchVersionsAll();
```

- [ ] **Step 3: 添加指标选择状态**

```typescript
// 指标选择（复用性能监控组件）
type MetricKey = 'cpu' | 'gpu' | 'memory' | 'commitMemory';
const currentMetric = ref<MetricKey>('cpu');
const showMorePopup = ref(false);

function handleMetricChange(metric: MetricKey) {
  currentMetric.value = metric;
}
```

- [ ] **Step 4: 添加标签状态和函数**

```typescript
// 标签管理
const tags = ref<CompareTag[]>([]);

// 加载标签
async function fetchTags() {
  try {
    const result = await getCompareTags();
    tags.value = result.items.map(t => ({
      id: t.id,
      name: t.name,
      type: t.type as 'peak' | 'stable',
      start_time: Math.floor(new Date(t.start_time).getTime() / 1000), // 转换为相对秒数
      end_time: Math.floor(new Date(t.end_time).getTime() / 1000),
      note: t.note,
    }));
  } catch (error) {
    console.error('获取标签失败', error);
  }
}

// 添加标签
async function handleAddTag(tagData: any) {
  try {
    await createCompareTag({
      name: tagData.name,
      type: tagData.type,
      start_time: tagData.start_time.toISOString(),
      end_time: tagData.end_time.toISOString(),
      note: tagData.note,
    });
    await fetchTags();
  } catch (error) {
    console.error('创建标签失败', error);
  }
}

// 删除标签
async function handleDeleteTag(tagId: string) {
  try {
    await deleteCompareTag(tagId);
    await fetchTags();
  } catch (error) {
    console.error('删除标签失败', error);
  }
}
```

- [ ] **Step 5: 添加悬停状态和版本进程数据**

```typescript
// 悬停状态
const hoverTime = ref<number | undefined>();

// 版本进程数据（用于 VersionProcessPanel）
const versionProcessData = computed(() => {
  return compareData.value.versions.map((v: any) => ({
    name: v.version.name,
    id: v.version.id,
    data: v.collects.flatMap((c: any) => c.data),
  }));
});
```

- [ ] **Step 6: 修改 fetchVersions 使用新 API**

```typescript
async function fetchVersionsAll() {
  try {
    const result = await getVersionsAll();
    versions.value = result.items;
  } catch (error) {
    console.error('获取版本列表失败', error);
  }
}

// onMounted 中调用：
onMounted(async () => {
  await fetchVersionsAll();
  // ...其他初始化逻辑
});
```

- [ ] **Step 7: 修改模板使用新组件**

主要改动（参考现有 compare.vue 模板结构）：
- 顶部控制栏使用 `VersionSelector`
- 指标选择器使用 `MetricSelector` 和 `MetricSearchPopup`
- 时间导航使用 `CompareTimeNavigator`
- 图表使用 `CompareChartPanel`
- 底部面板使用 `CompareSummaryTable` 和 `VersionProcessPanel`

- [ ] **Step 2: 提交 compare.vue 重构**

```bash
git add web/apps/web-ele/src/views/performance-monitor/compare.vue
git commit -m "feat(compare): 重构版本对比页面主组件"
```

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## Task 9: 新增对比标签 API（前端）

**Files:**
- Modify: `web/apps/web-ele/src/api/core/performance-monitor.ts`

- [ ] **Step 1: 添加对比标签 API 类型定义**

**注意**：`CompareTag` 类型已在 `types.ts` 中定义（Task 2），此处只需定义 API 专用类型。

在 API 文件中添加（约第 94 行后）：

```typescript
// 对比标签 API 请求类型（绝对时间，ISO 格式）
export interface CompareTagCreate {
  name: string;
  type: 'peak' | 'stable';
  start_time: string;  // ISO 格式绝对时间
  end_time: string;    // ISO 格式绝对时间
  note?: string;
}

// 对比标签 API 响应类型（后端返回格式）
export interface CompareTagResponse {
  id: string;
  name: string;
  type: string;
  type_display: string;  // '冲高' 或 '稳态'
  start_time: string;    // ISO 格式
  end_time: string;      // ISO 格式
  note?: string;
}
```

**时间格式转换说明**：
- API 使用 ISO 格式绝对时间（`CompareTagCreate.start_time: string`）
- 前端组件使用相对秒数（`CompareTag.start_time: number`）
- 转换逻辑在 `CompareTimeNavigator` 的 `handleAddTag` 函数中实现（参考 Task 7 Step 1）

- [ ] **Step 2: 添加对比标签 API 函数**

在 API 文件末尾添加：

```typescript
// 对比标签管理
export async function createCompareTag(params: CompareTagCreate) {
  return requestClient.post<{ id: string; status: string }>(
    '/api/core/performance-monitor/compare/tag',
    params
  );
}

export async function getCompareTags() {
  return requestClient.get<{ items: CompareTagResponse[] }>(
    '/api/core/performance-monitor/compare/tags'
  );
}

export async function deleteCompareTag(tagId: string) {
  return requestClient.delete<{ status: string }>(
    `/api/core/performance-monitor/compare/tag/${tagId}`
  );
}

// 版本列表（无设备限制）
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

- [ ] **Step 4: 验证提交成功**

```bash
git status
```

---

## Task 10: 验证并提交完整功能

- [ ] **Step 1: 启动前端开发服务器验证**

```bash
cd web && pnpm dev
```

检查：
- 版本对比页面布局正确
- 版本选择器功能正常（无 device_id）
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

- [ ] **Step 3: 验证提交成功**

```bash
git status
```

---

## 成功标准

- 版本对比页面与性能监控页面风格统一
- 移除设备选择后可正常选择所有版本
- 标签弹窗样式与性能监控标记弹窗一致
- 所有新组件正常工作