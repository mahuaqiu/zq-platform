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
      stripe
      style="width: 100%"
    >
      <ElTableColumn
        prop="featureId"
        label="需求编号"
        width="150"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureId) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureDesc"
        label="需求名称"
        width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureDesc) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesId"
        label="问题单"
        width="120"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesId) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesTitle"
        label="问题名称"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesTitle) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesServices"
        label="归属"
        width="100"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesServices) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesOwner"
        label="责任人"
        width="100"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesOwner) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesSeverity"
        label="严重程度"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesSeverity) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesProbability"
        label="重现概率"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesProbability) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesStatus"
        label="问题状态"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesStatus) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="issuesVersion"
        label="发现版本"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.issuesVersion) }}
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="pagination-wrapper mt-4 flex justify-end">
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
  border-radius: 8px;
}
</style>