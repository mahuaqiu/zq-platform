<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

import { ElTable, ElTableColumn, ElTag, ElPagination } from 'element-plus';

import type { FeatureAnalysisItem } from '#/api/core/feature-analysis';
import { getFeatureListApi } from '#/api/core/feature-analysis';

defineOptions({ name: 'FeatureTable' });

const props = defineProps<{
  version?: string;
}>();

const tableData = ref<FeatureAnalysisItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);

// 加载表格数据
async function loadTableData() {
  loading.value = true;
  try {
    const res = await getFeatureListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      version: props.version,
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

// 获取测试状态标签类型
function getStatusType(status: string): 'success' | 'warning' | 'info' {
  switch (status) {
    case '已完成':
      return 'success';
    case '测试中':
      return 'warning';
    default:
      return 'info';
  }
}

watch(
  () => props.version,
  () => {
    currentPage.value = 1;
    loadTableData();
  }
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
      stripe
      style="width: 100%"
    >
      <ElTableColumn
        prop="featureIdFather"
        label="父工作项编码号"
        width="150"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureId"
        label="需求编号"
        width="150"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureDesc"
        label="标题"
        min-width="200"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureOwner"
        label="测试责任人"
        width="100"
      />
      <ElTableColumn
        prop="featureTaskService"
        label="测试归属"
        width="100"
      />
      <ElTableColumn
        prop="featureSafeTest"
        label="涉及安全"
        width="80"
        align="center"
      />
      <ElTableColumn
        prop="featureTestExpectTime"
        label="预计转测时间"
        width="120"
      />
      <ElTableColumn
        prop="featureTestStartTime"
        label="实际转测情况"
        width="120"
      />
      <ElTableColumn
        prop="testStatus"
        label="测试状态"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          <ElTag :type="getStatusType(row.testStatus)" size="small">
            {{ row.testStatus }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn
        prop="featureProgress"
        label="测试进展"
        width="200"
        show-overflow-tooltip
      />
      <ElTableColumn
        prop="featureRisk"
        label="风险与关键问题"
        width="150"
        show-overflow-tooltip
      />
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
.feature-table {
  background: white;
  border-radius: 8px;
}
</style>