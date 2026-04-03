<script lang="ts" setup>
import type { SchedulerLog } from '#/api/core/scheduler';

import { ref, watch } from 'vue';

import { ZqDialog } from '#/components/zq-dialog';

import { ElTag, ElDescriptions, ElDescriptionsItem, ElMessage } from 'element-plus';

import { getSchedulerLogDetailApi } from '#/api/core/scheduler';
import {
  formatDateTime,
  formatDuration,
  getLogStatusLabel,
  getLogStatusClass,
} from '../data';

// Props
interface Props {
  visible: boolean;
  logId?: string;
}

const props = defineProps<Props>();

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

// 数据
const logDetail = ref<SchedulerLog | null>(null);
const loading = ref(false);

// 获取日志详情
async function loadLogDetail() {
  if (!props.logId) {
    logDetail.value = null;
    return;
  }

  loading.value = true;
  try {
    const res = await getSchedulerLogDetailApi(props.logId);
    logDetail.value = res;
  } catch (error: any) {
    console.error('获取日志详情失败:', error);
    ElMessage.error(error?.message || '获取日志详情失败');
    logDetail.value = null;
  } finally {
    loading.value = false;
  }
}

// 监听 visible 和 logId 变化
watch(
  () => [props.visible, props.logId],
  ([visible, logId]) => {
    if (visible && logId) {
      loadLogDetail();
    } else if (!visible) {
      logDetail.value = null;
    }
  },
  { immediate: true },
);

// 同步弹窗状态给父组件
function handleUpdateVisible(val: boolean) {
  emit('update:visible', val);
}

// 获取状态标签类型
function getStatusType(status: string): 'success' | 'danger' | 'warning' | 'info' {
  switch (status) {
    case 'success':
      return 'success';
    case 'failed':
      return 'danger';
    case 'timeout':
      return 'warning';
    case 'running':
    case 'pending':
      return 'info';
    default:
      return 'info';
  }
}
</script>

<template>
  <ZqDialog
    :model-value="visible"
    title="日志详情"
    width="900px"
    :show-confirm-button="false"
    cancel-text="关闭"
    @update:model-value="handleUpdateVisible"
    @cancel="handleUpdateVisible(false)"
  >
    <div v-if="loading" class="loading-wrapper">
      <span>加载中...</span>
    </div>

    <div v-else-if="logDetail" class="log-detail-wrapper">
      <!-- 基本信息 -->
      <div class="detail-section">
        <h3 class="section-title">基本信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <label class="info-label">任务名称</label>
            <div class="info-value">{{ logDetail.job_name || '-' }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">任务编码</label>
            <div class="info-value">{{ logDetail.job_code || '-' }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">执行状态</label>
            <div class="info-value">
              <ElTag :type="getStatusType(logDetail.status)" size="small">
                {{ getLogStatusLabel(logDetail.status) }}
              </ElTag>
            </div>
          </div>
          <div class="info-item">
            <label class="info-label">开始时间</label>
            <div class="info-value">{{ formatDateTime(logDetail.start_time) }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">结束时间</label>
            <div class="info-value">{{ formatDateTime(logDetail.end_time) }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">执行耗时</label>
            <div class="info-value">{{ formatDuration(logDetail.duration) }}</div>
          </div>
        </div>
      </div>

      <!-- 执行环境 -->
      <div class="detail-section">
        <h3 class="section-title">执行环境</h3>
        <div class="info-grid">
          <div class="info-item">
            <label class="info-label">执行主机</label>
            <div class="info-value">{{ logDetail.hostname || '-' }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">进程ID</label>
            <div class="info-value">{{ logDetail.process_id || '-' }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">重试次数</label>
            <div class="info-value">{{ logDetail.retry_count ?? 0 }}</div>
          </div>
        </div>
      </div>

      <!-- 执行结果 -->
      <div class="detail-section">
        <h3 class="section-title">执行结果</h3>
        <div class="result-wrapper">
          <div v-if="logDetail.result" class="result-content">
            <label class="info-label">执行结果</label>
            <pre class="result-text">{{ logDetail.result }}</pre>
          </div>

          <!-- 异常堆栈 -->
          <div v-if="logDetail.exception || logDetail.traceback" class="error-wrapper">
            <label class="info-label error-label">异常信息</label>
            <div v-if="logDetail.exception" class="error-content">
              <div class="error-message">{{ logDetail.exception }}</div>
            </div>
            <pre v-if="logDetail.traceback" class="error-traceback">{{ logDetail.traceback }}</pre>
          </div>

          <div v-if="!logDetail.result && !logDetail.exception && !logDetail.traceback" class="empty-result">
            暂无执行结果
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-wrapper">
      <span>暂无数据</span>
    </div>
  </ZqDialog>
</template>

<style scoped>
.loading-wrapper,
.empty-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: #999;
  font-size: 14px;
}

.log-detail-wrapper {
  max-height: 70vh;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8e8e8;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.info-value {
  font-size: 14px;
  color: #333;
  word-break: break-all;
}

.result-wrapper {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-text {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
}

.error-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-label {
  color: #ff4d4f;
}

.error-content {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  padding: 12px;
}

.error-message {
  color: #ff4d4f;
  font-size: 14px;
  font-weight: 500;
}

.error-traceback {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
  color: #ff4d4f;
}

.empty-result {
  color: #999;
  font-size: 14px;
  text-align: center;
  padding: 24px;
}

/* 响应式：小屏幕下改为2列 */
@media (max-width: 768px) {
  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 576px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>