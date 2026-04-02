<script lang="ts" setup>
import type { SchedulerLog, SchedulerJobSimple } from '#/api/core/scheduler';

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

import { getSchedulerLogListApi, getSchedulerJobAllApi } from '#/api/core/scheduler';

import {
  formatDateTime,
  formatDuration,
  getLogStatusLabel,
  getLogStatusClass,
  LOG_STATUS_OPTIONS,
} from './data';

defineOptions({ name: 'SchedulerLogPage' });

// 数据
const tableData = ref<SchedulerLog[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 统计数据
const statistics = ref({
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

    // 计算统计数据（从当前页数据）
    calculateStatistics(res.items || []);
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 计算统计数据
function calculateStatistics(logs: SchedulerLog[]) {
  // 这里暂时从当前页面数据计算，后续可以从 API 获取
  const total_executions = total.value;
  const success_executions = logs.filter((log) => log.status === 'success').length;
  const failed_executions = logs.filter((log) => log.status === 'failed').length;
  const success_rate = total_executions > 0 ? success_executions / total_executions : 0;

  statistics.value = {
    total_executions,
    success_executions,
    failed_executions,
    success_rate,
  };
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
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
}

// 清理日志
function handleCleanLogs() {
  ElMessage.info('清理日志功能开发中...');
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
function handleDetail(_row: SchedulerLog) {
  ElMessage.info('日志详情功能开发中...');
}

// 格式化成功率
function formatSuccessRate(rate: number): string {
  if (rate === 0) return '0%';
  return `${(rate * 100).toFixed(1)}%`;
}

// 初始加载
onMounted(() => {
  loadJobOptions();
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col">
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
              style="width: 200px"
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
              placeholder="请选择"
              clearable
              style="width: 120px"
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
              style="width: 180px"
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
              style="width: 180px"
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
        <ElCard class="stat-card stat-card-gray" shadow="hover">
          <div class="stat-content">
            <div class="stat-value">{{ statistics.total_executions }}</div>
            <div class="stat-label">总执行次数</div>
          </div>
        </ElCard>
        <ElCard class="stat-card stat-card-success" shadow="hover">
          <div class="stat-content">
            <div class="stat-value">{{ statistics.success_executions }}</div>
            <div class="stat-label">成功次数</div>
          </div>
        </ElCard>
        <ElCard class="stat-card stat-card-fail" shadow="hover">
          <div class="stat-content">
            <div class="stat-value">{{ statistics.failed_executions }}</div>
            <div class="stat-label">失败次数</div>
          </div>
        </ElCard>
        <ElCard class="stat-card stat-card-rate" shadow="hover">
          <div class="stat-content">
            <div class="stat-value">{{ formatSuccessRate(statistics.success_rate) }}</div>
            <div class="stat-label">成功率</div>
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
              <span :class="`scheduler-status-${getLogStatusClass(row.status)}`">
                {{ getLogStatusLabel(row.status) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="duration" label="耗时" min-width="100" align="right">
            <template #default="{ row }">
              {{ formatDuration(row.duration) }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="result" label="执行结果" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.result || row.exception || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="hostname" label="执行主机" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.hostname || '-' }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="80" fixed="right">
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
    </div>
  </Page>
</template>

<style scoped>
/* 搜索区域 */
.scheduler-search-area {
  margin-bottom: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.scheduler-search-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
}

.scheduler-search-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.scheduler-search-label {
  display: block;
  font-size: 12px;
  color: #666;
}

.scheduler-search-buttons {
  display: flex;
  align-items: flex-end;
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
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card :deep(.el-card__body) {
  padding: 20px;
}

.stat-content {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}

/* 简洁风格背景（非渐变）*/
.stat-card-gray {
  background: #f5f5f5;
}

.stat-card-gray .stat-value {
  color: #333;
}

.stat-card-success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.stat-card-success .stat-value {
  color: #52c41a;
}

.stat-card-fail {
  background: #fff2f0;
  border: 1px solid #ffccc7;
}

.stat-card-fail .stat-value {
  color: #ff4d4f;
}

.stat-card-rate {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

.stat-card-rate .stat-value {
  color: #1890ff;
}

/* 表格区域 */
.scheduler-table-wrapper {
  flex: 1;
  overflow: auto;
  background: #fff;
  padding: 16px;
  border-radius: 4px;
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
  background: #fafafa !important;
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
  white-space: nowrap;
}

/* 表格单元格样式 */
.scheduler-table :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
  border-right: 1px solid #e8e8e8 !important;
  border-bottom: 1px solid #e8e8e8 !important;
}

/* 状态样式 */
.scheduler-status-success {
  color: #52c41a;
  font-weight: 500;
}

.scheduler-status-danger {
  color: #ff4d4f;
  font-weight: 500;
}

.scheduler-status-warning {
  color: #faad14;
  font-weight: 500;
}

.scheduler-status-info {
  color: #1890ff;
  font-weight: 500;
}

/* 操作链接 */
.scheduler-link {
  color: #1890ff;
  cursor: pointer;
  margin-right: 12px;
  text-decoration: none;
}

.scheduler-link:hover {
  text-decoration: underline;
}

/* 分页 */
.scheduler-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0 0;
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
</style>