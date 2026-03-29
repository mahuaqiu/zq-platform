<script lang="ts" setup>
import type { TestReportDetail } from '#/api/core/test-report';

import { ref, onMounted, watch } from 'vue';

import {
  ElButton,
  ElMessage,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTabPane,
} from 'element-plus';

import { getReportDetailApi, getCaseLogApi } from '#/api/core/test-report';

import LogDialog from './LogDialog.vue';

const props = defineProps<{
  taskId: string;
}>();

// Tab 分类
type Category = 'final_fail' | 'always_fail' | 'unstable' | 'all';
const activeTab = ref<Category>('final_fail');

// 数据
const tableData = ref<TestReportDetail[]>([]);
const loading = ref(false);

// 日志弹窗
const logDialogVisible = ref(false);
const currentLogUrl = ref<string | null>(null);
const currentCaseName = ref('');

// 分类标签映射
const TAB_LABELS: Record<Category, string> = {
  final_fail: '最终失败',
  always_fail: '每轮都失败',
  unstable: '不稳定用例',
  all: '全部记录',
};

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getReportDetailApi(props.taskId, activeTab.value);
    tableData.value = res.items || [];
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 查看日志
async function handleViewLog(row: TestReportDetail) {
  currentCaseName.value = row.caseName;

  // 优先使用已有的 logUrl
  if (row.logUrl) {
    currentLogUrl.value = row.logUrl;
    logDialogVisible.value = true;
    return;
  }

  // 没有的话调用 API 获取
  try {
    const res = await getCaseLogApi(props.taskId, row.caseName);
    currentLogUrl.value = res.logUrl;
  } catch {
    currentLogUrl.value = null;
  }
  logDialogVisible.value = true;
}

// 格式化失败时间
function formatFailTime(time: string | null) {
  if (!time) return '--';
  const date = new Date(time);
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

// 监听 tab 切换
watch(activeTab, () => {
  loadData();
});

// 监听 taskId 变化
watch(
  () => props.taskId,
  () => {
    if (props.taskId) {
      loadData();
    }
  },
);

// 初始加载
onMounted(() => {
  if (props.taskId) {
    loadData();
  }
});
</script>

<template>
  <div class="fail-table">
    <ElTabs v-model="activeTab" class="fail-tabs">
      <ElTabPane
        v-for="(label, key) in TAB_LABELS"
        :key="key"
        :label="label"
        :name="key"
      />
    </ElTabs>

    <ElTable :data="tableData" v-loading="loading" class="fail-table-inner" border>
      <ElTableColumn prop="caseName" label="用例名称" min-width="200" show-overflow-tooltip />
      <ElTableColumn prop="caseFailStep" label="失败步骤" min-width="120">
        <template #default="{ row }">
          <span class="fail-step">{{ row.caseFailStep }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="caseFailLog" label="失败日志" min-width="300">
        <template #default="{ row }">
          <div class="fail-log-cell">
            <div class="fail-log-preview">{{ row.caseFailLog }}</div>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="failTime" label="失败时间" min-width="80" align="center">
        <template #default="{ row }">
          {{ formatFailTime(row.failTime) }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" min-width="100" align="center">
        <template #default="{ row }">
          <a class="fail-link" @click="handleViewLog(row)">查看完整日志</a>
        </template>
      </ElTableColumn>
    </ElTable>

    <LogDialog
      v-model:visible="logDialogVisible"
      :log-url="currentLogUrl"
      :case-name="currentCaseName"
    />
  </div>
</template>

<style scoped>
.fail-table {
  padding: 16px;
  background: #f5f7fa;
}

.fail-tabs {
  margin-bottom: 16px;
}

.fail-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.fail-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.fail-table-inner {
  --el-table-border-color: #e8e8e8;
  --el-table-header-bg-color: #fafafa;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fafafa;
  --el-table-text-color: #333;
  --el-table-header-text-color: #333;
  background: #fff;
}

.fail-table-inner :deep(th.el-table__cell) {
  background: #fafafa !important;
  padding: 12px 10px !important;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  border-color: #e8e8e8 !important;
}

.fail-table-inner :deep(td.el-table__cell) {
  padding: 12px 10px !important;
  font-size: 13px;
  color: #333;
  border-color: #e8e8e8 !important;
}

.fail-step {
  color: #ff4d4f;
}

.fail-log-cell {
  max-height: 60px;
  overflow: hidden;
}

.fail-log-preview {
  background: #fafafa;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fail-link {
  color: #1890ff;
  cursor: pointer;
  text-decoration: none;
}

.fail-link:hover {
  text-decoration: underline;
}
</style>