<script setup lang="ts">
import type { ChartSeries, CompareTag, SummaryRow } from './types';

import type {
  CompareDataResponse,
  PerformanceData,
  PerformanceVersion,
} from '#/api/core/performance-monitor';

import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';

import { ElButton, ElEmpty, ElMessage, ElTag } from 'element-plus';

import {
  createCompareTag,
  deleteCompareTag,
  getCompareData,
  getCompareTags,
  getVersions,
} from '#/api/core/performance-monitor';

import AddTagDialog from './components/AddTagDialog.vue';
import CompareChartPanel from './components/CompareChartPanel.vue';
import CompareSummaryTable from './components/CompareSummaryTable.vue';
import MetricSelector from './components/MetricSelector.vue';
import VersionSelector from './components/VersionSelector.vue';
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

// 对比标签
const compareTags = ref<CompareTag[]>([]);
const loadingTags = ref(false);
const showAddTagDialog = ref(false);

// 版本颜色映射
function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length] || '#67c23a';
}

// 判断是否是 CPU/GPU 指标（需要显示两个图表）
const isCpuOrGpuMetric = computed(() => {
  return currentMetric.value === 'cpu_usage' || currentMetric.value === 'gpu_usage';
});

// 系统数据图表（归一化：每条线从0开始）
const systemChartSeries = computed<ChartSeries[]>(() => {
  const result: ChartSeries[] = [];
  const metricField = currentMetric.value as keyof PerformanceData;

  compareData.value.versions.forEach((v, i) => {
    const systemData: Array<{ time: number; value: number }> = [];

    v.collects.forEach((c) => {
      c.data.forEach((d) => {
        systemData.push({
          time: d.relative_time,
          value: (d[metricField] as number) || 0,
        });
      });
    });

    systemData.sort((a, b) => a.time - b.time);
    const startTime = systemData.length > 0 ? systemData[0].time : 0;

    const normalizedData = systemData.map(d => ({
      time: d.time - startTime,
      value: d.value,
    }));

    result.push({
      name: v.version.name,
      data: normalizedData,
      color: getVersionColor(i),
    });
  });

  return result;
});

// 进程数据图表（仅 CPU/GPU）
const processChartSeries = computed<ChartSeries[]>(() => {
  if (!isCpuOrGpuMetric.value) return [];

  const result: ChartSeries[] = [];

  compareData.value.versions.forEach((v, i) => {
    const processData: Array<{ time: number; value: number }> = [];

    v.collects.forEach((c) => {
      c.data.forEach((d) => {
        const processValue = d.target_processes?.reduce((sum, p) => {
          return sum + (currentMetric.value === 'cpu_usage' ? p.total_cpu : p.total_gpu || 0);
        }, 0) || 0;
        processData.push({
          time: d.relative_time,
          value: processValue,
        });
      });
    });

    processData.sort((a, b) => a.time - b.time);
    const startTime = processData.length > 0 ? processData[0].time : 0;

    const normalizedData = processData.map(d => ({
      time: d.time - startTime,
      value: d.value,
    }));

    result.push({
      name: v.version.name,
      data: normalizedData,
      color: getVersionColor(i),
    });
  });

  return result;
});

// 图表标题
const systemChartTitle = computed(() => {
  const metric = metricOptions.find(m => m.key === currentMetric.value);
  const label = metric?.label || currentMetric.value;
  if (isCpuOrGpuMetric.value) {
    return `${label} - 系统使用率 (%)`;
  }
  if (currentMetric.value.includes('memory')) {
    return `${label} (GB)`;
  }
  return `${label} (%)`;
});

const processChartTitle = computed(() => {
  const metric = metricOptions.find(m => m.key === currentMetric.value);
  const label = metric?.label || currentMetric.value;
  return `${label} - 进程使用率 (%)`;
});

// 数据摘要
const summaryData = computed<SummaryRow[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    return {
      version_name: v.version.name,
      color: getVersionColor(i),
      peak_cpu: Math.max(...allData.map((d) => d.cpu_usage || 0)),
      peak_process_cpu: Math.max(
        ...allData.map(
          (d) => d.target_processes?.reduce((s, p) => s + p.total_cpu, 0) || 0,
        ),
      ),
      peak_gpu: Math.max(...allData.map((d) => d.gpu_usage || 0)),
      peak_process_gpu: Math.max(
        ...allData.map(
          (d) => d.target_processes?.reduce((s, p) => s + (p.total_gpu || 0), 0) || 0,
        ),
      ),
      peak_commit_memory: Math.max(...allData.map((d) => d.commit_memory || 0)),
      peak_memory_usage: Math.max(...allData.map((d) => d.memory_usage || 0)),
    };
  });
});

onMounted(async () => {
  await fetchVersions();

  // 优先从 sessionStorage 读取（页面切换恢复），其次从 URL 参数读取
  const storedVersionIds = sessionStorage.getItem('compare_version_ids');
  const urlVersionIds = route.query.version_ids as string;

  const versionIds = storedVersionIds || urlVersionIds;
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
  } catch {
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

    // 保存对比状态到 sessionStorage，用于页面切换恢复
    sessionStorage.setItem('compare_version_ids', selectedVersionIds.value.join(','));

    // 加载对比标签
    await fetchCompareTags();
  } catch {
    ElMessage.error('获取对比数据失败');
  } finally {
    loadingCompare.value = false;
  }
}

// 获取对比标签
async function fetchCompareTags() {
  loadingTags.value = true;
  try {
    const result = await getCompareTags();
    compareTags.value = result.items;
  } catch (error) {
    console.error('获取对比标签失败', error);
    compareTags.value = [];
  } finally {
    loadingTags.value = false;
  }
}

// 删除对比标签
async function handleRemoveTag(tagId: string) {
  try {
    await deleteCompareTag(tagId);
    ElMessage.success('标签删除成功');
    await fetchCompareTags();
  } catch {
    ElMessage.error('删除标签失败');
  }
}

// 添加对比标签
function handleAddTag(data: {
  end_time: number;
  name: string;
  note?: string;
  start_time: number;
  type: 'peak' | 'stable';
}) {
  createCompareTag(data)
    .then(() => {
      ElMessage.success('标签添加成功');
      fetchCompareTags();
    })
    .catch(() => {
      ElMessage.error('添加标签失败');
    });
  showAddTagDialog.value = false;
}

// 计算图表数据的最大时间（用于限制标签输入范围）
const maxChartTime = computed(() => {
  const allTimes = systemChartSeries.value.flatMap(s => s.data.map(d => d.time));
  return allTimes.length > 0 ? Math.max(...allTimes) : 0;
});

// 导出报告
function handleExport() {
  ElMessage.info('导出报告功能待实现');
}

// 注意：用户需要手动点击"开始对比"按钮，不自动触发
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
        <ElButton
          type="success"
          :disabled="selectedVersionIds.length < 2"
          @click="handleCompare"
        >
          开始对比
        </ElButton>
        <ElButton type="warning" @click="handleExport"> 导出报告 </ElButton>
      </div>
    </div>

    <!-- 指标选择器和标签区域 -->
    <div class="metric-bar" v-if="compareData.versions.length > 0">
      <MetricSelector
        :current-metric="currentMetric"
        @change="currentMetric = $event"
      />
      <!-- 标签列表 -->
      <div class="tag-area">
        <ElTag
          v-for="tag in compareTags"
          :key="tag.id"
          :type="tag.type === 'peak' ? 'danger' : 'success'"
          effect="plain"
          closable
          @close="handleRemoveTag(tag.id)"
        >
          {{ tag.name }}（{{ tag.type === 'peak' ? '冲高' : '稳态' }}: {{ tag.start_time }}s-{{ tag.end_time }}s）
        </ElTag>
        <ElButton size="small" type="primary" plain @click="showAddTagDialog = true">
          +标签
        </ElButton>
      </div>
    </div>

    <!-- 添加标签弹窗 -->
    <AddTagDialog
      :visible="showAddTagDialog"
      :max-time="maxChartTime"
      @update:visible="showAddTagDialog = $event"
      @submit="handleAddTag"
    />

    <!-- 图表区 - CPU/GPU 显示两个图表，其他指标显示一个 -->
    <div v-if="compareData.versions.length > 0" class="charts-area">
      <!-- CPU/GPU: 双图表布局 -->
      <div v-if="isCpuOrGpuMetric" class="dual-charts">
        <CompareChartPanel
          :title="systemChartTitle"
          :series="systemChartSeries"
          :tags="compareTags"
          :loading="loadingCompare"
          :current-metric="currentMetric"
        />
        <CompareChartPanel
          :title="processChartTitle"
          :series="processChartSeries"
          :tags="[]"
          :loading="loadingCompare"
          :current-metric="currentMetric"
        />
      </div>
      <!-- 其他指标: 单图表布局 -->
      <CompareChartPanel
        v-else
        :title="systemChartTitle"
        :series="systemChartSeries"
        :tags="compareTags"
        :loading="loadingCompare"
        :current-metric="currentMetric"
      />
    </div>

    <!-- 底部面板 -->
    <div class="bottom-panel" v-if="compareData.versions.length > 0">
      <CompareSummaryTable :summary-data="summaryData" />
    </div>

    <!-- 无数据提示 -->
    <ElEmpty
      v-if="selectedVersionIds.length < 2"
      description="请选择至少2个版本进行对比"
    />
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

.metric-bar {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.tag-area {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
}

.charts-area {
  margin-bottom: 12px;
}

.dual-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.dual-charts .compare-chart-panel {
  height: 100%;
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
