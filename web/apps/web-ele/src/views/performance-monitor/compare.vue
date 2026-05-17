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

// 图表数据（归一化：每条线从0开始）
// CPU/GPU 显示两条线：系统和进程
const chartSeries = computed<ChartSeries[]>(() => {
  const result: ChartSeries[] = [];
  const isCpuOrGpu = currentMetric.value === 'cpu_usage' || currentMetric.value === 'gpu_usage';
  const metricField = currentMetric.value as keyof PerformanceData;

  compareData.value.versions.forEach((v, i) => {
    // 遍历每个采集，获取所有数据点
    const systemData: Array<{ time: number; value: number }> = [];
    const processData: Array<{ time: number; value: number }> = [];

    v.collects.forEach((c) => {
      c.data.forEach((d) => {
        // 系统数据
        systemData.push({
          time: d.relative_time,
          value: (d[metricField] as number) || 0,
        });
        // 进程数据（仅 CPU/GPU）
        if (isCpuOrGpu) {
          const processValue = d.target_processes?.reduce((sum, p) => {
            return sum + (currentMetric.value === 'cpu_usage' ? p.total_cpu : p.total_gpu || 0);
          }, 0) || 0;
          processData.push({
            time: d.relative_time,
            value: processValue,
          });
        }
      });
    });

    // 按时间排序
    systemData.sort((a, b) => a.time - b.time);
    processData.sort((a, b) => a.time - b.time);

    // 获取第一个时间点作为偏移量
    const startTime = systemData.length > 0 ? systemData[0].time : 0;

    // 归一化：减去第一个时间点，从0开始
    const normalizedSystemData = systemData.map(d => ({
      time: d.time - startTime,
      value: d.value,
    }));
    const normalizedProcessData = processData.map(d => ({
      time: d.time - startTime,
      value: d.value,
    }));

    const baseColor = getVersionColor(i);

    // 添加系统线
    result.push({
      name: v.version.name,
      data: normalizedSystemData,
      color: baseColor,
    });

    // CPU/GPU 添加进程线（使用同色系的虚线效果，名称加 "(进程)"）
    if (isCpuOrGpu && processData.length > 0) {
      result.push({
        name: `${v.version.name}(进程)`,
        data: normalizedProcessData,
        color: baseColor,
        unit: '%',
      });
    }
  });

  return result;
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
  if (chartSeries.value.length === 0) return 0;
  const allTimes = chartSeries.value.flatMap(s => s.data.map(d => d.time));
  return Math.max(...allTimes);
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
        :metrics="metricOptions"
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

    <!-- 图表区 -->
    <CompareChartPanel
      v-if="compareData.versions.length > 0"
      :series="chartSeries"
      :tags="compareTags"
      :loading="loadingCompare"
      :current-metric="currentMetric"
    />

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

.bottom-panel {
  display: flex;
  gap: 16px;
  margin-top: 12px;
}

.bottom-panel > :first-child {
  flex: 1;
}
</style>
