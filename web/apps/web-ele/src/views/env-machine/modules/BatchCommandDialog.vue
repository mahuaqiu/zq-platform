<script lang="ts" setup>
import type { EnvMachine, CommandResultItem } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import {
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
  ElScrollbar,
} from 'element-plus';

import { batchExecuteCommandApi } from '#/api/core/env-machine';

interface Props {
  visible: boolean;
  selectedMachines: EnvMachine[];
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 命令输入
const command = ref('');

// 执行状态
const executing = ref(false);
const currentBatch = ref(0);
const totalBatches = ref(0);

// 执行结果
const results = ref<CommandResultItem[]>([]);

// 设备类型统计
const deviceStats = computed(() => {
  const machines = props.selectedMachines;
  const supported = machines.filter(
    m => (m.device_type === 'windows' || m.device_type === 'mac') && !m.is_virtual
  );
  const windows = supported.filter(m => m.device_type === 'windows').length;
  const mac = supported.filter(m => m.device_type === 'mac').length;
  const unsupported = machines.length - supported.length;
  return { windows, mac, unsupported, supported };
});

// 命令输入提示
const commandPlaceholder = computed(() => {
  if (deviceStats.value.windows > 0 && deviceStats.value.mac > 0) {
    return 'Windows 输入 CMD 命令，Mac 输入 Shell 命令';
  }
  if (deviceStats.value.windows > 0) {
    return '请输入 CMD 命令（Windows）';
  }
  if (deviceStats.value.mac > 0) {
    return '请输入 Shell 命令（Mac）';
  }
  return '无支持的设备';
});

// 监听弹窗打开，清空数据
watch(() => props.visible, (newVal) => {
  if (newVal) {
    command.value = '';
    results.value = [];
    executing.value = false;
    currentBatch.value = 0;
    totalBatches.value = 0;
  }
});

// 关闭弹窗
function handleClose() {
  if (executing.value) {
    ElMessage.warning('正在执行命令，请等待完成后再关闭');
    return;
  }
  emit('update:visible', false);
}

// 执行命令
async function handleExecute() {
  if (!command.value.trim()) {
    ElMessage.warning('请输入命令内容');
    return;
  }

  if (deviceStats.value.supported === 0) {
    ElMessage.warning('选中的设备不支持命令执行（仅支持 Windows/Mac 真实设备）');
    return;
  }

  executing.value = true;
  results.value = [];

  // 获取支持的设备
  const supportedMachines = props.selectedMachines.filter(
    m => (m.device_type === 'windows' || m.device_type === 'mac') && !m.is_virtual
  );

  // 分批执行（每批 20 台）
  const batchSize = 20;
  const batches: EnvMachine[][] = [];
  for (let i = 0; i < supportedMachines.length; i += batchSize) {
    batches.push(supportedMachines.slice(i, i + batchSize));
  }
  totalBatches.value = batches.length;

  // 逐批执行
  for (let i = 0; i < batches.length; i++) {
    currentBatch.value = i + 1;
    const batchIds = batches[i].map(m => m.id);

    try {
      const res = await batchExecuteCommandApi({
        ids: batchIds,
        command: command.value.trim(),
      });
      results.value.push(...res.results);
    } catch (error: any) {
      // 批次请求失败，标记所有设备为失败
      for (const machine of batches[i]) {
        results.value.push({
          id: machine.id,
          ip: machine.ip || '',
          device_type: machine.device_type,
          device_name: machine.asset_number || machine.ip || machine.id,
          success: false,
          stdout: '',
          stderr: error?.message || '请求失败',
          duration_seconds: 0,
        });
      }
    }
  }

  executing.value = false;

  // 显示完成提示
  const successCount = results.value.filter(r => r.success).length;
  const failedCount = results.value.length - successCount;
  if (failedCount === 0) {
    ElMessage.success(`全部执行成功 (${successCount} 台)`);
  } else if (successCount === 0) {
    ElMessage.error(`全部执行失败 (${failedCount} 台)`);
  } else {
    ElMessage.warning(`执行完成：成功 ${successCount} 台，失败 ${failedCount} 台`);
  }
}

// 格式化结果项标题
function getResultTitle(result: CommandResultItem): string {
  const typeText = result.device_type === 'windows' ? 'Windows' : 'Mac';
  return `${result.device_name || result.ip} (${typeText})`;
}

// 格式化耗时
function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`;
  }
  return `${seconds.toFixed(1)}s`;
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="批量执行命令"
    width="700px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <!-- 设备统计 -->
    <div class="stats-area">
      <div class="stats-row">
        已选中 <strong>{{ props.selectedMachines.length }}</strong> 台设备
        <span v-if="deviceStats.windows > 0">（Windows: {{ deviceStats.windows }}）</span>
        <span v-if="deviceStats.mac > 0">（Mac: {{ deviceStats.mac }}）</span>
      </div>
      <div v-if="deviceStats.unsupported > 0" class="stats-warning">
        注意：{{ deviceStats.unsupported }} 台设备不支持命令执行（iOS/Android 或虚拟设备），已自动过滤
      </div>
    </div>

    <!-- 命令输入 -->
    <div class="command-area">
      <div class="command-label">命令内容：</div>
      <ElInput
        v-model="command"
        type="textarea"
        :rows="3"
        :placeholder="commandPlaceholder"
        :disabled="executing"
      />
    </div>

    <!-- 执行进度 -->
    <div v-if="executing" class="progress-area">
      正在执行... 第 {{ currentBatch }}/{{ totalBatches }} 批
    </div>

    <!-- 执行按钮 -->
    <div class="button-area">
      <ElButton @click="handleClose">取消</ElButton>
      <ElButton
        type="primary"
        :loading="executing"
        :disabled="deviceStats.supported === 0"
        @click="handleExecute"
      >
        执行命令
      </ElButton>
    </div>

    <!-- 执行结果 -->
    <div v-if="results.length > 0" class="result-area">
      <div class="result-header">
        执行结果：
        <span class="result-summary">
          成功 {{ results.filter(r => r.success).length }} 台，
          失败 {{ results.filter(r => !r.success).length }} 台
        </span>
      </div>
      <ElScrollbar height="300px">
        <div class="result-list">
          <div
            v-for="result in results"
            :key="result.id"
            class="result-item"
            :class="{ 'result-success': result.success, 'result-failed': !result.success }"
          >
            <div class="result-title">
              <span class="result-icon">{{ result.success ? '✓' : '✗' }}</span>
              {{ getResultTitle(result) }}
              <span class="result-status">{{ result.success ? '成功' : '失败' }}</span>
              <span class="result-duration">{{ formatDuration(result.duration_seconds) }}</span>
            </div>
            <div v-if="result.stdout" class="result-output">
              <div class="output-label">stdout:</div>
              <pre class="output-content">{{ result.stdout }}</pre>
            </div>
            <div v-if="result.stderr" class="result-output result-stderr">
              <div class="output-label">stderr:</div>
              <pre class="output-content">{{ result.stderr }}</pre>
            </div>
          </div>
        </div>
      </ElScrollbar>
    </div>
  </ElDialog>
</template>

<style scoped>
.stats-area {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 4px;
}

.stats-row {
  font-size: 14px;
}

.stats-row strong {
  color: #1890ff;
}

.stats-warning {
  margin-top: 8px;
  font-size: 12px;
  color: #ff4d4f;
}

.command-area {
  margin-bottom: 16px;
}

.command-label {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
}

.progress-area {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #e6f7ff;
  border-radius: 4px;
  color: #1890ff;
  font-size: 13px;
}

.button-area {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 16px;
}

.result-area {
  margin-top: 16px;
}

.result-header {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
}

.result-summary {
  font-size: 12px;
  color: #666;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item {
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.result-success {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.result-failed {
  background: #fff2f0;
  border-color: #ffccc7;
}

.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
}

.result-icon {
  font-size: 16px;
}

.result-success .result-icon {
  color: #52c41a;
}

.result-failed .result-icon {
  color: #ff4d4f;
}

.result-status {
  font-size: 12px;
}

.result-success .result-status {
  color: #52c41a;
}

.result-failed .result-status {
  color: #ff4d4f;
}

.result-duration {
  font-size: 12px;
  color: #999;
}

.result-output {
  margin-top: 8px;
}

.output-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.output-content {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  background: #fafafa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-stderr .output-content {
  color: #ff4d4f;
}
</style>