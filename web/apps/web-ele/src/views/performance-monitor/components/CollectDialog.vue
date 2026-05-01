<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { ElMessage, ElDialog, ElInput, ElCheckbox, ElSelect, ElOption } from 'element-plus';
import { startCollect } from '#/api/core/performance-monitor';
import type { TargetProcessConfig } from '#/api/core/performance-monitor';

const props = defineProps<{
  visible: boolean;
  deviceId: string;
  deviceInfo?: { ip: string; status: string; device_type?: string };
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'started', collectId: string): void;
}>();

// 设备显示信息
const deviceDisplay = computed(() => {
  if (props.deviceInfo) {
    const deviceType = props.deviceInfo.device_type || 'windows';
    return `${deviceType}-${props.deviceInfo.ip}`;
  }
  return '未选择设备';
});
const interval = ref(5);
const intervalOptions = [1, 5, 10, 30];

// 进程列表（模拟数据）
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
    emit('update:visible', false);
  } catch (error) {
    ElMessage.error('开始采集失败');
  } finally {
    loading.value = false;
  }
}

function selectAll() {
  selectedProcesses.value = processList.value.map((p) => ({
    name: p.name,
    pids: [p.pid],
  }));
}

function clearAll() {
  selectedProcesses.value = [];
}

watch(() => props.visible, (v) => {
  if (v) {
    fetchProcesses();
    selectedProcesses.value = [];
  }
});
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
    width="500px"
    destroy-on-close
    align-center
    :close-on-click-modal="false"
    class="collect-dialog"
  >
    <!-- 弹窗标题 -->
    <template #header>
      <div class="dialog-title">开始性能采集</div>
    </template>
    <!-- 设备信息 -->
    <div class="device-info">
      <div class="device-label">目标设备</div>
      <div class="device-name">{{ deviceDisplay }}</div>
    </div>

    <!-- 目标进程选择 -->
    <div class="process-section">
      <div class="section-title">目标进程 <span class="subtitle">（可多选）</span></div>

      <!-- 搜索框 -->
      <div class="search-wrapper">
        <el-input
          v-model="searchQuery"
          placeholder="搜索进程名称..."
          size="small"
          clearable
        />
      </div>

      <!-- 预置进程名标签 -->
      <div class="preset-tags">
        <span
          v-for="name in presetProcesses"
          :key="name"
          class="preset-tag"
          @click="searchQuery = name"
        >
          {{ name }}
        </span>
      </div>

      <!-- 进程列表 -->
      <div class="process-list" v-loading="loading">
        <div
          v-for="proc in filteredProcesses"
          :key="`${proc.name}-${proc.pid}`"
          :class="['process-item', isProcessSelected(proc.name, proc.pid) ? 'selected' : '']"
        >
          <el-checkbox
            :model-value="isProcessSelected(proc.name, proc.pid)"
            @change="toggleProcess(proc.name, proc.pid)"
          />
          <span class="process-name">{{ proc.name }}</span>
          <span class="process-pid">PID: {{ proc.pid }}</span>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="quick-actions">
        <button class="quick-btn" @click="selectAll">全选</button>
        <button class="quick-btn" @click="clearAll">清空</button>
        <span class="selected-count">已选 {{ selectedProcesses.length }} 个进程</span>
      </div>
    </div>

    <!-- 采集配置 -->
    <div class="config-section">
      <div class="section-title">采集配置</div>
      <div class="config-item">
        <div class="config-label">采集间隔</div>
        <el-select v-model="interval" size="small" style="width: 100%">
          <el-option
            v-for="opt in intervalOptions"
            :key="opt"
            :label="`${opt}秒`"
            :value="opt"
          />
        </el-select>
      </div>
      <div class="config-tip">
        <b>说明：</b>采集间隔越小，数据越精细，但占用更多存储空间。点击"停止采集"手动结束。
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <button class="cancel-btn" @click="emit('update:visible', false)">取消</button>
        <button class="start-btn" :disabled="loading" @click="handleStart">
          {{ loading ? '加载中...' : '开始采集' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}
.device-info {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 4px;
}
.device-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 4px;
}
.device-name {
  font-size: 12px;
  font-weight: 600;
  color: #67c23a;
}
.process-section {
  margin-bottom: 12px;
}
.section-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}
.subtitle {
  color: #999;
  font-weight: normal;
}
.search-wrapper {
  margin-bottom: 6px;
}
.preset-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.preset-tag {
  padding: 3px 8px;
  background: #e6f7ff;
  color: #409eff;
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
  border: 1px solid #91d5ff;
}
.preset-tag:hover {
  background: #bae7ff;
}
.process-list {
  border: 1px solid #eee;
  border-radius: 4px;
  max-height: 180px;
  overflow-y: auto;
  padding: 8px;
}
.process-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 3px;
  margin-bottom: 4px;
}
.process-item.selected {
  background: #f0f9eb;
}
.process-name {
  flex: 1;
  font-size: 11px;
}
.process-pid {
  font-size: 10px;
  color: #999;
}
.quick-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  align-items: center;
}
.quick-btn {
  padding: 4px 10px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
}
.quick-btn:hover {
  background: #eee;
}
.selected-count {
  font-size: 10px;
  color: #999;
  margin-left: auto;
}
.config-section {
  margin-bottom: 16px;
}
.config-item {
  margin-bottom: 8px;
}
.config-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 4px;
}
.config-tip {
  font-size: 10px;
  color: #999;
  padding: 6px 10px;
  background: #f8f9fa;
  border-radius: 4px;
}
.dialog-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.cancel-btn {
  padding: 8px 20px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.cancel-btn:hover {
  background: #eee;
}
.start-btn {
  padding: 8px 20px;
  background: #67c23a;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.start-btn:hover {
  background: #5cb85c;
}
.start-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>