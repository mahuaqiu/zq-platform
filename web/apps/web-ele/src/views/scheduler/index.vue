<script lang="ts" setup>
import type { SchedulerJob, SchedulerStatistics } from '#/api/core/scheduler';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElInput,
} from 'element-plus';

import {
  deleteSchedulerJobApi,
  executeSchedulerJobApi,
  getSchedulerJobGroupsApi,
  getSchedulerJobListApi,
  getSchedulerStatisticsApi,
} from '#/api/core/scheduler';

import {
  formatDateTime,
  formatTriggerConfig,
  getJobStatusLabel,
  getJobStatusClass,
  getTriggerTypeLabel,
  JOB_STATUS_OPTIONS,
  TRIGGER_TYPE_OPTIONS,
} from './data';
import TaskFormModal from './modules/task-form-modal.vue';

defineOptions({ name: 'SchedulerJobPage' });

// 数据
const tableData = ref<SchedulerJob[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 统计数据
const statistics = ref<SchedulerStatistics>({
  total_jobs: 0,
  enabled_jobs: 0,
  disabled_jobs: 0,
  paused_jobs: 0,
  total_executions: 0,
  success_executions: 0,
  failed_executions: 0,
  success_rate: 0,
});

// 筛选条件
const searchForm = ref({
  name: '',
  trigger_type: '',
  status: undefined as number | undefined,
  group: '',
});

// 分组列表
const groupOptions = ref<string[]>([]);

// 任务表单弹窗
const taskFormModalRef = ref();
const currentJobId = ref<string>();

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getSchedulerJobListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      name: searchForm.value.name || undefined,
      trigger_type: searchForm.value.trigger_type || undefined,
      status: searchForm.value.status,
      group: searchForm.value.group || undefined,
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

// 加载统计数据
async function loadStatistics() {
  try {
    const res = await getSchedulerStatisticsApi();
    statistics.value = res;
  } catch (error) {
    console.error('加载统计数据失败:', error);
  }
}

// 加载分组列表
async function loadGroupOptions() {
  try {
    const groups = await getSchedulerJobGroupsApi();
    groupOptions.value = groups || [];
  } catch (error) {
    console.error('加载分组列表失败:', error);
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
  loadStatistics(); // 同时刷新统计数据
}

// 重置
function handleReset() {
  searchForm.value = {
    name: '',
    trigger_type: '',
    status: undefined,
    group: '',
  };
  currentPage.value = 1;
  loadData();
  loadStatistics(); // 同时刷新统计数据
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

// 新增
function handleCreate() {
  currentJobId.value = undefined;
  taskFormModalRef.value?.open();
}

// 编辑
function handleEdit(row: SchedulerJob) {
  currentJobId.value = row.id;
  taskFormModalRef.value?.open(row.id);
}

// 执行任务
function handleExecute(row: SchedulerJob) {
  const displayName = row.name || row.code || row.id;
  ElMessageBox.confirm(`确定要立即执行任务 "${displayName}" 吗？`, '执行确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'info',
  }).then(async () => {
    try {
      await executeSchedulerJobApi({ job_id: row.id });
      ElMessage.success('任务已开始执行');
      loadData();
      loadStatistics();
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '执行失败';
      ElMessage.error(msg);
    }
  });
}

// 删除
function handleDelete(row: SchedulerJob) {
  const displayName = row.name || row.code || row.id;
  ElMessageBox.confirm(`确定要删除任务 "${displayName}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteSchedulerJobApi(row.id);
      ElMessage.success('删除成功');
      loadData();
      loadStatistics();
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '删除失败';
      ElMessage.error(msg);
    }
  });
}

// 格式化成功率（后端返回的是百分比数值，如 66.67 表示 66.67%）
function formatSuccessRate(rate: number): string {
  if (rate === 0) return '0%';
  return `${rate.toFixed(1)}%`;
}

// 初始加载
onMounted(() => {
  loadData();
  loadStatistics();
  loadGroupOptions();
});
</script>

<template>
  <Page auto-content-height>
    <div class="scheduler-page flex h-full flex-col">
      <!-- 搜索区域 -->
      <div class="scheduler-search-area">
        <div class="scheduler-search-form">
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">任务名称</label>
            <ElInput
              v-model="searchForm.name"
              placeholder="请输入"
              clearable
              style="width: 160px"
            />
          </div>
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">触发类型</label>
            <ElSelect
              v-model="searchForm.trigger_type"
              placeholder="全部"
              clearable
              style="width: 120px"
            >
              <ElOption
                v-for="opt in TRIGGER_TYPE_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </div>
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">任务状态</label>
            <ElSelect
              v-model="searchForm.status"
              placeholder="全部"
              clearable
              style="width: 100px"
            >
              <ElOption
                v-for="opt in JOB_STATUS_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </div>
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">任务分组</label>
            <ElSelect
              v-model="searchForm.group"
              placeholder="全部"
              clearable
              style="width: 140px"
            >
              <ElOption
                v-for="group in groupOptions"
                :key="group"
                :label="group"
                :value="group"
              />
            </ElSelect>
          </div>

          <div class="scheduler-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>

          <ElButton class="scheduler-create-btn" @click="handleCreate">
            + 新增任务
          </ElButton>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="scheduler-statistics">
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">总任务数</div>
            <div class="stat-value stat-blue">{{ statistics.total_jobs }}</div>
          </div>
        </ElCard>
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">启用任务</div>
            <div class="stat-value stat-green">{{ statistics.enabled_jobs }}</div>
          </div>
        </ElCard>
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">执行成功率</div>
            <div class="stat-value stat-green">{{ formatSuccessRate(statistics.success_rate) }}</div>
          </div>
        </ElCard>
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">今天总执行</div>
            <div class="stat-value stat-blue">{{ statistics.total_executions }}</div>
          </div>
        </ElCard>
      </div>

      <!-- 表格区域 -->
      <div class="scheduler-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="scheduler-table" border>
          <ElTableColumn prop="group" label="任务分组" min-width="100" show-overflow-tooltip />
          <ElTableColumn prop="name" label="任务名称" min-width="150" show-overflow-tooltip />
          <ElTableColumn prop="code" label="任务编码" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <code class="scheduler-code">{{ row.code }}</code>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="trigger_type" label="触发类型" min-width="100">
            <template #default="{ row }">
              {{ getTriggerTypeLabel(row.trigger_type) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="trigger_config" label="触发配置" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <code class="scheduler-code">{{ formatTriggerConfig(row) }}</code>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="status" label="状态" min-width="80" align="center">
            <template #default="{ row }">
              <span :class="`job-status-tag job-status-${getJobStatusClass(row.status)}`">
                {{ getJobStatusLabel(row.status) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="today_run_count" label="今日执行" min-width="90" align="center">
            <template #default="{ row }">
              {{ row.today_run_count || 0 }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="next_run_time" label="下次执行时间" min-width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.next_run_time) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="140" fixed="right" align="center">
            <template #default="{ row }">
              <a class="scheduler-link" @click="handleExecute(row)">执行</a>
              <a class="scheduler-link" @click="handleEdit(row)">编辑</a>
              <a class="scheduler-link scheduler-link-danger" @click="handleDelete(row)">删除</a>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 分页 -->
        <div class="scheduler-pagination">
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

      <!-- 任务表单弹窗 -->
      <TaskFormModal ref="taskFormModalRef" @success="loadData" />
    </div>
  </Page>
</template>

<style scoped>
/* 页面容器 */
.scheduler-page {
  background: #f0f2f5;
}

/* 响应式：小屏幕下统计卡片改为2列 */
@media (max-width: 1200px) {
  .scheduler-statistics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .scheduler-statistics {
    grid-template-columns: 1fr;
  }
}

.scheduler-search-area {
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.scheduler-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.scheduler-search-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.scheduler-search-label {
  font-size: 13px;
  font-weight: 600;
  color: #111;
}

.scheduler-search-buttons {
  display: flex;
  gap: 8px;
}

.scheduler-create-btn {
  margin-left: auto;
  background: #f5f5f5 !important;
  color: #111 !important;
  border: 1px solid #d9d9d9 !important;
  border-radius: 8px !important;
  padding: 10px 20px !important;
  font-weight: 500;
}

/* 统计卡片 */
.scheduler-statistics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  padding: 24px;
  margin-bottom: 0;
}

.stat-card {
  cursor: pointer;
  background: #fff !important;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border: 1px solid #e8e8e8;
  transition: transform 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card :deep(.el-card__body) {
  padding: 20px;
}

.stat-content {
  text-align: left;
}

.stat-label {
  font-size: 13px;
  font-weight: 600;
  color: #111;
}

.stat-value {
  margin-top: 8px;
  font-size: 32px;
  font-weight: 600;
  color: #3b82f6;
}

/* 数字颜色类 */
.stat-blue {
  color: #3b82f6;
}

.stat-green {
  color: #22c55e;
}

.stat-red {
  color: #ef4444;
}

.stat-orange {
  color: #f59e0b;
}

/* 表格区域 */
.scheduler-table-wrapper {
  flex: 1;
  padding: 0 24px 24px;
  overflow: auto;
}

/* 表格支持水平滚动 */
.scheduler-table-wrapper :deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

/* 带边框表格样式 */
.scheduler-table {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* 确保表格有外边框 */
.scheduler-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.scheduler-table :deep(.el-table__border-left-patch) {
  background-color: #e8e8e8 !important;
}

/* 表头样式 */
.scheduler-table :deep(th.el-table__cell) {
  padding: 12px 16px !important;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
  background: #fafafa !important;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 表格单元格样式 - 确保无斑马纹/阴影背景 */
.scheduler-table :deep(td.el-table__cell) {
  padding: 14px 16px !important;
  font-size: 13px;
  color: #333;
  background: #fff !important;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 去掉斑马纹效果 */
.scheduler-table :deep(.el-table__row--striped) {
  background: #fff !important;
}

.scheduler-table :deep(.el-table__row--striped td.el-table__cell) {
  background: #fff !important;
}

/* 代码样式 */
.scheduler-code {
  padding: 2px 6px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 12px;
  color: #333;
  background: #f5f5f5;
  border-radius: 4px;
}

/* 状态样式 */
.scheduler-status-success {
  font-weight: 500;
  color: #52c41a;
}

.scheduler-status-danger {
  font-weight: 500;
  color: #ff4d4f;
}

.scheduler-status-warning {
  font-weight: 500;
  color: #faad14;
}

.scheduler-status-info {
  font-weight: 500;
  color: #1890ff;
}

/* 状态标签样式（带背景色） */
.job-status-tag {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 4px;
}

.job-status-success {
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.job-status-danger {
  color: #ff4d4f;
  background: #fff1f0;
  border: 1px solid #ffa39e;
}

.job-status-warning {
  color: #faad14;
  background: #fffbe6;
  border: 1px solid #ffe58f;
}

.job-status-info {
  color: #1890ff;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

/* 操作链接 */
.scheduler-link {
  margin-right: 12px;
  color: #1890ff;
  text-decoration: none;
  cursor: pointer;
}

.scheduler-link:hover {
  text-decoration: underline;
}

.scheduler-link-danger {
  margin-right: 0;
  color: #ff4d4f;
}

/* 分页 */
.scheduler-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0;
}

/* 搜索区域 */
</style>