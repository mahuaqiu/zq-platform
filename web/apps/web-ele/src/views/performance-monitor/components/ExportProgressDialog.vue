<script setup lang="ts">
import type { ExportTaskStatus } from '#/api/core/performance-monitor';

import { computed, onUnmounted, ref, watch } from 'vue';

import { ElButton, ElDialog, ElMessage, ElProgress } from 'element-plus';

import {
  getExportDownloadUrl,
  getExportStatus,
} from '#/api/core/performance-monitor';

const props = defineProps<{
  taskId: string;
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'completed'): void;
}>();

const status = ref<ExportTaskStatus>({
  task_id: '',
  status: 'pending',
  progress: 0,
  message: '',
});

const pollingTimer = ref<null | number>(null);
const retryCount = ref(0);
const MAX_RETRY = 3;
const POLLING_INTERVAL = 3000;

const isCompleted = computed(() => status.value.status === 'completed');
const isFailed = computed(() => status.value.status === 'failed');
const downloadUrl = computed(() => getExportDownloadUrl(props.taskId));

async function pollStatus() {
  try {
    const result = await getExportStatus(props.taskId);
    status.value = result;
    retryCount.value = 0;

    if (isCompleted.value || isFailed.value) {
      stopPolling();
    }
  } catch {
    retryCount.value++;
    if (retryCount.value >= MAX_RETRY) {
      ElMessage.error('网络异常，请稍后重试');
      stopPolling();
    }
  }
}

function startPolling() {
  pollStatus();
  pollingTimer.value = window.setInterval(pollStatus, POLLING_INTERVAL);
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

function handleDownload() {
  window.open(downloadUrl.value, '_blank');
  emit('completed');
}

function handleClose() {
  emit('update:visible', false);
}

watch(
  () => props.visible,
  (newVal) => {
    if (newVal && props.taskId) {
      startPolling();
    } else {
      stopPolling();
    }
  },
);

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="导出报告"
    width="400px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="export-progress">
      <ElProgress
        :percentage="status.progress"
        :status="isCompleted ? 'success' : isFailed ? 'exception' : undefined"
      />
      <div class="status-message">{{ status.message }}</div>

      <div v-if="isCompleted" class="download-section">
        <ElButton type="success" @click="handleDownload"> 下载文件 </ElButton>
      </div>

      <div v-if="isFailed" class="error-section">
        <span class="error-text">导出失败：{{ status.message }}</span>
      </div>
    </div>

    <template #footer>
      <ElButton @click="handleClose">
        {{ isCompleted || isFailed ? '关闭' : '取消' }}
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.export-progress {
  text-align: center;
}

.status-message {
  margin-top: 16px;
  color: #666;
}

.download-section {
  margin-top: 20px;
}

.error-section {
  margin-top: 20px;
  color: #f56c6c;
}
</style>
