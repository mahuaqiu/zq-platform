<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElPagination } from 'element-plus';

import type { FeatureAnalysisItem } from '#/api/core/feature-analysis';
import { getFeatureListApi } from '#/api/core/feature-analysis';
import type { ProgressFilterParams } from './FilterBar.vue';

defineOptions({ name: 'FeatureTable' });

const props = defineProps<{
  filterParams: ProgressFilterParams;
}>();

const tableData = ref<FeatureAnalysisItem[]>([]);
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

    const res = await getFeatureListApi({
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

// 获取状态样式类
function getStatusClass(status: string): string {
  const statusMap: Record<string, string> = {
    '已完成': 'status-success',
    '测试中': 'status-warning',
    '未开始': 'status-info',
    '延期': 'status-delayed',
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
  <div class="feature-table">
    <ElTable
      v-loading="loading"
      :data="tableData"
      border
      style="width: 100%"
      class="data-table"
      @sort-change="handleSortChange"
    >
      <ElTableColumn
        prop="featureIdFather"
        label="EP编号"
        min-width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <code v-if="row.featureIdFather" class="code-text">{{ row.featureIdFather }}</code>
          <span v-else class="empty-text">-</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureId"
        label="FE编号"
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
        label="标题"
        min-width="180"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureOwner"
        label="责任人"
        min-width="80"
      />
      <ElTableColumn
        prop="featureTaskService"
        label="归属"
        min-width="80"
      />
      <ElTableColumn
        prop="featureSafeTest"
        label="安全"
        min-width="60"
        align="center"
      />
      <ElTableColumn
        prop="featureTestExpectTime"
        label="预计转测"
        min-width="100"
        sortable="custom"
      />
      <ElTableColumn
        prop="featureTestStartTime"
        label="实际转测"
        min-width="100"
        sortable="custom"
      />
      <ElTableColumn
        prop="testStatus"
        label="状态"
        min-width="80"
        align="center"
        sortable="custom"
      >
        <template #default="{ row }">
          <span :class="getStatusClass(row.testStatus)">{{ row.testStatus || '-' }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureProgress"
        label="进展"
        min-width="80"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureRisk"
        label="风险问题"
        min-width="120"
        show-overflow-tooltip
      />
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
.feature-table {
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

.status-delayed {
  color: #ff4d4f;
}

.status-info {
  color: #909399;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0 0;
}
</style>