<script lang="ts" setup>
import type { TestReportListItem } from '#/api/core/test-report';

import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import { deleteReportApi, getReportListApi } from '#/api/core/test-report';

defineOptions({ name: 'TestReportListPage' });

const router = useRouter();

// 数据
const tableData = ref<TestReportListItem[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 筛选条件
const searchTaskName = ref('');

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getReportListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      taskName: searchTaskName.value || undefined,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
}

// 重置
function handleReset() {
  searchTaskName.value = '';
  currentPage.value = 1;
  loadData();
}

// 分页
function handlePageChange(page: number) {
  currentPage.value = page;
  loadData();
}

function handleSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadData();
}

// 查看详情
function handleViewDetail(row: TestReportListItem) {
  router.push(`/test-report/detail/${row.taskProjectID}`);
}

// 删除报告
async function handleDelete(row: TestReportListItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除报告「${row.taskName}」吗？删除后将无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    await deleteReportApi(row.id);
    ElMessage.success('删除成功');
    loadData();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error);
      ElMessage.error('删除失败');
    }
  }
}

// 格式化执行时间
function formatExecuteTime(time: string | null) {
  if (!time) return '--';
  const date = new Date(time);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

// 格式化同比变化
function formatCompareChange(change: number | null) {
  if (change === null) return '--';
  if (change > 0) return `↑${change}`;
  if (change < 0) return `↓${Math.abs(change)}`;
  return '→0';
}

// 获取同比变化样式类
function getCompareClass(change: number | null) {
  if (change === null) return 'tr-compare-gray';
  if (change > 0) return 'tr-compare-red';
  if (change < 0) return 'tr-compare-green';
  return 'tr-compare-gray';
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col">
      <!-- 搜索区域 -->
      <div class="tr-search-area">
        <div class="tr-search-form">
          <div class="tr-search-item">
            <label class="tr-search-label">任务名称</label>
            <ElInput
              v-model="searchTaskName"
              placeholder="搜索任务名称"
              clearable
              style="width: 240px"
            />
          </div>
          <div class="tr-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="tr-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="tr-table" border>
          <ElTableColumn prop="taskName" label="任务名称" min-width="200" show-overflow-tooltip />
          <ElTableColumn prop="executeTime" label="执行时间" min-width="140">
            <template #default="{ row }">
              {{ formatExecuteTime(row.executeTime) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="totalCases" label="用例总数" min-width="100" align="center" />
          <ElTableColumn prop="failTotal" label="失败总数" min-width="100" align="center">
            <template #default="{ row }">
              <span :class="row.failTotal > 0 ? 'tr-fail' : 'tr-pass'">{{ row.failTotal }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="passRate" label="通过率" min-width="100" align="center">
            <template #default="{ row }">
              <span :class="parseFloat(row.passRate) >= 80 ? 'tr-pass' : 'tr-warning'">{{ row.passRate }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="compareChange" label="同比变化" min-width="100" align="center">
            <template #default="{ row }">
              <span :class="getCompareClass(row.compareChange)">{{ formatCompareChange(row.compareChange) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="140" align="center">
            <template #default="{ row }">
              <a class="tr-link" @click="handleViewDetail(row)">查看详情</a>
              <a class="tr-link tr-link-danger" @click="handleDelete(row)">删除</a>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 分页 -->
        <div class="tr-pagination">
          <ElPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </div>
    </div>
  </Page>
</template>

<style scoped>
/* 搜索区域 */
.tr-search-area {
  padding: 16px;
  margin-bottom: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.tr-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
}

.tr-search-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tr-search-label {
  display: block;
  font-size: 12px;
  color: #666;
}

.tr-search-buttons {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

/* 表格区域 */
.tr-table-wrapper {
  flex: 1;
  padding: 16px;
  overflow: auto;
  background: #fff;
  border-radius: 4px;
}

.tr-table {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
}

.tr-table :deep(th.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  background: #fafafa !important;
  border-color: #e8e8e8 !important;
}

.tr-table :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
}

/* 状态样式 */
.tr-pass {
  font-weight: 500;
  color: #52c41a;
}

.tr-fail {
  font-weight: 500;
  color: #ff4d4f;
}

.tr-warning {
  font-weight: 500;
  color: #faad14;
}

.tr-compare-green {
  font-weight: 500;
  color: #52c41a;
}

.tr-compare-red {
  font-weight: 500;
  color: #ff4d4f;
}

.tr-compare-gray {
  color: #999;
}

/* 操作链接 */
.tr-link {
  color: #1890ff;
  text-decoration: none;
  cursor: pointer;
}

.tr-link:hover {
  text-decoration: underline;
}

.tr-link-danger {
  margin-left: 12px;
  color: #ff4d4f;
}

/* 分页 */
.tr-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0;
}
</style>