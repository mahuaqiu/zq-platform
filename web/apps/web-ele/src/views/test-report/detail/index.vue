<script lang="ts" setup>
import type { TestReportSummary } from '#/api/core/test-report';

import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import { ElButton, ElMessage } from 'element-plus';

import { getReportSummaryApi } from '#/api/core/test-report';

import StatsCards from './components/StatsCards.vue';
import RoundAnalysis from './components/RoundAnalysis.vue';
import StepDistribution from './components/StepDistribution.vue';
import FailTable from './components/FailTable.vue';

defineOptions({ name: 'TestReportDetailPage' });

const route = useRoute();
const router = useRouter();

// 数据
const summary = ref<TestReportSummary | null>(null);
const loading = ref(false);

// 从路由获取 taskId
const taskId = route.params.task_id as string;

// 格式化执行时间
function formatExecuteTime(time: string | null) {
  if (!time) return '--';
  const date = new Date(time);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

// 加载数据
async function loadData() {
  if (!taskId) return;

  loading.value = true;
  try {
    summary.value = await getReportSummaryApi(taskId);
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 返回列表
function handleBack() {
  router.push('/test-report/list');
}

// 导出报告（暂未实现）
function handleExport() {
  ElMessage.info('导出功能开发中...');
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="detail-page" v-loading="loading">
      <!-- 顶部信息区 -->
      <div class="detail-header">
        <div class="header-info">
          <span class="header-title">任务名称：{{ summary?.taskName ?? '--' }}</span>
          <span class="header-time">执行时间：{{ formatExecuteTime(summary?.executeTime ?? null) }}</span>
        </div>
        <div class="header-actions">
          <ElButton class="btn-export" @click="handleExport">导出报告</ElButton>
          <ElButton class="btn-back" @click="handleBack">返回列表</ElButton>
        </div>
      </div>

      <!-- 统计卡片 -->
      <StatsCards :summary="summary" :loading="loading" />

      <!-- AI 分析区 -->
      <div class="ai-analysis">
        <div class="ai-title">AI 分析结论</div>
        <div class="ai-content">
          <p v-if="summary?.aiAnalysis">{{ summary.aiAnalysis }}</p>
          <p v-else class="ai-pending">等待 AI 分析任务执行...（可配置定时任务触发分析）</p>
          <p class="ai-hint" v-if="!summary?.aiAnalysis">分析内容将包括：失败原因归类、可能的根因建议、需要关注的用例列表</p>
        </div>
      </div>

      <!-- 轮次分析 -->
      <RoundAnalysis :round-stats="summary?.roundStats ?? null" />

      <!-- 失败步骤分布 -->
      <StepDistribution :step-distribution="summary?.stepDistribution ?? null" />

      <!-- 失败记录表格 -->
      <FailTable :task-id="taskId" />
    </div>
  </Page>
</template>

<style scoped>
.detail-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: auto;
  background: #f0f2f5;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.header-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #111;
}

.header-time {
  font-size: 14px;
  color: #666;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* 导出报告按钮 - 蓝色边框 */
.btn-export {
  background: #fff;
  color: #1890ff;
  border: 1px solid #1890ff;
}

/* 返回列表按钮 - 浅灰背景 */
.btn-back {
  background: #f5f5f5;
  color: #666;
  border: 1px solid #d9d9d9;
}

/* AI 分析区 */
.ai-analysis {
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  margin: 16px;
}

.ai-title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #111;
}

.ai-content {
  padding: 16px;
  color: #1e40af;
  background: #eff6ff;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
}

.ai-content p {
  margin: 0;
}

.ai-pending {
  color: #999;
}

.ai-hint {
  margin-top: 8px !important;
  font-size: 12px;
  color: #999;
}
</style>