<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElPagination } from 'element-plus';

import type { IssuesAnalysisItem } from '#/api/core/issues-analysis';
import { getIssuesListApi } from '#/api/core/issues-analysis';

defineOptions({ name: 'IssuesTable' });

export interface FilterParams {
  version?: string;
  featureDesc?: string;
  issuesOwner?: string;
  issuesSeverity?: string;
}

const props = defineProps<{
  filterParams: FilterParams;
}>();

const tableData = ref<IssuesAnalysisItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const res = await getIssuesListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      ...props.filterParams,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载表格数据失败:', error);
  } finally {
    loading.value = false;
  }
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

// 获取严重程度样式
function getSeverityClass(severity: string): string {
  const severityMap: Record<string, string> = {
    '严重': 'status-danger',
    '一般': 'status-warning',
    '轻微': 'status-success',
  };
  return severityMap[severity] || '';
}

// 获取问题状态样式
function getIssueStatusClass(status: string): string {
  const statusMap: Record<string, string> = {
    '已解决': 'status-success',
    '处理中': 'status-warning',
    '待处理': 'status-info',
  };
  return statusMap[status] || '';
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
  <div class="issues-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      style="width: 100%"
      class="data-table"
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
        label="需求名称"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureDesc) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesId"
        label="问题单"
        min-width="100"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <code v-if="row.issuesId" class="code-text">{{ row.issuesId }}</code>
          <span v-else class="empty-text">-</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesTitle"
        label="问题名称"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesTitle) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesServices"
        label="归属"
        min-width="80"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesServices) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesOwner"
        label="责任人"
        min-width="80"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesOwner) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesSeverity"
        label="严重程度"
        min-width="90"
        align="center"
      >
        <template #default="{ row }">
          <span :class="getSeverityClass(row.issuesSeverity)">{{ showEmpty(row.issuesSeverity) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesProbability"
        label="重现概率"
        min-width="90"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesProbability) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesStatus"
        label="问题状态"
        min-width="90"
        align="center"
      >
        <template #default="{ row }">
          <span :class="getIssueStatusClass(row.issuesStatus)">{{ showEmpty(row.issuesStatus) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesVersion"
        label="发现版本"
        min-width="90"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesVersion) }}
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
.issues-table {
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

.status-info {
  color: #1890ff;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0 0;
}
</style>