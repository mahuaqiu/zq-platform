<script lang="ts" setup>
import type { SchedulerLog, SchedulerJobSimple, SchedulerLogStatistics } from '#/api/core/scheduler';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElMessage,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElDatePicker,
} from 'element-plus';

import {
  getSchedulerLogListApi,
  getSchedulerJobAllApi,
  getSchedulerLogStatisticsApi,
} from '#/api/core/scheduler';

import {
  formatDateTime,
  formatDuration,
  getLogStatusLabel,
  getLogStatusClass,
  LOG_STATUS_OPTIONS,
} from './data';
import LogDetailModal from './modules/log-detail-modal.vue';
import CleanLogModal from './modules/clean-log-modal.vue';

defineOptions({ name: 'SchedulerLogPage' });

// 数据
const tableData = ref<SchedulerLog[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 统计数据
const statistics = ref<SchedulerLogStatistics>({
  total_executions: 0,
  success_executions: 0,
  failed_executions: 0,
  success_rate: 0,
});

// 任务列表（用于下拉选择）
const jobOptions = ref<SchedulerJobSimple[]>([]);

// 筛选条件
const searchForm = ref({
  job_id: '',
  status: '',
  startTimeGte: '',
  startTimeLte: '',
});

// 日志详情弹窗
const logDetailVisible = ref(false);
const currentLogId = ref<string>();

// 清理日志弹窗
const cleanLogVisible = ref(false);

// 加载任务列表（用于下拉选择）
async function loadJobOptions() {
  try {
    const res = await getSchedulerJobAllApi();
    jobOptions.value = res || [];
  } catch (error) {
    console.error('加载任务列表失败:', error);
  }
}

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getSchedulerLogListApi({
      page: currentPage.value,
      pageSize: pageSize.value,
      job_id: searchForm.value.job_id || undefined,
      status: searchForm.value.status || undefined,
      startTimeGte: searchForm.value.startTimeGte || undefined,
      startTimeLte: searchForm.value.startTimeLte || undefined,
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
    const res = await getSchedulerLogStatisticsApi({
      job_id: searchForm.value.job_id || undefined,
      status: searchForm.value.status || undefined,
      startTimeGte: searchForm.value.startTimeGte || undefined,
      startTimeLte: searchForm.value.startTimeLte || undefined,
    });
    statistics.value = res;
  } catch (error) {
    console.error('加载统计数据失败:', error);
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
    job_id: '',
    status: '',
    startTimeGte: '',
    startTimeLte: '',
  };
  currentPage.value = 1;
  loadData();
  loadStatistics(); // 同时刷新统计数据
}

// 清理日志
function handleCleanLogs() {
  cleanLogVisible.value = true;
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
function handleDetail(row: SchedulerLog) {
  currentLogId.value = row.id;
  logDetailVisible.value = true;
}

// 格式化成功率（后端返回的是百分比数值，如 66.67 表示 66.67%）
function formatSuccessRate(rate: number): string {
  if (rate === 0) return '0%';
  return `${rate.toFixed(1)}%`;
}

// 初始加载
onMounted(() => {
  loadJobOptions();
  loadData();
  loadStatistics();
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
            <ElSelect
              v-model="searchForm.job_id"
              placeholder="全部任务"
              clearable
              filterable
              style="width: 160px"
            >
              <ElOption
                v-for="job in jobOptions"
                :key="job.id"
                :label="job.name"
                :value="job.id"
              />
            </ElSelect>
          </div>
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">执行状态</label>
            <ElSelect
              v-model="searchForm.status"
              placeholder="全部"
              clearable
              style="width: 100px"
            >
              <ElOption
                v-for="opt in LOG_STATUS_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </ElSelect>
          </div>
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">开始时间</label>
            <ElDatePicker
              v-model="searchForm.startTimeGte"
              type="datetime"
              placeholder="选择开始时间"
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 160px"
              clearable
            />
          </div>
          <div class="scheduler-search-item">
            <label class="scheduler-search-label">结束时间</label>
            <ElDatePicker
              v-model="searchForm.startTimeLte"
              type="datetime"
              placeholder="选择结束时间"
              format="YYYY-MM-DD HH:mm:ss"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 160px"
              clearable
            />
          </div>

          <div class="scheduler-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>

          <!-- 清理日志按钮 -->
          <ElButton type="danger" class="scheduler-clean-btn" @click="handleCleanLogs">
            清理日志
          </ElButton>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="scheduler-statistics">
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">总执行次数</div>
            <div class="stat-value stat-blue">{{ statistics.total_executions }}</div>
          </div>
        </ElCard>
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">成功次数</div>
            <div class="stat-value stat-green">{{ statistics.success_executions }}</div>
          </div>
        </ElCard>
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">失败次数</div>
            <div class="stat-value stat-red">{{ statistics.failed_executions }}</div>
          </div>
        </ElCard>
        <ElCard class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-label">成功率</div>
            <div class="stat-value stat-green">{{ formatSuccessRate(statistics.success_rate) }}</div>
          </div>
        </ElCard>
      </div>

      <!-- 表格区域 -->
      <div class="scheduler-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="scheduler-table" border>
          <ElTableColumn prop="job_name" label="任务名称" min-width="150" show-overflow-tooltip />
          <ElTableColumn prop="start_time" label="执行时间" min-width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.start_time) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="status" label="状态" min-width="80" align="center">
            <template #default="{ row }">
              <span :class="`log-status-tag log-status-${getLogStatusClass(row.status)}`">
                {{ getLogStatusLabel(row.status) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="duration" label="耗时" min-width="100" align="center">
            <template #default="{ row }">
              {{ formatDuration(row.duration) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="result" label="执行结果" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.result || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="hostname" label="执行主机" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <code v-if="row.hostname" class="scheduler-code">{{ row.hostname }}</code>
              <span v-else>-</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="80" fixed="right" align="center">
            <template #default="{ row }">
              <a class="scheduler-link" @click="handleDetail(row)">详情</a>
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

      <!-- 日志详情弹窗 -->
      <LogDetailModal
        v-model:visible="logDetailVisible"
        :log-id="currentLogId"
      />

      <!-- 清理日志弹窗 -->
      <CleanLogModal
        v-model:visible="cleanLogVisible"
        @success="loadData"
      />
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

.scheduler-clean-btn {
  margin-left: auto;
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

/* 状态标签样式（带背景色） */
.log-status-tag {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 4px;
}

.log-status-success {
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.log-status-danger {
  color: #ff4d4f;
  background: #fff1f0;
  border: 1px solid #ffa39e;
}

.log-status-warning {
  color: #faad14;
  background: #fffbe6;
  border: 1px solid #ffe58f;
}

.log-status-info {
  color: #1890ff;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
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

/* 分页 */
.scheduler-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0;
}
</style>