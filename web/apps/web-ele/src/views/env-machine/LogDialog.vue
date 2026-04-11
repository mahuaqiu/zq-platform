<script lang="ts" setup>
import { computed, nextTick, ref, watch } from 'vue';

import { ElButton, ElDialog, ElMessage, ElInput } from 'element-plus';

import { getMachineLogsApi } from '#/api/core/env-machine';

interface Props {
  visible: boolean;
  machineId: string;
  machineIp: string;
  machinePort: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const loading = ref(false);
const logLines = ref<string[]>([]);

// 刷新相关
const MAX_LOG_LINES = 3000;
const FETCH_LINES = 400;

// 搜索相关
const searchKeyword = ref('');
const currentMatchIndex = ref(-1);
const allMatchIndices = ref<number[]>([]);

// 日志容器 ref
const logContainerRef = ref<HTMLElement | null>(null);

// 统计信息
const lineCount = computed(() => logLines.value.length);

/**
 * 根据日志级别返回对应的 CSS 类
 */
function getLogLevelClass(line: string): string {
  const upper = line.toUpperCase();
  if (upper.includes('CRITICAL') || upper.includes('FATAL'))
    return 'log-critical';
  if (upper.includes('ERROR') || upper.includes('ERR')) return 'log-error';
  if (upper.includes('WARNING') || upper.includes('WARN')) return 'log-warning';
  if (upper.includes('DEBUG')) return 'log-debug';
  return 'log-info';
}

/**
 * 加载日志（首次打开）
 */
async function loadLogs() {
  if (!props.machineId) return;
  loading.value = true;
  try {
    const res = await getMachineLogsApi(props.machineId, FETCH_LINES);
    const text = res.content || '';
    const newLines = text.split('\n').filter((line) => line.trim() !== '');

    logLines.value = newLines;
    currentMatchIndex.value = -1;
    allMatchIndices.value = [];
    await nextTick();
    scrollToBottom();
  } catch (error: any) {
    console.error('获取日志失败:', error);
    ElMessage.error(error?.message || '获取日志失败');
  } finally {
    loading.value = false;
  }
}

/**
 * 刷新日志（追加模式，去重）
 */
async function refreshLogs() {
  if (!props.machineId) return;
  loading.value = true;
  try {
    const res = await getMachineLogsApi(props.machineId, FETCH_LINES);
    const text = res.content || '';
    const newLines = text.split('\n').filter((line) => line.trim() !== '');

    const existingLines = new Set(logLines.value);
    const linesToAdd: string[] = [];

    for (const line of newLines) {
      if (!existingLines.has(line)) {
        linesToAdd.push(line);
      }
    }

    if (linesToAdd.length > 0) {
      logLines.value = [...logLines.value, ...linesToAdd];

      if (logLines.value.length > MAX_LOG_LINES) {
        logLines.value = logLines.value.slice(-MAX_LOG_LINES);
        currentMatchIndex.value = -1;
        allMatchIndices.value = [];
      }

      await nextTick();
      scrollToBottom();
    } else {
      ElMessage.info('暂无新日志');
    }
  } catch (error: any) {
    console.error('获取日志失败:', error);
    ElMessage.error(error?.message || '获取日志失败');
  } finally {
    loading.value = false;
  }
}

/**
 * 复制日志到剪贴板
 */
async function copyLogs() {
  const text = logLines.value.join('\n');
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('日志已复制到剪贴板');
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    ElMessage.success('日志已复制到剪贴板');
  }
}

/**
 * 滚动到底部
 */
function scrollToBottom() {
  if (logContainerRef.value) {
    logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight;
  }
}

/**
 * 跳转到上一个匹配
 */
function prevMatch() {
  if (allMatchIndices.value.length === 0) return;
  currentMatchIndex.value =
    (currentMatchIndex.value - 1 + allMatchIndices.value.length) %
    allMatchIndices.value.length;
  scrollToMatch(currentMatchIndex.value);
}

/**
 * 跳转到下一个匹配
 */
function nextMatch() {
  if (allMatchIndices.value.length === 0) return;
  currentMatchIndex.value =
    (currentMatchIndex.value + 1) % allMatchIndices.value.length;
  scrollToMatch(currentMatchIndex.value);
}

/**
 * 滚动到指定匹配行
 */
function scrollToMatch(matchIdx: number) {
  const lineIdx = allMatchIndices.value[matchIdx];
  if (lineIdx === undefined) return;

  nextTick(() => {
    const container = logContainerRef.value;
    if (!container) return;

    const lineEl = container.querySelector(
      `[data-line="${lineIdx}"]`,
    ) as HTMLElement | null;
    if (lineEl) {
      lineEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  });
}

/**
 * 处理搜索输入键盘事件
 */
function handleSearchKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault();
    if (e.shiftKey) {
      prevMatch();
    } else {
      nextMatch();
    }
  }
}

/**
 * 判断某一行是否是当前搜索匹配项
 */
function isCurrentMatch(lineIndex: number): boolean {
  if (allMatchIndices.value.length === 0 || currentMatchIndex.value < 0)
    return false;
  return lineIndex === allMatchIndices.value[currentMatchIndex.value];
}

/**
 * 高亮搜索关键词
 */
function highlightSearch(text: string): string {
  if (!searchKeyword.value) return escapeHtml(text);
  const escaped = escapeHtml(text);
  const keyword = escapeHtml(searchKeyword.value);
  const regex = new RegExp(
    keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
    'gi',
  );
  return escaped.replace(regex, '<mark class="search-highlight">$&</mark>');
}

/**
 * HTML 转义
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * 监听弹窗打开，自动加载日志
 */
watch(
  () => props.visible,
  (val) => {
    if (val) {
      logLines.value = [];
      searchKeyword.value = '';
      currentMatchIndex.value = -1;
      allMatchIndices.value = [];
      loadLogs();
    }
  },
);

/**
 * 监听搜索关键词变化，计算匹配索引
 */
watch(
  [searchKeyword, logLines],
  ([keyword, lines]) => {
    if (!keyword || lines.length === 0) {
      allMatchIndices.value = [];
      currentMatchIndex.value = -1;
      return;
    }

    const indices: number[] = [];
    const lowerKeyword = keyword.toLowerCase();
    lines.forEach((line, index) => {
      if (line.toLowerCase().includes(lowerKeyword)) {
        indices.push(index);
      }
    });

    allMatchIndices.value = indices;
    if (indices.length > 0) {
      currentMatchIndex.value = 0;
      scrollToMatch(0);
    } else {
      currentMatchIndex.value = -1;
    }
  },
);

/**
 * 弹窗关闭时清理
 */
function handleDialogClose() {
  logLines.value = [];
  searchKeyword.value = '';
  currentMatchIndex.value = -1;
  allMatchIndices.value = [];
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    width="1200px"
    :close-on-click-modal="false"
    class="log-dialog"
    @closed="handleDialogClose"
  >
    <!-- 自定义标题栏 -->
    <template #header>
      <div class="dialog-header">
        <span class="dialog-title">📄 设备日志 - </span>
        <span class="machine-ip-code">{{ machineIp }}</span>
      </div>
    </template>

    <div class="log-dialog-body">
      <!-- 工具栏 -->
      <div class="log-toolbar">
        <ElButton
          type="primary"
          size="small"
          @click="refreshLogs"
          :loading="loading"
        >
          🔄 刷新
        </ElButton>
        <ElButton size="small" @click="copyLogs">
          📋 复制日志
        </ElButton>
        <div class="log-search">
          <ElInput
            v-model="searchKeyword"
            placeholder="🔍 搜索日志..."
            size="small"
            class="log-search-input"
            @keydown="handleSearchKeydown"
            clearable
          />
          <div class="log-search-nav">
            <ElButton
              size="small"
              :disabled="allMatchIndices.length === 0"
              title="上一个 (Shift+Enter)"
              @click="prevMatch"
            >
              ▲
            </ElButton>
            <ElButton
              size="small"
              :disabled="allMatchIndices.length === 0"
              title="下一个 (Enter)"
              @click="nextMatch"
            >
              ▼
            </ElButton>
          </div>
          <span class="match-count">
            <template v-if="searchKeyword">
              {{
                allMatchIndices.length > 0
                  ? `${currentMatchIndex + 1}/${allMatchIndices.length}`
                  : '0/0'
              }}
            </template>
          </span>
        </div>
        <span class="line-count-info"
          >当前 {{ lineCount }}/{{ MAX_LOG_LINES }} 行</span
        >
      </div>

      <!-- 日志区域 -->
      <div class="log-container" ref="logContainerRef">
        <div v-if="loading && logLines.length === 0" class="log-loading">
          <div class="spinner" />
          <span>加载中...</span>
        </div>
        <template v-else>
          <div
            v-for="(line, index) in logLines"
            :key="index"
            :data-line="index"
            class="log-line"
            :class="[
              getLogLevelClass(line),
              { 'current-match': isCurrentMatch(index) },
            ]"
            v-html="highlightSearch(line)"
          />
        </template>
      </div>
    </div>

    <template #footer>
      <ElButton @click="dialogVisible = false">关闭</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 弹窗样式 */
.log-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  margin-right: 0;
  border-bottom: 1px solid #e8e8e8;
}

.dialog-header {
  display: flex;
  align-items: center;
}

.dialog-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.machine-ip-code {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 4px;
}

.log-dialog :deep(.el-dialog__headerbtn) {
  top: 16px;
  right: 16px;
  width: 30px;
  height: 30px;
}

.log-dialog :deep(.el-dialog__body) {
  padding: 0;
  min-height: 450px;
}

.log-dialog :deep(.el-dialog__footer) {
  padding: 12px 20px;
  border-top: 1px solid #e8e8e8;
}

.log-dialog-body {
  display: flex;
  flex-direction: column;
}

/* 工具栏 */
.log-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}

.log-search {
  display: flex;
  align-items: center;
  gap: 6px;
}

.log-search .el-button {
  margin: 0;
}

.log-search-nav {
  display: flex;
}

.log-search-nav .el-button {
  margin: 0;
  border-radius: 0;
}

.log-search-nav .el-button:first-child {
  border-radius: 4px 0 0 4px;
}

.log-search-nav .el-button:last-child {
  border-radius: 0 4px 4px 0;
  border-left: none;
}

.log-search-input {
  width: 220px;
}

.log-search :deep(.el-input__inner) {
  font-size: 12px;
}

.match-count {
  min-width: 30px;
  font-size: 11px;
  color: #999;
  white-space: nowrap;
}

.line-count-info {
  margin-left: auto;
  font-size: 12px;
  color: #999;
  white-space: nowrap;
}

/* 日志容器 */
.log-container {
  min-height: 400px;
  max-height: 600px;
  padding: 12px 16px;
  margin: 16px 20px;
  overflow-y: auto;
  font-family: Consolas, Monaco, 'Courier New', Menlo, monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #d4d4d4;
  background: #1e1e1e;
  border-radius: 6px;
}

/* 日志行 */
.log-line {
  display: block;
  padding: 1px 4px;
  word-break: break-all;
  white-space: pre;
  border-radius: 2px;
}

.log-line:hover {
  background: rgb(255 255 255 / 5%);
}

/* 日志级别颜色 */
.log-info {
  color: #4fc3f7;
}

.log-warning {
  font-weight: 600;
  color: #ffb74d;
}

.log-error,
.log-critical {
  font-weight: 700;
  color: #ef5350;
  background: rgb(239 83 80 / 10%);
}

.log-debug {
  color: #78909c;
}

/* 加载状态 */
.log-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
}

.log-loading .spinner {
  width: 32px;
  height: 32px;
  margin-bottom: 12px;
  border: 3px solid #333;
  border-top: 3px solid #1890ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 搜索高亮 */
:deep(.search-highlight) {
  padding: 0 2px;
  font-weight: 700;
  color: #000;
  background: #faad14;
  border-radius: 1px;
}

/* 当前匹配的搜索项 */
.log-line.current-match {
  color: #fff !important;
  background: #f5222d !important;
}

.log-line.current-match :deep(.search-highlight) {
  color: #f5222d;
  background: #fff;
}

/* 滚动条样式 */
.log-container::-webkit-scrollbar {
  width: 8px;
}

.log-container::-webkit-scrollbar-track {
  background: #2d2d2d;
  border-radius: 4px;
}

.log-container::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

.log-container::-webkit-scrollbar-thumb:hover {
  background: #777;
}
</style>
