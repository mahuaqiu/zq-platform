<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import ChartPanel from './components/ChartPanel.vue';
import { getVersions, getCompareData, createVersion } from '#/api/core/performance-monitor';
import type { PerformanceVersion, PerformanceCollect, PerformanceData, PerformanceTag } from '#/api/core/performance-monitor';
import { VERSION_COLORS } from './types';
import type { ChartSeries, SummaryRow } from './types';

// 设备ID
const deviceId = ref('');

// 版本列表
const versions = ref<PerformanceVersion[]>([]);
const selectedVersions = ref<string[]>([]);
const maxVersions = 6;

// 对比数据
const compareData = ref<{
  versions: Array<{
    version: PerformanceVersion;
    collects: Array<{
      collect: PerformanceCollect;
      data: PerformanceData[];
      tags: PerformanceTag[];
    }>;
  }>;
}>({ versions: [] });

// 标签弹窗
const showTagDialog = ref(false);
const tagForm = ref({
  collect_id: '',
  name: '',
  start_relative_time: 0,
  duration: 60,
  type: 'peak' as 'peak' | 'mean',
});

// 版本颜色映射
function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length];
}

// 曲线图数据（相对时间）
const cpuChartSeries = computed<ChartSeries[]>(() => {
  return compareData.value.versions.map((v, i) => {
    // 合并所有采集的数据
    const allData = v.collects.flatMap((c) => c.data);
    return {
      name: v.version.name,
      data: allData.map((d) => ({
        time: d.relative_time,
        value: d.cpu_usage || 0,
      })),
      color: getVersionColor(i),
    };
  });
});

const gpuChartSeries = computed<ChartSeries[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    return {
      name: v.version.name,
      data: allData.map((d) => ({
        time: d.relative_time,
        value: d.gpu_usage || 0,
      })),
      color: getVersionColor(i),
    };
  });
});

const commitMemoryChartSeries = computed<ChartSeries[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    return {
      name: v.version.name,
      data: allData.map((d) => ({
        time: d.relative_time,
        value: d.commit_memory || 0,
      })),
      color: getVersionColor(i),
    };
  });
});

const memoryChartSeries = computed<ChartSeries[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    return {
      name: v.version.name,
      data: allData.map((d) => ({
        time: d.relative_time,
        value: d.memory_usage || 0,
      })),
      color: getVersionColor(i),
    };
  });
});

// 数据摘要表
const summaryTable = computed<SummaryRow[]>(() => {
  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);
    const cpuValues = allData.map((d) => d.cpu_usage || 0);
    const gpuValues = allData.map((d) => d.gpu_usage || 0);
    const memValues = allData.map((d) => d.memory_usage || 0);
    const commitValues = allData.map((d) => d.commit_memory || 0);

    return {
      version_name: v.version.name,
      color: getVersionColor(i),
      peak_cpu: Math.max(...cpuValues),
      mean_cpu: cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length,
      peak_gpu: Math.max(...gpuValues),
      mean_gpu: gpuValues.reduce((a, b) => a + b, 0) / gpuValues.length,
      peak_memory_usage: Math.max(...memValues),
      mean_memory_usage: memValues.reduce((a, b) => a + b, 0) / memValues.length,
      peak_commit_memory: Math.max(...commitValues),
      mean_commit_memory: commitValues.reduce((a, b) => a + b, 0) / commitValues.length,
    };
  });
});

// 找出最优和最差值
function isBest(key: keyof SummaryRow, value: number): boolean {
  const values = summaryTable.value
    .map((r) => r[key] as number)
    .filter((v) => v !== undefined);
  return value === Math.min(...values);
}

function isWorst(key: keyof SummaryRow, value: number): boolean {
  const values = summaryTable.value
    .map((r) => r[key] as number)
    .filter((v) => v !== undefined);
  return value === Math.max(...values);
}

onMounted(async () => {
  // 从路由参数获取 deviceId
  deviceId.value = 'device-001'; // 实际应从路由获取
  await fetchVersions();
});

async function fetchVersions() {
  try {
    const result = await getVersions(deviceId.value);
    versions.value = result.items;
  } catch (error) {
    console.error('获取版本列表失败', error);
  }
}

async function handleCompare() {
  if (selectedVersions.value.length < 2) {
    ElMessage.warning('请至少选择2个版本进行对比');
    return;
  }
  try {
    const result = await getCompareData(selectedVersions.value);
    compareData.value = result;
  } catch (error) {
    ElMessage.error('获取对比数据失败');
  }
}

function handleVersionChange() {
  if (selectedVersions.value.length >= 2) {
    handleCompare();
  }
}

// 导出功能
function handleExportHtml() {
  ElMessage.info('导出 HTML 功能待实现');
}

function handleExportExcel() {
  ElMessage.info('导出 Excel 功能待实现');
}
</script>

<template>
  <div class="performance-compare">
    <!-- 版本选择 -->
    <div class="version-selector">
      <div class="selector-header">
        <h3>版本对比</h3>
        <div class="export-buttons">
          <el-button size="small" @click="handleExportHtml">导出 HTML</el-button>
          <el-button size="small" @click="handleExportExcel">导出 Excel</el-button>
        </div>
      </div>
      <el-select
        v-model="selectedVersions"
        multiple
        placeholder="选择版本（最多6个）"
        style="width: 100%"
        :max-collapse-tags="maxVersions"
        @change="handleVersionChange"
      >
        <el-option
          v-for="v in versions"
          :key="v.id"
          :label="v.name"
          :value="v.id"
        />
      </el-select>
      <div class="selected-tags">
        <el-tag
          v-for="(id, i) in selectedVersions"
          :key="id"
          :color="getVersionColor(i)"
          effect="dark"
          closable
          @close="selectedVersions.splice(i, 1)"
        >
          {{ versions.find(v => v.id === id)?.name }}
        </el-tag>
      </div>
    </div>

    <!-- 曲线图区 -->
    <div class="charts-area" v-if="compareData.versions.length > 0">
      <ChartPanel title="CPU 使用率" :series="cpuChartSeries" :height="200" />
      <ChartPanel title="GPU 使用率" :series="gpuChartSeries" :height="160" />
      <ChartPanel title="提交内存" :series="commitMemoryChartSeries" :height="160" />
      <ChartPanel title="内存使用" :series="memoryChartSeries" :height="160" />
    </div>

    <!-- 数据摘要表 -->
    <div class="summary-table" v-if="summaryTable.length > 0">
      <h3>数据摘要对比</h3>
      <el-table :data="summaryTable" border stripe>
        <el-table-column prop="version_name" label="版本" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.color, fontWeight: '600' }">
              {{ row.version_name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="CPU峰值" prop="peak_cpu">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_cpu', row.peak_cpu), 'worst-value': isWorst('peak_cpu', row.peak_cpu) }">
              {{ row.peak_cpu?.toFixed(1) }}%
              <span v-if="isBest('peak_cpu', row.peak_cpu)"> ✓</span>
              <span v-if="isWorst('peak_cpu', row.peak_cpu)"> ✗</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="CPU均值" prop="mean_cpu">
          <template #default="{ row }">
            {{ row.mean_cpu?.toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="GPU峰值" prop="peak_gpu">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_gpu', row.peak_gpu), 'worst-value': isWorst('peak_gpu', row.peak_gpu) }">
              {{ row.peak_gpu?.toFixed(1) }}%
              <span v-if="isBest('peak_gpu', row.peak_gpu)"> ✓</span>
              <span v-if="isWorst('peak_gpu', row.peak_gpu)"> ✗</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="提交内存峰值" prop="peak_commit_memory">
          <template #default="{ row }">
            {{ row.peak_commit_memory?.toFixed(2) }} GB
          </template>
        </el-table-column>
        <el-table-column label="内存峰值" prop="peak_memory_usage">
          <template #default="{ row }">
            {{ row.peak_memory_usage?.toFixed(2) }} GB
          </template>
        </el-table-column>
      </el-table>
      <div class="table-note">
        <span class="best-value">✓ 最优</span> |
        <span class="worst-value">✗ 最差</span>
      </div>
    </div>

    <!-- 无数据提示 -->
    <div class="no-data" v-if="selectedVersions.length < 2">
      <el-empty description="请选择至少2个版本进行对比" />
    </div>
  </div>
</template>

<style scoped>
.performance-compare {
  padding: 16px;
  background: #f5f5f5;
  min-height: 100vh;
}
.version-selector {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.selector-header h3 {
  margin: 0;
  font-size: 16px;
}
.export-buttons {
  display: flex;
  gap: 8px;
}
.selected-tags {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.charts-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}
.summary-table {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}
.summary-table h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
}
.table-note {
  margin-top: 8px;
  font-size: 11px;
  color: #666;
}
.best-value {
  color: #67c23a;
  font-weight: 600;
}
.worst-value {
  color: #f56c6c;
  font-weight: 600;
}
.no-data {
  background: #fff;
  border-radius: 8px;
  padding: 32px;
}
</style>