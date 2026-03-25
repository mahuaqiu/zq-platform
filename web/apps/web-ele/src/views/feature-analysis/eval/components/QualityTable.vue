<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElPagination } from 'element-plus';

import type { QualityEvaluationItem } from '#/api/core/feature-analysis';
import { getQualityListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'QualityTable' });

export interface FilterParams {
  version?: string;
  featureId?: string;
  featureDesc?: string;
}

const props = defineProps<{
  filterParams: FilterParams;
}>();

const tableData = ref<QualityEvaluationItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 排序状态
const currentSort = ref<{ prop: string; order: string | null }>({
  prop: '',
  order: null,
});

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const sortBy = currentSort.value.prop || undefined;
    const sortOrder = currentSort.value.order
      ? currentSort.value.order === 'ascending' ? 'asc' : 'desc'
      : undefined;

    const res = await getQualityListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      ...props.filterParams,
      sortBy,
      sortOrder,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载表格数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 排序变化
function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  currentSort.value = { prop, order };
  currentPage.value = 1;
  loadTableData();
}

// 分页变更
function handlePageChange(page: number) {
  currentPage.value = page;
  loadTableData();
}

function handleSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadTableData();
}

// 显示空值
function showEmpty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return String(value);
}

// 获取质量评价样式
function getQualityClass(quality: string): string {
  const qualityMap: Record<string, string> = {
    '良好': 'status-success',
    '待改进': 'status-warning',
    '较差': 'status-danger',
  };
  return qualityMap[quality] || '';
}

watch(
  () => props.filterParams,
  () => {
    currentPage.value = 1;
    loadTableData();
  },
  { deep: true }
);

onMounted(() => {
  loadTableData();
});
</script>

<template>
  <div class="quality-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      style="width: 100%"
      class="data-table"
      @sort-change="handleSortChange"
    >
      <ElTableColumn
        prop="featureId"
        label="需求编号"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <code v-if="row.featureId" class="code-text">{{ row.featureId }}</code>
          <span v-else class="empty-text">-</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureDesc"
        label="特性名称"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureDesc) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureOwner"
        label="责任人"
        min-width="80"
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureOwner) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="delayDays"
        label="延期天数"
        min-width="90"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          <span v-if="row.delayDays && row.delayDays > 0" class="status-danger">{{ row.delayDays }}</span>
          <span v-else>{{ showEmpty(row.delayDays) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="testCount"
        label="转测次数"
        min-width="90"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.testCount) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugTotal"
        label="问题单总数"
        min-width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugTotal) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugSerious"
        label="严重问题"
        min-width="90"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          <span v-if="row.bugSerious && row.bugSerious > 0" class="status-danger">{{ row.bugSerious }}</span>
          <span v-else>{{ showEmpty(row.bugSerious) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugIntroCount"
        label="修改引入"
        min-width="90"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugIntroCount) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="codeLines"
        label="新增代码量"
        min-width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.codeLines) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="qualityJudge"
        label="质量评价"
        min-width="90"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span :class="getQualityClass(row.qualityJudge)">{{ showEmpty(row.qualityJudge) }}</span>
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="pagination-wrapper">
      <ElPagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.quality-table {
  background: white;
  border-radius: 4px;
}

/* 带边框表格样式 */
.data-table {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
}

/* 表头样式 */
.data-table :deep(th.el-table__cell) {
  background: #fafafa !important;
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 表格单元格样式 */
.data-table :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 编号样式 */
.code-text {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
}

.empty-text {
  color: #999;
}

/* 状态颜色 */
.status-success {
  color: #52c41a;
}

.status-warning {
  color: #faad14;
}

.status-danger {
  color: #ff4d4f;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0 0;
}
</style>