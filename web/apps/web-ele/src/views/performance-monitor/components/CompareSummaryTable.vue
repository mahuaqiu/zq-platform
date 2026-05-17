<script setup lang="ts">
import { ElTable, ElTableColumn } from 'element-plus';
import type { SummaryRow } from '../types';

defineProps<{
  summaryData: SummaryRow[];
}>();

// Find best/worst values for each metric column
const getMetricClass = (value: number | undefined, metricKey: string, allData: SummaryRow[]) => {
  if (value === undefined) return '';

  // Get all non-undefined values for this metric
  const values = allData
    .map(row => row[metricKey as keyof SummaryRow] as number | undefined)
    .filter(v => v !== undefined) as number[];

  if (values.length === 0) return '';

  // For CPU/GPU/Memory metrics, lower is better
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
    <div class="title">数据摘要（全局峰值统计）</div>
    <ElTable :data="summaryData" border stripe>
      <ElTableColumn prop="version_name" label="版本" width="120">
        <template #default="{ row }">
          <span :style="{ color: row.color, fontWeight: 'bold' }">
            {{ row.version_name }}
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="peak_cpu" label="系统CPU">
        <template #default="{ row }">
          <span :class="getMetricClass(row.peak_cpu, 'peak_cpu', summaryData)">
            {{ formatValue(row.peak_cpu) }}
            <span v-if="getMetricClass(row.peak_cpu, 'peak_cpu', summaryData) === 'best'"> ✓</span>
            <span v-if="getMetricClass(row.peak_cpu, 'peak_cpu', summaryData) === 'worst'"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="peak_process_cpu" label="进程CPU">
        <template #default="{ row }">
          <span :class="getMetricClass(row.peak_process_cpu, 'peak_process_cpu', summaryData)">
            {{ formatValue(row.peak_process_cpu) }}
            <span v-if="getMetricClass(row.peak_process_cpu, 'peak_process_cpu', summaryData) === 'best'"> ✓</span>
            <span v-if="getMetricClass(row.peak_process_cpu, 'peak_process_cpu', summaryData) === 'worst'"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="peak_gpu" label="系统GPU">
        <template #default="{ row }">
          <span :class="getMetricClass(row.peak_gpu, 'peak_gpu', summaryData)">
            {{ formatValue(row.peak_gpu) }}
            <span v-if="getMetricClass(row.peak_gpu, 'peak_gpu', summaryData) === 'best'"> ✓</span>
            <span v-if="getMetricClass(row.peak_gpu, 'peak_gpu', summaryData) === 'worst'"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="peak_process_gpu" label="进程GPU">
        <template #default="{ row }">
          <span :class="getMetricClass(row.peak_process_gpu, 'peak_process_gpu', summaryData)">
            {{ formatValue(row.peak_process_gpu) }}
            <span v-if="getMetricClass(row.peak_process_gpu, 'peak_process_gpu', summaryData) === 'best'"> ✓</span>
            <span v-if="getMetricClass(row.peak_process_gpu, 'peak_process_gpu', summaryData) === 'worst'"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="peak_commit_memory" label="提交内存">
        <template #default="{ row }">
          <span :class="getMetricClass(row.peak_commit_memory, 'peak_commit_memory', summaryData)">
            {{ formatValue(row.peak_commit_memory, 'GB') }}
            <span v-if="getMetricClass(row.peak_commit_memory, 'peak_commit_memory', summaryData) === 'best'"> ✓</span>
            <span v-if="getMetricClass(row.peak_commit_memory, 'peak_commit_memory', summaryData) === 'worst'"> ✗</span>
          </span>
        </template>
      </ElTableColumn>
    </ElTable>
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

.best {
  color: #67c23a;
  font-weight: 500;
}

.worst {
  color: #f56c6c;
  font-weight: 500;
}
</style>