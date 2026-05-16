<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { ElMessage, ElButton, ElEmpty } from 'element-plus';
import { useRoute } from 'vue-router';
import VersionSelector from './components/VersionSelector.vue';
import CompareChartPanel from './components/CompareChartPanel.vue';
import CompareTimeNavigator from './components/CompareTimeNavigator.vue';
import CompareSummaryTable from './components/CompareSummaryTable.vue';
import VersionProcessPanel from './components/VersionProcessPanel.vue';
import MetricSelector from './components/MetricSelector.vue';
import {
  getVersions,
  getCompareData,
  createCompareTag,
  deleteCompareTag,
} from '#/api/core/performance-monitor';
import type { PerformanceVersion, PerformanceData, CompareDataResponse } from '#/api/core/performance-monitor';
import type { CompareTag, ChartSeries, SummaryRow } from './types';
import { VERSION_COLORS } from './types';

const route = useRoute();

// 版本列表
const versions = ref<PerformanceVersion[]>([]);
const selectedVersionIds = ref<string[]>([]);
const loadingVersions = ref(false);

// 对比数据
const compareData = ref<CompareDataResponse>({ versions: [] });
const loadingCompare = ref(false);

// 当前指标
const currentMetric = ref('cpu_usage');
const metricOptions = [
  { key: 'cpu_usage', label: 'CPU' },
  { key: 'gpu_usage', label: 'GPU' },
  { key: 'memory_usage', label: '内存' },
  { key: 'commit_memory', label: '提交内存' },
];

// 时间范围
const timeRange = ref<{ start: Date; end: Date }>({
  start: new Date(),
  end: new Date(),
});

// 对比标签
const compareTags = ref<CompareTag[]>([]);
const loadingTags = ref(false);

// 进程详情（悬停数据）
const processData = ref<Array<{
  versionName: string;
  versionColor: string;
  processName: string;
  pid: number;
  currentValue: number;
  unit: string;
}>>([]);

// 版本颜色映射
function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length] || '#67c23a';
}

// 图表数据
const chartSeries = computed<ChartSeries[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    return {
      name: v.version.name,
      data: allData.map((d) => ({
        time: d.relative_time,
        value: d[currentMetric.value as keyof PerformanceData] as number || 0,
      })),
      color: getVersionColor(i),
    };
  });
});

// 数据摘要
const summaryData = computed<SummaryRow[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    return {
      version_name: v.version.name,
      color: getVersionColor(i),
      peak_cpu: Math.max(...allData.map(d => d.cpu_usage || 0)),
      peak_process_cpu: Math.max(...allData.map(d =>
        d.target_processes?.reduce((s, p) => s + p.total_cpu, 0) || 0
      )),
      peak_gpu: Math.max(...allData.map(d => d.gpu_usage || 0)),
      peak_commit_memory: Math.max(...allData.map(d => d.commit_memory || 0)),
      peak_memory_usage: Math.max(...allData.map(d => d.memory_usage || 0)),
    };
  });
});

onMounted(async () => {
  await fetchVersions();

  // 如果有 version_ids 参数，自动对比
  const versionIds = route.query.version_ids as string;
  if (versionIds) {
    selectedVersionIds.value = versionIds.split(',');
    await handleCompare();
  }
});

// 获取版本列表（不需要 device_id）
async function fetchVersions() {
  loadingVersions.value = true;
  try {
    const result = await getVersions();
    versions.value = result.items;
  } catch (error) {
    ElMessage.error('获取版本列表失败');
  } finally {
    loadingVersions.value = false;
  }
}

// 开始对比
async function handleCompare() {
  if (selectedVersionIds.value.length < 2) {
    ElMessage.warning('请至少选择2个版本进行对比');
    return;
  }

  loadingCompare.value = true;
  try {
    const result = await getCompareData(selectedVersionIds.value);
    compareData.value = result;

    // 加载对比标签
    await fetchCompareTags();

    // 初始化时间范围
    const allData = result.versions.flatMap(v => v.collects.flatMap(c => c.data));
    if (allData.length > 0) {
      const minTime = Math.min(...allData.map(d => d.relative_time));
      const maxTime = Math.max(...allData.map(d => d.relative_time));
      // 假设第一个采集的开始时间为基准
      const baseTime = new Date(result.versions[0]?.collects[0]?.collect.start_time || Date.now());
      timeRange.value = {
        start: new Date(baseTime.getTime() + minTime * 1000),
        end: new Date(baseTime.getTime() + maxTime * 1000),
      };
    }
  } catch (error) {
    ElMessage.error('获取对比数据失败');
  } finally {
    loadingCompare.value = false;
  }
}

// 获取对比标签
async function fetchCompareTags() {
  loadingTags.value = true;
  try {
    // TODO: 需要从后端 API 获取对比标签
    // const result = await getCompareTags();
    // compareTags.value = result.items;
    compareTags.value = []; // 暂时为空，等待后端 API
  } catch (error) {
    console.error('获取对比标签失败', error);
  } finally {
    loadingTags.value = false;
  }
}

// 添加对比标签
async function handleAddTag(data: { name: string; type: 'peak' | 'stable'; start_time: string; end_time: string; note?: string }) {
  try {
    await createCompareTag(data);
    ElMessage.success('标签添加成功');
    await fetchCompareTags();
  } catch (error) {
    ElMessage.error('添加标签失败');
  }
}

// 删除对比标签
async function handleRemoveTag(tagId: string) {
  try {
    await deleteCompareTag(tagId);
    ElMessage.success('标签删除成功');
    await fetchCompareTags();
  } catch (error) {
    ElMessage.error('删除标签失败');
  }
}

// 时间范围变化
function handleTimeRangeChange(range: { start: Date; end: Date }) {
  timeRange.value = range;
}

// 悬停数据更新
function handleHoverChange(data: { time: number; values: Record<string, number> }) {
  processData.value = compareData.value.versions.map((v, i) => {
    const collect = v.collects[0];
    const processData = collect?.data[0]?.target_processes?.[0];
    const instance = processData?.instances?.[0];
    return {
      versionName: v.version.name,
      versionColor: getVersionColor(i),
      processName: processData?.name || 'N/A',
      pid: instance?.pid || 0,
      currentValue: data.values[v.version.name] || 0,
      unit: currentMetric.value.includes('memory') ? 'GB' : '%',
    };
  });
}

// 导出报告
function handleExport() {
  ElMessage.info('导出报告功能待实现');
}

// 监听版本选择变化
watch(selectedVersionIds, (newIds) => {
  if (newIds.length >= 2) {
    handleCompare();
  }
});
</script>

<template>
  <div class="version-compare">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <h3>版本对比</h3>
      <VersionSelector
        :versions="versions"
        :selected-ids="selectedVersionIds"
        @update:selected-ids="selectedVersionIds = $event"
      />
      <div class="action-buttons">
        <ElButton type="success" :disabled="selectedVersionIds.length < 2" @click="handleCompare">
          开始对比
        </ElButton>
        <ElButton type="warning" @click="handleExport">
          导出报告
        </ElButton>
      </div>
    </div>

    <!-- 指标选择器 -->
    <MetricSelector
      :current-metric="currentMetric"
      :metrics="metricOptions"
      @change="currentMetric = $event"
    />

    <!-- 时间导航条 -->
    <CompareTimeNavigator
      :time-range="timeRange"
      :tags="compareTags"
      @time-range-change="handleTimeRangeChange"
      @add-tag="handleAddTag"
      @remove-tag="handleRemoveTag"
    />

    <!-- 图表区 -->
    <CompareChartPanel
      v-if="compareData.versions.length > 0"
      :series="chartSeries"
      :tags="compareTags"
      :loading="loadingCompare"
      @hover-change="handleHoverChange"
    />

    <!-- 底部面板 -->
    <div class="bottom-panel" v-if="compareData.versions.length > 0">
      <CompareSummaryTable :summary-data="summaryData" />
      <VersionProcessPanel :process-data="processData" />
    </div>

    <!-- 无数据提示 -->
    <ElEmpty v-if="selectedVersionIds.length < 2" description="请选择至少2个版本进行对比" />
  </div>
</template>

<style scoped>
.version-compare {
  padding: 16px;
  background: #f5f5f5;
  min-height: 100vh;
}

.control-bar {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.control-bar h3 {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.action-buttons {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.bottom-panel {
  display: flex;
  gap: 16px;
  margin-top: 12px;
}

.bottom-panel > :first-child {
  flex: 1;
}
</style>