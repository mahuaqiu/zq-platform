<script lang="ts" setup>
import { computed, nextTick, ref, watch } from 'vue';

import {
  ElButton,
  ElDialog,
  ElMessage,
  ElInput,
  ElTabs,
  ElTabPane,
  ElInputNumber,
  ElDatePicker,
  ElTag,
  ElTooltip,
} from 'element-plus';

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
const error = ref<string>('');

// 查询模式
const queryMode = ref<'lines' | 'request_id' | 'time_range'>('lines');

// lines 模式参数
const linesCount = ref(400);

// request_id 模式参数
const requestIdInput = ref('');

// time_range 模式参数
const timeRangeStart = ref<Date | null>(null);
const timeRangeEnd = ref<Date | null>(null);

// 响应头信息
const logCount = ref(0);
const filesScanned = ref(0);

// 搜索相关
const searchKeyword = ref('');
const currentMatchIndex = ref(-1);
const allMatchIndices = ref<number[]>([]);

// 日志容器 ref
const logContainerRef = ref<HTMLElement | null>(null);

const MAX_LOG_LINES = 2000;

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
 * 设置快捷时间范围
 */
function setQuickTimeRange(minutes: number) {
  const now = new Date();
  const start = new Date(now.getTime() - minutes * 60 * 1000);
  timeRangeStart.value = start;
  timeRangeEnd.value = now;
}

/**
 * 格式化时间为 ISO 8601（本地时间）
 */
function formatIsoTime(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
}

/**
 * 执行日志查询
 */
async function executeQuery() {
  if (!props.machineId) return;

  // 验证参数
  if (queryMode.value === 'time_range') {
    if (!timeRangeStart.value || !timeRangeEnd.value) {
      ElMessage.warning('请选择时间范围');
      return;
    }
    const diffMs = timeRangeEnd.value.getTime() - timeRangeStart.value.getTime();
    const diffMin = diffMs / (1000 * 60);
    if (diffMin > 5) {
      ElMessage.warning('时间区间不能超过 5 分钟');
      return;
    }
    if (diffMs <= 0) {
      ElMessage.warning('结束时间必须大于开始时间');
      return;
    }
  }

  if (queryMode.value === 'request_id' && !requestIdInput.value.trim()) {
    ElMessage.warning('请输入 Request ID');
    return;
  }

  loading.value = true;
  error.value = '';

  try {
    let params: Record<string, any> = {};

    switch (queryMode.value) {
      case 'lines':
        params.lines = linesCount.value;
        break;
      case 'request_id':
        params.request_id = requestIdInput.value.trim();
        break;
      case 'time_range':
        params.start_time = formatIsoTime(timeRangeStart.value!);
        params.end_time = formatIsoTime(timeRangeEnd.value!);
        break;
    }

    const res = await getMachineLogsApi(props.machineId, params);

    // 从响应头获取统计信息
    logCount.value = res.log_count || 0;
    filesScanned.value = res.files_scanned || 1;

    const text = res.content || '';
    const newLines = text.split('\n').filter((line) => line.trim() !== '');

    logLines.value = newLines;
    currentMatchIndex.value = -1;
    allMatchIndices.value = [];

    await nextTick();

    if (newLines.length > 0) {
      scrollToBottom();
    }

    if (newLines.length === 0) {
      ElMessage.info('查询结果为空');
    }
  } catch (err: any) {
    console.error('获取日志失败:', err);
    const errorMsg = err?.response?.data?.detail || err?.message || '获取日志失败';
    error.value = errorMsg;
    ElMessage.error(errorMsg);
  } finally {
    loading.value = false;
  }
}

/**
 * 复制日志到剪贴板
 */
async function copyLogs() {
  if (logLines.value.length === 0) {
    ElMessage.warning('暂无日志可复制');
    return;
  }
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
      // 重置状态
      logLines.value = [];
      error.value = '';
      searchKeyword.value = '';
      currentMatchIndex.value = -1;
      allMatchIndices.value = [];
      queryMode.value = 'lines';
      linesCount.value = 400;
      requestIdInput.value = '';
      timeRangeStart.value = null;
      timeRangeEnd.value = null;
      logCount.value = 0;
      filesScanned.value = 0;

      // 默认加载
      executeQuery();
    }
  },
);

/**
 * 监听搜索关键词变化
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
  error.value = '';
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
    align-center
    class="log-dialog-v2"
    @closed="handleDialogClose"
  >
    <!-- 自定义标题栏 -->
    <template #header>
      <div class="dialog-header">
        <div class="header-left">
          <span class="dialog-title">📄 设备日志 - </span>
          <span class="machine-ip-code">{{ machineIp }}</span>
        </div>
        <div class="header-stats">
          <ElTag size="small" type="info">
            行数: {{ logCount }}
          </ElTag>
          <ElTag size="small" type="info">
            扫描文件: {{ filesScanned }}
          </ElTag>
        </div>
      </div>
    </template>

    <div class="log-dialog-body">
      <!-- 查询控制面板 -->
      <div class="query-panel">
        <ElTabs v-model="queryMode" class="query-tabs">
          <!-- Lines 模式 -->
          <ElTabPane name="lines">
            <template #label>
              <span>Lines 行数</span>
            </template>
            <div class="query-content">
              <div class="query-row">
                <label class="query-label">返回行数</label>
                <ElInputNumber
                  v-model="linesCount"
                  :min="1"
                  :max="2000"
                  :step="100"
                  size="small"
                  controls-position="right"
                />
                <span class="query-hint">范围 1-2000，默认 400</span>
              </div>
            </div>
          </ElTabPane>

          <!-- Request ID 模式 -->
          <ElTabPane name="request_id">
            <template #label>
              <span>Request ID</span>
            </template>
            <div class="query-content">
              <div class="query-row">
                <label class="query-label">请求 ID</label>
                <ElInput
                  v-model="requestIdInput"
                  placeholder="输入 request_id 进行 grep 搜索"
                  size="small"
                  style="width: 300px"
                  clearable
                />
              </div>
            </div>
          </ElTabPane>

          <!-- Time Range 模式 -->
          <ElTabPane name="time_range">
            <template #label>
              <span>Time Range</span>
            </template>
            <div class="query-content">
              <div class="query-row">
                <label class="query-label">开始时间</label>
                <ElDatePicker
                  v-model="timeRangeStart"
                  type="datetime"
                  placeholder="选择开始时间"
                  size="small"
                  format="YYYY-MM-DD HH:mm:ss"
                  style="width: 180px"
                />
                <label class="query-label">结束时间</label>
                <ElDatePicker
                  v-model="timeRangeEnd"
                  type="datetime"
                  placeholder="选择结束时间"
                  size="small"
                  format="YYYY-MM-DD HH:mm:ss"
                  style="width: 180px"
                />
                <ElTooltip content="时间区间最多 5 分钟" placement="top">
                  <ElTag size="small" type="warning">≤ 5min</ElTag>
                </ElTooltip>
              </div>
              <div class="quick-time-row">
                <span class="quick-label">快捷选择:</span>
                <ElButton size="small" text type="primary" @click="setQuickTimeRange(1)">
                  最近1分钟
                </ElButton>
                <ElButton size="small" text type="primary" @click="setQuickTimeRange(3)">
                  最近3分钟
                </ElButton>
                <ElButton size="small" text type="primary" @click="setQuickTimeRange(5)">
                  最近5分钟
                </ElButton>
              </div>
            </div>
          </ElTabPane>
        </ElTabs>

        <!-- 查询按钮 -->
        <ElButton
          type="primary"
          size="small"
          :loading="loading"
          @click="executeQuery"
          style="margin-bottom: 4px"
        >
          查询
        </ElButton>
      </div>

      <!-- 工具栏 -->
      <div class="log-toolbar">
        <ElButton size="small" @click="copyLogs" :disabled="logLines.length === 0">
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
          <template v-if="searchKeyword">
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
            <span class="match-count">
              {{ allMatchIndices.length > 0 ? `${currentMatchIndex + 1}/${allMatchIndices.length}` : '0/0' }}
            </span>
          </template>
        </div>
        <span class="line-count-info">当前 {{ logLines.length }} 行</span>
      </div>

      <!-- 日志区域 -->
      <div class="log-container" ref="logContainerRef">
        <div v-if="loading && logLines.length === 0" class="log-loading">
          <div class="spinner" />
          <span>加载中...</span>
        </div>

        <div v-else-if="error" class="log-error-display">
          <span class="error-icon">⚠️</span>
          <span>{{ error }}</span>
        </div>

        <div v-else-if="logLines.length === 0" class="log-empty">
          <span>查询结果为空</span>
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
              { 'long-line': line.length > 300 },
            ]"
            v-html="highlightSearch(line)"
          />
        </template>
      </div>

      <!-- 查询模式提示 -->
      <div class="mode-hint">
        <span v-if="queryMode === 'lines'">
          ⓘ Lines 模式: 返回最后 {{ linesCount }} 行日志
        </span>
        <span v-else-if="queryMode === 'request_id'">
          ⓘ Request ID 模式: grep 搜索所有日志文件中匹配的日志
        </span>
        <span v-else-if="queryMode === 'time_range'">
          ⓘ Time Range 模式: 按时间区间过滤，最多 5 分钟
        </span>
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

/* 弹窗样式 - 保持原色调 */
.log-dialog-v2 :deep(.el-dialog__header) {
  padding: 16px 20px;
  margin-right: 0;
  border-bottom: 1px solid #e8e8e8;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
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

.header-stats {
  display: flex;
  gap: 8px;
}

.log-dialog-v2 :deep(.el-dialog__headerbtn) {
  top: 16px;
  right: 16px;
  width: 30px;
  height: 30px;
}

.log-dialog-v2 :deep(.el-dialog__body) {
  padding: 0;
  min-height: 350px;
  max-height: 70vh;
  overflow: hidden;
}

.log-dialog-v2 :deep(.el-dialog__footer) {
  padding: 12px 20px;
  border-top: 1px solid #e8e8e8;
}

.log-dialog-body {
  display: flex;
  flex-direction: column;
}

/* ═══════════════════════════════════════════════════════════
   查询面板
   ═══════════════════════════════════════════════════════════ */

.query-panel {
  display: flex;
  align-items: flex-end;
  padding: 12px 20px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  gap: 16px;
}

.query-tabs {
  flex: 1;
}

.query-tabs :deep(.el-tabs__header) {
  margin-bottom: 10px;
}

.query-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0;
}

.query-tabs :deep(.el-tabs__item) {
  padding: 8px 16px;
  font-size: 13px;
  color: #666;
}

.query-tabs :deep(.el-tabs__item:hover) {
  color: #409eff;
}

.query-tabs :deep(.el-tabs__item.is-active) {
  color: #409eff;
  font-weight: 500;
}

.query-content {
  padding: 8px 0;
}

.query-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.query-label {
  font-size: 13px;
  color: #666;
}

.query-hint {
  font-size: 12px;
  color: #999;
}

.quick-time-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.quick-label {
  font-size: 12px;
  color: #999;
}

/* ═══════════════════════════════════════════════════════════
   工具栏
   ═══════════════════════════════════════════════════════════ */

.log-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.log-search {
  display: flex;
  align-items: center;
  gap: 6px;
}

.log-search-input {
  width: 220px;
}

.log-search :deep(.el-input__inner) {
  font-size: 12px;
}

.match-count {
  min-width: 40px;
  font-size: 12px;
  color: #999;
}

.line-count-info {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}

/* ═══════════════════════════════════════════════════════════
   日志容器
   ═══════════════════════════════════════════════════════════ */

.log-container {
  min-height: 300px;
  max-height: 400px;
  padding: 12px 16px;
  margin: 12px 20px;
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
  white-space: pre;
  border-radius: 2px;
}

.log-line.long-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.05);
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
  background: rgba(239, 83, 80, 0.1);
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
  height: 150px;
  color: #999;
}

.log-loading .spinner {
  width: 28px;
  height: 28px;
  margin-bottom: 10px;
  border: 3px solid #333;
  border-top: 3px solid #1890ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 错误显示 */
.log-error-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 120px;
  color: #ff4d4f;
}

.error-icon {
  font-size: 16px;
}

/* 空结果 */
.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  color: #999;
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

/* 模式提示 */
.mode-hint {
  padding: 8px 20px;
  background: #f5f5f5;
  font-size: 12px;
  color: #666;
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