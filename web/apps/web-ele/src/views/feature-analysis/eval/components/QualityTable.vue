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
      stripe
      style="width: 100%"
      @sort-change="handleSortChange"
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
        label="特性名称"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureDesc) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureOwner"
        label="责任人"
        width="100"
      >
        <template #default="{ row }">
          {{ showEmpty(row.featureOwner) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="delayDays"
        label="延期天数"
        width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.delayDays) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="testCount"
        label="需求转测次数"
        width="120"
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
        width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugTotal) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugSerious"
        label="严重问题数量"
        width="120"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugSerious) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="bugIntroCount"
        label="修改引入数量"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.bugIntroCount) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="codeLines"
        label="新增代码量"
        width="100"
        sortable="custom"
        align="center"
      >
        <template #default="{ row }">
          {{ showEmpty(row.codeLines) }}
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="qualityJudge"
        label="特性质量评价"
        min-width="150"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ showEmpty(row.qualityJudge) }}
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
.quality-table {
  background: white;
  border-radius: 8px;
}
</style>