<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { startCollect, getCollectStatus } from '#/api/core/performance-monitor';
import type { TargetProcessConfig } from '#/api/core/performance-monitor';

const props = defineProps<{
  visible: boolean;
  deviceId: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'started', collectId: string): void;
}>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
});

// 采集频率
const interval = ref(5);
const intervalOptions = [1, 5, 10, 30];

// 进程列表（模拟数据，实际应从 Worker 获取）
const processList = ref<Array<{ name: string; pid: number; cpu: number }>>([]);
const searchQuery = ref('');
const selectedProcesses = ref<TargetProcessConfig[]>([]);
const loading = ref(false);

// 预设常用进程
const presetProcesses = ['chrome.exe', 'node.exe', 'python.exe', 'vscode.exe'];

const filteredProcesses = computed(() => {
  if (!searchQuery.value) return processList.value;
  return processList.value.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
  );
});

async function fetchProcesses() {
  loading.value = true;
  // 实际应调用 Worker API 获取进程列表
  // 这里模拟一些数据
  processList.value = [
    { name: 'chrome.exe', pid: 1234, cpu: 5.2 },
    { name: 'chrome.exe', pid: 2345, cpu: 4.8 },
    { name: 'node.exe', pid: 4567, cpu: 6.1 },
    { name: 'python.exe', pid: 6789, cpu: 3.2 },
    { name: 'vscode.exe', pid: 8901, cpu: 2.5 },
  ];
  loading.value = false;
}

function toggleProcess(name: string, pid: number) {
  const existing = selectedProcesses.value.find((p) => p.name === name);
  if (existing) {
    if (existing.pids?.includes(pid)) {
      existing.pids = existing.pids.filter((id) => id !== pid);
      if (existing.pids.length === 0) {
        selectedProcesses.value = selectedProcesses.value.filter(
          (p) => p.name !== name,
        );
      }
    } else {
      existing.pids = [...(existing.pids || []), pid];
    }
  } else {
    selectedProcesses.value.push({ name, pids: [pid] });
  }
}

function isProcessSelected(name: string, pid: number): boolean {
  const existing = selectedProcesses.value.find((p) => p.name === name);
  return existing?.pids?.includes(pid) || false;
}

async function handleStart() {
  if (selectedProcesses.value.length === 0) {
    ElMessage.warning('请选择目标进程');
    return;
  }

  try {
    loading.value = true;
    const result = await startCollect({
      device_id: props.deviceId,
      interval: interval.value,
      target_processes: selectedProcesses.value,
    });
    ElMessage.success('采集已开始');
    emit('started', result.collect_id);
    dialogVisible.value = false;
  } catch (error) {
    ElMessage.error('开始采集失败');
  } finally {
    loading.value = false;
  }
}

watch(dialogVisible, (v) => {
  if (v) {
    fetchProcesses();
    selectedProcesses.value = [];
  }
});
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="采集配置"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="collect-dialog">
      <!-- 采集频率 -->
      <div class="config-section">
        <div class="section-label">采集频率</div>
        <div class="interval-config">
          <el-input-number
            v-model="interval"
            :min="1"
            :max="60"
            size="small"
          />
          <span class="interval-unit">秒</span>
          <div class="interval-buttons">
            <el-button
              v-for="opt in intervalOptions"
              :key="opt"
              size="small"
              :type="interval === opt ? 'primary' : 'default'"
              @click="interval = opt"
            >
              {{ opt }}秒
            </el-button>
          </div>
        </div>
      </div>

      <!-- 目标进程 -->
      <div class="config-section">
        <div class="section-label">目标进程</div>
        <div class="preset-buttons">
          <el-button
            v-for="name in presetProcesses"
            :key="name"
            size="small"
            @click="searchQuery = name"
          >
            {{ name }}
          </el-button>
        </div>
        <el-input
          v-model="searchQuery"
          placeholder="搜索进程名"
          size="small"
          clearable
          style="margin-bottom: 12px"
        />
        <div class="process-list" v-loading="loading">
          <div
            v-for="proc in filteredProcesses"
            :key="`${proc.name}-${proc.pid}`"
            class="process-item"
          >
            <el-checkbox
              :model-value="isProcessSelected(proc.name, proc.pid)"
              @change="toggleProcess(proc.name, proc.pid)"
            />
            <span class="process-name">{{ proc.name }}</span>
            <span class="process-pid">PID: {{ proc.pid }}</span>
            <span class="process-cpu">{{ proc.cpu.toFixed(1) }}%</span>
          </div>
        </div>
        <div class="selected-summary">
          已选择:
          <span v-for="(p, i) in selectedProcesses" :key="i">
            {{ p.name }}({{ p.pids?.length || 0 }})
          </span>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleStart">
        开始采集
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.collect-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.config-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.section-label {
  font-size: 14px;
  font-weight: 600;
}
.interval-config {
  display: flex;
  align-items: center;
  gap: 8px;
}
.interval-unit {
  font-size: 12px;
  color: #666;
}
.interval-buttons {
  display: flex;
  gap: 4px;
}
.preset-buttons {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}
.process-list {
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 8px;
  max-height: 200px;
  overflow-y: auto;
}
.process-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.process-name {
  flex: 1;
  font-size: 12px;
}
.process-pid {
  font-size: 11px;
  color: #666;
}
.process-cpu {
  font-size: 11px;
  color: #e6a23c;
}
.selected-summary {
  font-size: 11px;
  color: #666;
}
</style>