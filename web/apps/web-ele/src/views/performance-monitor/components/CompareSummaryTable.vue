<script setup lang="ts">
import { computed } from 'vue';
import { ElTable, ElTableColumn } from 'element-plus';
import type { SummaryRow } from '../types';

const props = defineProps<{
  summaryData: SummaryRow[];
  currentMetric: string;
}>();

// 是否有冲高标签数据
const hasPeakData = computed(() => {
  return props.summaryData.some(row => row.peak_cpu !== undefined || row.peak_gpu !== undefined);
});

// 是否有稳态标签数据
const hasStableData = computed(() => {
  return props.summaryData.some(row => row.mean_cpu !== undefined || row.mean_gpu !== undefined);
});

// 根据当前指标判断显示哪些列
const isCpuMetric = computed(() => props.currentMetric === 'cpu_usage');
const isGpuMetric = computed(() => props.currentMetric === 'gpu_usage');
const isMemoryMetric = computed(() => props.currentMetric === 'memory_usage');
const isCommitMemoryMetric = computed(() => props.currentMetric === 'commit_memory');

// Find best/worst values
const getMetricClass = (value: number | undefined, metricKey: string, allData: SummaryRow[]) => {
  if (value === undefined) return '';

  const values = allData
    .map(row => row[metricKey as keyof SummaryRow] as number | undefined)
    .filter(v => v !== undefined) as number[];

  if (values.length === 0) return '';

  const isLowerBetter = metricKey.includes('cpu') || metricKey.includes('gpu') || metricKey.includes('memory');
  const best = isLowerBetter ? Math.min(...values) : Math.max(...values);
  const worst = isLowerBetter ? Math.max(...values) : Math.min(...values);

  if (value === best) return 'best';
  if (value === worst) return 'worst';
  return '';
};

const formatValue = (value: number | undefined, unit: string = '%') => {
  if (value === undefined) return '-';
  if (unit === 'GB') {
    return `${value.toFixed(2)}${unit}`;
  }
  return `${value.toFixed(1)}${unit}`;
};
</script>

<template>
  <div class="compare-summary-table">
    <div class="title">数据摘要</div>
    <div class="tables-container">
      <!-- 冲高区间最高值表格 -->
      <div v-if="hasPeakData" class="summary-section">
        <div class="section-title">冲高区间最高值</div>
        <ElTable :data="summaryData" border stripe size="small">
          <ElTableColumn prop="version_name" label="版本" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.color, fontWeight: 'bold' }">
                {{ row.version_name }}
              </span>
            </template>
          </ElTableColumn>
          <!-- CPU 指标 -->
          <ElTableColumn v-if="isCpuMetric" prop="peak_cpu" label="系统" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.peak_cpu, 'peak_cpu', summaryData)">
                {{ formatValue(row.peak_cpu) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn v-if="isCpuMetric" prop="peak_process_cpu" label="进程" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.peak_process_cpu, 'peak_process_cpu', summaryData)">
                {{ formatValue(row.peak_process_cpu) }}
              </span>
            </template>
          </ElTableColumn>
          <!-- GPU 指标 -->
          <ElTableColumn v-if="isGpuMetric" prop="peak_gpu" label="系统" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.peak_gpu, 'peak_gpu', summaryData)">
                {{ formatValue(row.peak_gpu) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn v-if="isGpuMetric" prop="peak_process_gpu" label="进程" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.peak_process_gpu, 'peak_process_gpu', summaryData)">
                {{ formatValue(row.peak_process_gpu) }}
              </span>
            </template>
          </ElTableColumn>
          <!-- 内存指标 -->
          <ElTableColumn v-if="isMemoryMetric" prop="peak_memory_usage" label="峰值" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.peak_memory_usage, 'peak_memory_usage', summaryData)">
                {{ formatValue(row.peak_memory_usage, 'GB') }}
              </span>
            </template>
          </ElTableColumn>
          <!-- 提交内存指标 -->
          <ElTableColumn v-if="isCommitMemoryMetric" prop="peak_commit_memory" label="峰值" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.peak_commit_memory, 'peak_commit_memory', summaryData)">
                {{ formatValue(row.peak_commit_memory, 'GB') }}
              </span>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>

      <!-- 稳态区间平均值表格 -->
      <div v-if="hasStableData" class="summary-section">
        <div class="section-title">稳态区间平均值</div>
        <ElTable :data="summaryData" border stripe size="small">
          <ElTableColumn prop="version_name" label="版本" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.color, fontWeight: 'bold' }">
                {{ row.version_name }}
              </span>
            </template>
          </ElTableColumn>
          <!-- CPU 指标 -->
          <ElTableColumn v-if="isCpuMetric" prop="mean_cpu" label="系统" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.mean_cpu, 'mean_cpu', summaryData)">
                {{ formatValue(row.mean_cpu) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn v-if="isCpuMetric" prop="mean_process_cpu" label="进程" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.mean_process_cpu, 'mean_process_cpu', summaryData)">
                {{ formatValue(row.mean_process_cpu) }}
              </span>
            </template>
          </ElTableColumn>
          <!-- GPU 指标 -->
          <ElTableColumn v-if="isGpuMetric" prop="mean_gpu" label="系统" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.mean_gpu, 'mean_gpu', summaryData)">
                {{ formatValue(row.mean_gpu) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn v-if="isGpuMetric" prop="mean_process_gpu" label="进程" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.mean_process_gpu, 'mean_process_gpu', summaryData)">
                {{ formatValue(row.mean_process_gpu) }}
              </span>
            </template>
          </ElTableColumn>
          <!-- 内存指标 -->
          <ElTableColumn v-if="isMemoryMetric" prop="mean_memory_usage" label="平均" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.mean_memory_usage, 'mean_memory_usage', summaryData)">
                {{ formatValue(row.mean_memory_usage, 'GB') }}
              </span>
            </template>
          </ElTableColumn>
          <!-- 提交内存指标 -->
          <ElTableColumn v-if="isCommitMemoryMetric" prop="mean_commit_memory" label="平均" width="80">
            <template #default="{ row }">
              <span :class="getMetricClass(row.mean_commit_memory, 'mean_commit_memory', summaryData)">
                {{ formatValue(row.mean_commit_memory, 'GB') }}
              </span>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>

      <!-- 无标签提示 -->
      <div v-if="!hasPeakData && !hasStableData" class="no-tags-tip">
        请添加冲高/稳态标签以查看数据摘要
      </div>
    </div>
  </div>
</template>

<style scoped>
.compare-summary-table {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #333;
}

.tables-container {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.summary-section {
  flex: 0 0 auto;
}

.section-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.no-tags-tip {
  font-size: 13px;
  color: #999;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 4px;
}

.best {
  color: #67c23a;
  font-weight: 500;
}

.worst {
  color: #f56c6c;
  font-weight: 500;
}
</style>