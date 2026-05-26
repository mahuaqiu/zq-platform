<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { ElMessage, ElDialog, ElInput, ElCheckbox, ElSelect, ElOption, ElRadioGroup, ElRadioButton } from 'element-plus';
import { startCollect, getProcesses } from '#/api/core/performance-monitor';
import type { TargetProcessConfig, ProcessInfo } from '#/api/core/performance-monitor';
import { getDisplayProcesses, saveProcessesToHistory } from '../config';

const props = defineProps<{
  visible: boolean;
  deviceId: string;
  deviceInfo?: { ip: string; status: string; device_type?: string };
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'started', collectId: string): void;
}>();

// 判断是否为 Linux 设备
const isLinuxDevice = computed(() => {
  return props.deviceInfo?.device_type === 'linux';
});

// 设备显示信息
const deviceDisplay = computed(() => {
  if (props.deviceInfo) {
    const deviceType = props.deviceInfo.device_type || 'windows';
    return `${deviceType}-${props.deviceInfo.ip}`;
  }
  return '未选择设备';
});

// 弹窗标题（Linux 设备显示简化标题）
const dialogTitle = computed(() => {
  if (isLinuxDevice.value) {
    return '开始系统性能采集';
  }
  return '开始性能采集';
});
const interval = ref(5);
const intervalOptions = [1, 3, 5, 10, 30];

// 采集模式：'pid' 按PID采集，'name' 按进程名采集（采集该进程名下所有实例）
const collectMode = ref<'pid' | 'name'>('pid');

// 进程列表
const processList = ref<Array<{ name: string; pid: number; cpu: number }>>([]);
const searchQuery = ref('');
// 进程名模式下：存储选中的进程名列表；PID模式下：存储 TargetProcessConfig
const selectedProcessNames = ref<string[]>([]);
const selectedProcesses = ref<TargetProcessConfig[]>([]);
const loading = ref(false);

// 动态获取进程推荐列表（优先历史记录，其次预设配置）
const presetProcesses = ref<string[]>(getDisplayProcesses());

// 手动输入的进程名
const manualInput = ref('');

// 根据采集模式计算选中状态
const selectedCount = computed(() => {
  if (collectMode.value === 'name') {
    return selectedProcessNames.value.length;
  }
  return selectedProcesses.value.length;
});

const filteredProcesses = computed(() => {
  if (!searchQuery.value) return processList.value;
  return processList.value.filter((p) =>
    p.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
  );
});

// 进程名模式下的唯一进程名列表（带实例数统计）
const uniqueProcessNames = computed(() => {
  // 先过滤搜索结果
  const filtered = searchQuery.value
    ? processList.value.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
      )
    : processList.value;

  // 统计每个进程名的实例数
  const nameCountMap = new Map<string, number>();
  for (const p of filtered) {
    nameCountMap.set(p.name, (nameCountMap.get(p.name) || 0) + 1);
  }

  // 当前运行的进程（带实例数统计）
  const runningProcesses = Array.from(nameCountMap.entries()).map(([name, count]) => ({
    name,
    instanceCount: count,
  }));

  // 手动输入但未运行的进程名（从选中列表中筛选）
  const manualProcesses = selectedProcessNames.value
    .filter((name) => !runningProcesses.some((p) => p.name === name))
    .map((name) => ({ name, instanceCount: 0 }));

  // 合并：手动输入的放在最前面（方便删除），当前运行的放在后面
  return [...manualProcesses, ...runningProcesses];
});

// 根据采集模式获取最终的目标进程配置
const finalTargetProcesses = computed<TargetProcessConfig[]>(() => {
  if (collectMode.value === 'name') {
    // 进程名模式：每个进程名下采集所有实例（pids 为 undefined）
    return selectedProcessNames.value.map((name) => ({
      name,
      pids: undefined,
    }));
  }
  // PID模式：采集指定PID
  return selectedProcesses.value;
});

async function fetchProcesses() {
  loading.value = true;
  try {
    const result = await getProcesses(props.deviceId, searchQuery.value);
    processList.value = result.processes.map((p: ProcessInfo) => ({
      name: p.name,
      pid: p.pid,
      cpu: p.cpu_usage,
    }));
  } catch (error) {
    ElMessage.error('获取进程列表失败');
    processList.value = [];
  } finally {
    loading.value = false;
  }
}

// PID模式：选中/取消选中进程
function toggleProcessPid(name: string, pid: number) {
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

// 进程名模式：选中/取消选中进程名
function toggleProcessName(name: string) {
  const idx = selectedProcessNames.value.indexOf(name);
  if (idx >= 0) {
    selectedProcessNames.value.splice(idx, 1);
  } else {
    selectedProcessNames.value.push(name);
  }
}

// 判断是否选中（根据采集模式）
function isProcessSelected(name: string, pid: number): boolean {
  if (collectMode.value === 'name') {
    return selectedProcessNames.value.includes(name);
  }
  const existing = selectedProcesses.value.find((p) => p.name === name);
  return existing?.pids?.includes(pid) || false;
}

/**
 * 验证进程名格式
 * 允许：chrome.exe、chrome、app.exe
 * 拒绝：chrome.dll、app.txt、空字符串
 */
function validateProcessName(name: string): boolean {
  if (!name || name.trim() === '') return false;
  const trimmed = name.trim();
  // 允许无扩展名或 .exe 后缀
  const hasNoExtension = !trimmed.includes('.');
  const hasExeExtension = trimmed.toLowerCase().endsWith('.exe');
  return hasNoExtension || hasExeExtension;
}

/**
 * 处理手动添加进程名
 * 1. 按逗号或分号分隔
 * 2. 验证每个进程名格式
 * 3. 过滤已存在的进程名（避免重复）
 * 4. 添加到选中列表
 */
function handleManualAdd() {
  const input = manualInput.value.trim();
  if (!input) return;

  // 按逗号或分号分隔
  const names = input.split(/[;,]/).map((n) => n.trim()).filter((n) => n);

  // 验证格式
  const invalidNames = names.filter((n) => !validateProcessName(n));
  if (invalidNames.length > 0) {
    ElMessage.warning(`格式无效: ${invalidNames.join(', ')}，请使用 .exe 或无扩展名`);
    return;
  }

  // 添加到选中列表（去重）
  const newNames = names.filter((n) => !selectedProcessNames.value.includes(n));
  if (newNames.length === 0) {
    ElMessage.info('所有进程名已存在');
    return;
  }

  selectedProcessNames.value.push(...newNames);
  ElMessage.success(`已添加 ${newNames.length} 个进程名`);
  manualInput.value = '';
}

async function handleStart() {
  // Linux 设备：无需选择进程，直接开始采集
  if (isLinuxDevice.value) {
    try {
      loading.value = true;
      const result = await startCollect({
        device_id: props.deviceId,
        interval: interval.value,
        target_processes: [],  // Linux 设备不传进程列表，采集系统级数据
      });
      ElMessage.success('系统性能采集已开始');
      emit('started', result.collect_id);
      emit('update:visible', false);
    } catch (error) {
      ElMessage.error('开始采集失败');
    } finally {
      loading.value = false;
    }
    return;
  }

  // Windows 设备：需要选择进程
  if (selectedCount.value === 0) {
    ElMessage.warning('请选择目标进程');
    return;
  }

  try {
    loading.value = true;
    const result = await startCollect({
      device_id: props.deviceId,
      interval: interval.value,
      target_processes: finalTargetProcesses.value,
    });
    // 保存到历史记录，下次优先显示
    const names = collectMode.value === 'name'
      ? selectedProcessNames.value
      : selectedProcesses.value.map((p) => p.name);
    saveProcessesToHistory(names);
    // 更新推荐列表
    presetProcesses.value = getDisplayProcesses();
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
  // 全选时使用过滤后的列表（搜索结果），而不是完整列表
  if (collectMode.value === 'name') {
    // 进程名模式：选中过滤后的所有唯一进程名
    selectedProcessNames.value = uniqueProcessNames.value.map((item) => item.name);
  } else {
    // PID模式：选中过滤后的所有进程的具体PID
    selectedProcesses.value = filteredProcesses.value.map((p) => ({
      name: p.name,
      pids: [p.pid],
    }));
  }
}

function clearAll() {
  selectedProcessNames.value = [];
  selectedProcesses.value = [];
}

// 采集模式切换时清空选择
watch(collectMode, () => {
  selectedProcessNames.value = [];
  selectedProcesses.value = [];
});

watch(() => props.visible, (v) => {
  if (v) {
    // Linux 设备不获取进程列表（采集系统级数据，无需选择进程）
    if (!isLinuxDevice.value) {
      fetchProcesses();
    }
    selectedProcessNames.value = [];
    selectedProcesses.value = [];
  }
});
</script>

<template>
  <el-dialog
    :model-value="props.visible"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
    width="600px"
    destroy-on-close
    align-center
    :close-on-click-modal="false"
    class="collect-dialog"
  >
    <!-- 弹窗标题（动态显示） -->
    <template #header>
      <div class="dialog-title">{{ dialogTitle }}</div>
    </template>
    <!-- 设备信息 -->
    <div class="device-info">
      <div class="device-label">目标设备</div>
      <div class="device-name">{{ deviceDisplay }}</div>
      <!-- Linux 设备特殊提示 -->
      <div v-if="isLinuxDevice" class="device-tip">
        Linux 设备将采集系统级 CPU/内存性能数据
      </div>
    </div>

    <!-- 目标进程选择（仅 Windows 设备显示） -->
    <div v-if="!isLinuxDevice" class="process-section">
      <div class="section-title">目标进程 <span class="subtitle">（可多选）</span></div>

      <!-- 采集模式选择 -->
      <div class="mode-selector">
        <el-radio-group v-model="collectMode" size="small">
          <el-radio-button value="pid">按PID采集</el-radio-button>
          <el-radio-button value="name">按进程名采集</el-radio-button>
        </el-radio-group>
        <div class="mode-tip">
          {{ collectMode === 'pid' ? '采集指定PID的进程' : '采集该进程名下所有实例（含未来启动的新实例）' }}
        </div>
      </div>

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

      <!-- 手动输入进程名（仅进程名模式） -->
      <div v-if="collectMode === 'name'" class="manual-input-wrapper">
        <el-input
          v-model="manualInput"
          placeholder="输入进程名(逗号或分号分隔)"
          size="small"
          clearable
          style="flex: 1"
        />
        <button class="add-btn" @click="handleManualAdd">添加</button>
      </div>

      <!-- 进程列表 -->
      <div class="process-list" v-loading="loading">
        <!-- PID模式：显示每个PID实例 -->
        <template v-if="collectMode === 'pid'">
          <div
            v-for="proc in filteredProcesses"
            :key="`${proc.name}-${proc.pid}`"
            :class="['process-item', isProcessSelected(proc.name, proc.pid) ? 'selected' : '']"
          >
            <el-checkbox
              :model-value="isProcessSelected(proc.name, proc.pid)"
              @change="toggleProcessPid(proc.name, proc.pid)"
            />
            <span class="process-name">{{ proc.name }}</span>
            <span class="process-pid">PID: {{ proc.pid }}</span>
          </div>
        </template>
        <!-- 进程名模式：显示去重后的进程名 -->
        <template v-else>
          <div
            v-for="item in uniqueProcessNames"
            :key="item.name"
            :class="['process-item', selectedProcessNames.includes(item.name) ? 'selected' : 'name-mode']"
          >
            <el-checkbox
              :model-value="selectedProcessNames.includes(item.name)"
              @change="toggleProcessName(item.name)"
            />
            <span class="process-name">{{ item.name }}</span>
            <span class="process-badge" v-if="item.instanceCount > 1">
              {{ item.instanceCount }}实例
            </span>
          </div>
        </template>
      </div>

      <!-- 快捷操作 -->
      <div class="quick-actions">
        <button class="quick-btn" @click="selectAll">全选</button>
        <button class="quick-btn" @click="clearAll">清空</button>
        <span class="selected-count">
          已选 {{ selectedCount }} 个{{ collectMode === 'name' ? '进程名' : '进程' }}
        </span>
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
        <template v-if="isLinuxDevice">
          <b>说明：</b>Linux 设备采集系统级 CPU/内存性能数据。采集间隔越小，数据越精细，但占用更多存储空间。点击"停止采集"手动结束。
        </template>
        <template v-else>
          <b>说明：</b>采集间隔越小，数据越精细，但占用更多存储空间。点击"停止采集"手动结束。
        </template>
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
  font-size: 16px;
  font-weight: 600;
  color: #333;
}
.device-info {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #f0f9eb;
  border-radius: 4px;
}
.device-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}
.device-name {
  font-size: 14px;
  font-weight: 600;
  color: #67c23a;
}
.device-tip {
  font-size: 13px;
  color: #e6a23c;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #d4e6c9;
}
.process-section {
  margin-bottom: 14px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}
.subtitle {
  color: #999;
  font-weight: normal;
}
.search-wrapper {
  margin-bottom: 8px;
}
.mode-selector {
  margin-bottom: 12px;
}
.mode-tip {
  font-size: 12px;
  color: #999;
  margin-top: 6px;
}
.preset-tags {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.preset-tag {
  padding: 4px 10px;
  background: #e6f7ff;
  color: #409eff;
  border-radius: 3px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid #91d5ff;
}
.preset-tag:hover {
  background: #bae7ff;
}
.process-list {
  border: 1px solid #eee;
  border-radius: 4px;
  max-height: 280px;
  overflow-y: auto;
  padding: 6px;
}
.process-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 3px;
  margin-bottom: 3px;
}
.process-item:last-child {
  margin-bottom: 0;
}
.process-item.selected {
  background: #f0f9eb;
}
.process-name {
  flex: 1;
  font-size: 13px;
}
.process-pid {
  font-size: 12px;
  color: #999;
}
.process-badge {
  font-size: 12px;
  color: #409eff;
  background: #e6f7ff;
  padding: 3px 8px;
  border-radius: 2px;
}
.process-item.name-mode.selected {
  background: #e6f7ff;
}
.quick-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
  align-items: center;
}
.quick-btn {
  padding: 6px 12px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 12px;
  cursor: pointer;
}
.quick-btn:hover {
  background: #eee;
}
.selected-count {
  font-size: 12px;
  color: #999;
  margin-left: auto;
}
.config-section {
  margin-bottom: 16px;
}
.config-item {
  margin-bottom: 10px;
}
.config-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}
.config-tip {
  font-size: 12px;
  color: #999;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 4px;
}
.dialog-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.cancel-btn {
  padding: 10px 24px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}
.cancel-btn:hover {
  background: #eee;
}
.start-btn {
  padding: 10px 24px;
  background: #67c23a;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}
.start-btn:hover {
  background: #5cb85c;
}
.start-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.manual-input-wrapper {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.add-btn {
  padding: 0 14px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 3px;
  font-size: 13px;
  cursor: pointer;
  height: 28px;
  line-height: 28px;
}
.add-btn:hover {
  background: #66b1ff;
}
</style>