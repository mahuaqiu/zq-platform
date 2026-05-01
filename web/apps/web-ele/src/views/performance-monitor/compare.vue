<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElButton, ElSelect, ElOption, ElTag, ElTable, ElTableColumn, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElEmpty, ElRadioGroup, ElRadio } from 'element-plus';
import { useRoute } from 'vue-router';
import ChartPanel from './components/ChartPanel.vue';
import {
  getVersions,
  getCompareData,
  createTag,
  getTags,
  deleteTag,
} from '#/api/core/performance-monitor';
import type {
  PerformanceVersion,
  PerformanceCollect,
  PerformanceData,
  PerformanceTag,
} from '#/api/core/performance-monitor';
import { VERSION_COLORS } from './types';
import type { ChartSeries, ChartTag, SummaryRow } from './types';

const route = useRoute();

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
const durationOptions = [30, 60, 120, 300];

// 当前选中的采集ID（用于标签操作）
const activeCollectId = ref<string>('');

// 版本颜色映射
function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length] || '#67c23a';
}

// 获取每个采集的标签
const collectTags = ref<Map<string, PerformanceTag[]>>(new Map());

// 转换为 ChartTag 格式
function getChartTags(collectId: string): ChartTag[] {
  const tags = collectTags.value.get(collectId) || [];
  return tags.map((tag) => ({
    name: tag.name,
    start: tag.start_relative_time,
    duration: tag.duration,
    type: tag.type,
    color: tag.type === 'peak' ? '#67c23a' : '#f56c6c',
  }));
}

// 曲线图数据（相对时间）- 包含原始数据用于 Tooltip
const cpuChartSeries = computed<ChartSeries[]>(() => {
  return compareData.value.versions.map((v, i) => {
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

// 获取原始数据用于 Tooltip
const allRawData = computed<PerformanceData[]>(() => {
  return compareData.value.versions.flatMap((v) =>
    v.collects.flatMap((c) => c.data),
  );
});

// 合并区间计算
function getMergedInterval(): { start: number; end: number } | null {
  // 获取所有标签
  const allTags = Array.from(collectTags.value.values()).flat();

  if (allTags.length === 0) return null;

  // 找最小起始和最大结束
  const starts = allTags.map((t) => t.start_relative_time);
  const ends = allTags.map((t) => t.start_relative_time + t.duration);

  return {
    start: Math.min(...starts),
    end: Math.max(...ends),
  };
}

// 数据摘要表 - 按区间计算
const summaryTable = computed<SummaryRow[]>(() => {
  const interval = getMergedInterval();

  return compareData.value.versions.map((v, i) => {
    const allData = v.collects.flatMap((c) => c.data);

    // 根据区间筛选数据
    let intervalData = allData;
    if (interval) {
      intervalData = allData.filter(
        (d) =>
          d.relative_time >= interval.start && d.relative_time < interval.end,
      );
    }

    // 如果没有数据，返回空行
    if (intervalData.length === 0) {
      return {
        version_name: v.version.name,
        color: getVersionColor(i),
      };
    }

    // 计算各指标
    const cpuValues = intervalData.map((d) => d.cpu_usage || 0);
    const gpuValues = intervalData.map((d) => d.gpu_usage || 0);
    const memValues = intervalData.map((d) => d.memory_usage || 0);
    const commitValues = intervalData.map((d) => d.commit_memory || 0);
    const processCpuValues = intervalData.map((d) =>
      d.target_processes?.reduce((s, p) => s + p.total_cpu, 0) || 0,
    );

    // 默认计算峰值和均值
    return {
      version_name: v.version.name,
      color: getVersionColor(i),
      // 峰值（最大值）
      peak_cpu: Math.max(...cpuValues),
      peak_process_cpu: Math.max(...processCpuValues),
      peak_gpu: Math.max(...gpuValues),
      peak_commit_memory: Math.max(...commitValues),
      peak_memory_usage: Math.max(...memValues),
      // 均值
      mean_cpu:
        cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length || 0,
      mean_process_cpu:
        processCpuValues.reduce((a, b) => a + b, 0) / processCpuValues.length || 0,
      mean_gpu:
        gpuValues.reduce((a, b) => a + b, 0) / gpuValues.length || 0,
      mean_commit_memory:
        commitValues.reduce((a, b) => a + b, 0) / commitValues.length || 0,
      mean_memory_usage:
        memValues.reduce((a, b) => a + b, 0) / memValues.length || 0,
    };
  });
});

// 找出最优和最差值
function isBest(key: keyof SummaryRow, value: number): boolean {
  const values = summaryTable.value
    .map((r) => r[key] as number)
    .filter((v) => v !== undefined && v > 0);
  if (values.length === 0) return false;
  return value === Math.min(...values);
}

function isWorst(key: keyof SummaryRow, value: number): boolean {
  const values = summaryTable.value
    .map((r) => r[key] as number)
    .filter((v) => v !== undefined && v > 0);
  if (values.length === 0) return false;
  return value === Math.max(...values);
}

// 区间描述
const intervalDescription = computed(() => {
  const interval = getMergedInterval();
  if (!interval) return '全部数据区间';
  return `相对时间 ${interval.start}秒 - ${interval.end}秒`;
});

onMounted(async () => {
  // 从路由参数获取 deviceId
  deviceId.value = route.query.device_id as string || 'device-001';
  await fetchVersions();

  // 如果有 version_ids 参数，自动对比
  const versionIds = route.query.version_ids as string;
  if (versionIds) {
    selectedVersions.value = versionIds.split(',');
    await handleCompare();
  }
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

    // 加载每个采集的标签
    for (const v of result.versions) {
      for (const c of v.collects) {
        await fetchTagsForCollect(c.collect.id);
      }
    }
  } catch (error) {
    ElMessage.error('获取对比数据失败');
  }
}

async function fetchTagsForCollect(collectId: string) {
  try {
    const result = await getTags(collectId);
    collectTags.value.set(collectId, result.items);
  } catch (error) {
    console.error('获取标签失败', error);
  }
}

function handleVersionChange() {
  if (selectedVersions.value.length >= 2) {
    handleCompare();
  }
}

// 标签操作
function handlePointClick(data: { time: number; collectId: string }) {
  // 设置第一个采集作为默认目标（实际应该让用户选择）
  const firstCollect = compareData.value.versions[0]?.collects[0]?.collect.id;
  if (!firstCollect) {
    ElMessage.warning('没有可用的采集数据');
    return;
  }

  tagForm.value = {
    collect_id: data.collectId || firstCollect,
    name: '',
    start_relative_time: data.time,
    duration: 60,
    type: 'peak',
  };
  activeCollectId.value = data.collectId || firstCollect;
  showTagDialog.value = true;
}

async function handleCreateTag() {
  if (!tagForm.value.name) {
    ElMessage.warning('请输入标签名称');
    return;
  }
  try {
    await createTag({
      collect_id: tagForm.value.collect_id,
      name: tagForm.value.name,
      start_relative_time: tagForm.value.start_relative_time,
      duration: tagForm.value.duration,
      type: tagForm.value.type,
    });
    ElMessage.success('标签创建成功');
    showTagDialog.value = false;
    await fetchTagsForCollect(tagForm.value.collect_id);
  } catch (error) {
    ElMessage.error('创建标签失败');
  }
}

async function handleTagDelete(tagName: string) {
  // 需要找到对应的标签ID
  const tags = collectTags.value.get(activeCollectId.value) || [];
  const tag = tags.find((t) => t.name === tagName);
  if (!tag) return;

  try {
    await deleteTag(tag.id);
    ElMessage.success('标签删除成功');
    await fetchTagsForCollect(activeCollectId.value);
  } catch (error) {
    ElMessage.error('删除标签失败');
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
      <!-- 简化版：只显示对比图表 -->
      <ChartPanel
        title="CPU 使用率对比"
        :series="cpuChartSeries"
        :height="200"
        :raw-data="allRawData"
        :show-actual-time="true"
        :enable-tag-click="true"
        :collect-id="compareData.versions[0]?.collects[0]?.collect.id"
        :tags="getChartTags(compareData.versions[0]?.collects[0]?.collect.id || '')"
        @point-click="handlePointClick"
        @tag-delete="handleTagDelete"
      />
      <ChartPanel
        title="GPU 使用率对比"
        :series="gpuChartSeries"
        :height="160"
        :raw-data="allRawData"
        :show-actual-time="true"
      />
      <ChartPanel
        title="提交内存对比"
        :series="commitMemoryChartSeries"
        :height="160"
        :raw-data="allRawData"
        :show-actual-time="true"
      />
      <ChartPanel
        title="内存使用对比"
        :series="memoryChartSeries"
        :height="160"
        :raw-data="allRawData"
        :show-actual-time="true"
      />
    </div>

    <!-- 数据摘要表 -->
    <div class="summary-table" v-if="summaryTable.length > 0">
      <div class="summary-header">
        <h3>数据摘要对比（峰值区间）</h3>
      </div>
      <el-table :data="summaryTable" border stripe size="small">
        <el-table-column prop="version_name" label="版本" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.color, fontWeight: '600' }">
              {{ row.version_name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="系统CPU" align="center">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_cpu', row.peak_cpu), 'worst-value': isWorst('peak_cpu', row.peak_cpu) }">
              {{ row.peak_cpu?.toFixed(1) }}%
              <span v-if="isBest('peak_cpu', row.peak_cpu)"> ✓</span>
              <span v-if="isWorst('peak_cpu', row.peak_cpu)"> ✗</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="进程CPU" align="center">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_process_cpu', row.peak_process_cpu), 'worst-value': isWorst('peak_process_cpu', row.peak_process_cpu) }">
              {{ row.peak_process_cpu?.toFixed(1) }}%
              <span v-if="isBest('peak_process_cpu', row.peak_process_cpu)"> ✓</span>
              <span v-if="isWorst('peak_process_cpu', row.peak_process_cpu)"> ✗</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="GPU" align="center">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_gpu', row.peak_gpu), 'worst-value': isWorst('peak_gpu', row.peak_gpu) }">
              {{ row.peak_gpu?.toFixed(1) }}%
              <span v-if="isBest('peak_gpu', row.peak_gpu)"> ✓</span>
              <span v-if="isWorst('peak_gpu', row.peak_gpu)"> ✗</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="提交内存" align="center">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_commit_memory', row.peak_commit_memory), 'worst-value': isWorst('peak_commit_memory', row.peak_commit_memory) }">
              {{ row.peak_commit_memory?.toFixed(1) }} GB
              <span v-if="isBest('peak_commit_memory', row.peak_commit_memory)"> ✓</span>
              <span v-if="isWorst('peak_commit_memory', row.peak_commit_memory)"> ✗</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="内存使用" align="center">
          <template #default="{ row }">
            <span :class="{ 'best-value': isBest('peak_memory_usage', row.peak_memory_usage), 'worst-value': isWorst('peak_memory_usage', row.peak_memory_usage) }">
              {{ row.peak_memory_usage?.toFixed(1) }} GB
              <span v-if="isBest('peak_memory_usage', row.peak_memory_usage)"> ✓</span>
              <span v-if="isWorst('peak_memory_usage', row.peak_memory_usage)"> ✗</span>
            </span>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-note">
        <span class="best-value">✓ 最优</span> |
        <span class="worst-value">✗ 最差</span> |
        <span>区间：{{ intervalDescription }}</span>
      </div>
    </div>

    <!-- 无数据提示 -->
    <div class="no-data" v-if="selectedVersions.length < 2">
      <el-empty description="请选择至少2个版本进行对比" />
    </div>

    <!-- 标签配置弹窗 -->
    <el-dialog v-model="showTagDialog" title="添加区间标签" width="400px">
      <el-form label-width="80px">
        <el-form-item label="起始时间">
          <span>{{ tagForm.start_relative_time }}秒</span>
        </el-form-item>
        <el-form-item label="标签名称">
          <el-input
            v-model="tagForm.name"
            placeholder="如：发起共享、场景加载"
          />
        </el-form-item>
        <el-form-item label="时间长度">
          <el-input-number v-model="tagForm.duration" :min="10" :max="600" />
          <span style="margin-left: 8px">秒</span>
          <div style="margin-top: 8px; display: flex; gap: 4px">
            <el-button
              v-for="opt in durationOptions"
              :key="opt"
              size="small"
              :type="tagForm.duration === opt ? 'primary' : 'default'"
              @click="tagForm.duration = opt"
            >
              {{ opt }}秒
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="区间类型">
          <el-radio-group v-model="tagForm.type">
            <el-radio value="peak">峰值区间（绿色）</el-radio>
            <el-radio value="mean">均值区间（红色）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTagDialog = false">取消</el-button>
        <el-button type="success" @click="handleCreateTag">确认添加</el-button>
      </template>
    </el-dialog>
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
.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.summary-header h3 {
  margin: 0;
  font-size: 14px;
}
.interval-note {
  font-size: 12px;
  color: #666;
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