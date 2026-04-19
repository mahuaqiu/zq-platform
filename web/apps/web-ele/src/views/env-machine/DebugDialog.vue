<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { onMounted, ref, computed } from 'vue';

import {
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
  ElTag,
} from 'element-plus';

import { debugDeviceActionApi } from '#/api/core/env-machine';
import { DEVICE_TYPE_OPTIONS, STATUS_OPTIONS } from './types';
import KeyPressDialog from './modules/KeyPressDialog.vue';

interface Props {
  visible: boolean;
  machine: EnvMachine | null;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 弹窗状态
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

// 设备信息
const deviceInfo = computed(() => {
  if (!props.machine) return null;
  const typeOpt = DEVICE_TYPE_OPTIONS.find(o => o.value === props.machine!.device_type);
  const statusOpt = STATUS_OPTIONS.find(o => o.value === props.machine!.status);
  return {
    type: typeOpt?.label || props.machine.device_type,
    status: statusOpt?.label || props.machine.status,
  };
});

// 截图相关
const screenshotBase64 = ref('');
const screenshotLoading = ref(false);
const screenshotWidth = ref(400);
const screenshotHeight = ref(700);

// 坐标显示
const mouseCoord = ref<{ x: number; y: number } | null>(null);

// 点击指示器
const clickIndicator = ref<{ x: number; y: number; show: boolean }>({ x: 0, y: 0, show: false });

// 拖拽滑动状态
const isDragging = ref(false);
const dragStart = ref<{ x: number; y: number } | null>(null);
const dragEnd = ref<{ x: number; y: number } | null>(null);

// 操作状态
const isOperating = ref(false);
const lastOperationTime = ref(0);
const lastScreenshotTime = ref(0);

// 操作历史
interface OperationRecord {
  type: string;
  params: string;
  status: 'pending' | 'success' | 'failed';
  time: string;
}
const operationHistory = ref<OperationRecord[]>([]);

// 子弹窗
const keyPressDialogVisible = ref(false);

// 文本输入
const textInputValue = ref('');

// 解锁密码
const unlockPassword = ref('');

// 常量
const OPERATION_TIMEOUT = 10000;
const MIN_OPERATION_INTERVAL = 300;
const SCREENSHOT_COOLDOWN = 1000;

// 辅助函数
function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatTime() {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

function formatHistoryDisplay(type: string, params: Record<string, any>): string {
  switch (type) {
    case 'screenshot':
      return ''; // 截图操作不显示在历史中
    case 'click':
      return `点击(${params.x}, ${params.y})`;
    case 'swipe':
      return '滑动';
    case 'input':
      const text = params.text || '';
      return `输入"${text.length > 10 ? text.slice(0, 10) + '...' : text}"`;
    case 'press':
      return `${params.key}`;
    case 'unlock_screen':
      return `解锁屏幕`;
    default:
      return type;
  }
}

function addHistory(type: string, params: string, status: 'pending' | 'success' | 'failed') {
  operationHistory.value.unshift({
    type,
    params,
    status,
    time: formatTime(),
  });
  // 限制历史记录数量
  if (operationHistory.value.length > 20) {
    operationHistory.value = operationHistory.value.slice(0, 20);
  }
}

function updateHistoryStatus(status: 'success' | 'failed') {
  const record = operationHistory.value[0];
  if (record) {
    record.status = status;
  }
}

// 执行操作（带超时和间隔控制）
async function executeOperation(
  actionType: string,
  params: Record<string, any>,
  skipRefresh = false,
  isAuto = false,  // 自动操作不记录历史
): Promise<boolean> {
  if (!props.machine) return false;

  // 检查最小间隔
  const now = Date.now();
  const elapsed = now - lastOperationTime.value;
  if (elapsed < MIN_OPERATION_INTERVAL) {
    await sleep(MIN_OPERATION_INTERVAL - elapsed);
  }

  // 设置操作锁
  isOperating.value = true;
  lastOperationTime.value = Date.now();

  // 记录操作开始（自动操作和截图不记录）
  if (!isAuto && actionType !== 'screenshot') {
    const displayText = formatHistoryDisplay(actionType, params);
    addHistory(actionType, displayText, 'pending');
  }

  try {
    // 超时控制
    const timeoutPromise = new Promise<null>((_, reject) =>
      setTimeout(() => reject(new Error('操作超时')), OPERATION_TIMEOUT),
    );

    const result = await Promise.race([
      debugDeviceActionApi(props.machine.id, { action_type: actionType as any, params }),
      timeoutPromise,
    ]);

    if (result && result.success) {
      // 更新历史记录状态（自动操作不更新）
      if (!isAuto) {
        updateHistoryStatus('success');
      }

      // 处理截图结果
      if (actionType === 'screenshot' && result.result?.screenshot_base64) {
        screenshotBase64.value = result.result.screenshot_base64;
        lastScreenshotTime.value = Date.now();

        // 解析图片尺寸
        const img = new Image();
        img.onload = () => {
          screenshotWidth.value = img.width;
          screenshotHeight.value = img.height;
        };
        img.src = `data:image/png;base64,${result.result!.screenshot_base64}`;
      }

      // 操作成功后自动刷新截图（除了截图操作本身）
      if (!skipRefresh && actionType !== 'screenshot') {
        await sleep(1000);  // 等待 1 秒后再截图
        await refreshScreenshot(true);
      }

      return true;
    } else {
      const errorMsg = result?.result?.error || '操作失败';
      if (!isAuto) {
        updateHistoryStatus('failed');
      }
      ElMessage.error(errorMsg);
      return false;
    }
  } catch (error: any) {
    if (!isAuto) {
      updateHistoryStatus('failed');
    }
    const errorMsg = error.message || '操作失败';
    ElMessage.error(errorMsg);
    return false;
  } finally {
    isOperating.value = false;
  }
}

// 刷新截图
async function refreshScreenshot(auto = false) {
  if (!props.machine) return;

  // 检查冷却时间
  const now = Date.now();
  if (now - lastScreenshotTime.value < SCREENSHOT_COOLDOWN) {
    if (!auto) {
      ElMessage.warning('截图已刷新，请稍后再刷新');
    }
    return;
  }

  screenshotLoading.value = true;
  await executeOperation('screenshot', {}, true, auto);
  screenshotLoading.value = false;
}

// 获取图片上的坐标
function getImageCoords(event: MouseEvent): { x: number; y: number } {
  const img = event.currentTarget as HTMLImageElement;
  const rect = img.getBoundingClientRect();
  const x = Math.round((event.clientX - rect.left) * (screenshotWidth.value / rect.width));
  const y = Math.round((event.clientY - rect.top) * (screenshotHeight.value / rect.height));
  return { x, y };
}

// 拖拽开始（按下鼠标）
function handleDragStart(event: MouseEvent) {
  if (isOperating.value || !screenshotBase64.value) return;
  event.preventDefault(); // 阻止默认行为

  isDragging.value = true;
  dragStart.value = getImageCoords(event);
  dragEnd.value = null;
}

// 拖拽移动
function handleDragMove(event: MouseEvent) {
  if (isDragging.value) {
    dragEnd.value = getImageCoords(event);
    mouseCoord.value = dragEnd.value; // 拖拽时显示终点坐标
  } else {
    // 非拖拽时显示鼠标位置坐标
    handleMouseMove(event);
  }
}

// 拖拽结束（松开鼠标）
async function handleDragEnd(event: MouseEvent) {
  if (!isDragging.value || !dragStart.value) return;

  isDragging.value = false;
  const endCoord = getImageCoords(event);

  // 计算滑动距离，如果距离太短则视为点击
  const dx = Math.abs(endCoord.x - dragStart.value.x);
  const dy = Math.abs(endCoord.y - dragStart.value.y);

  if (dx < 20 && dy < 20) {
    // 距离太短，执行点击
    clickIndicator.value = { x: dragStart.value.x, y: dragStart.value.y, show: true };
    setTimeout(() => {
      clickIndicator.value.show = false;
    }, 500);
    await executeOperation('click', { x: dragStart.value.x, y: dragStart.value.y });
  } else {
    // 执行滑动
    await executeOperation('swipe', {
      from_x: dragStart.value.x,
      from_y: dragStart.value.y,
      to_x: endCoord.x,
      to_y: endCoord.y,
      duration: 500,
    });
  }

  dragStart.value = null;
  dragEnd.value = null;
}

// 鼠标移动显示坐标
function handleMouseMove(event: MouseEvent) {
  if (!screenshotBase64.value) return;
  const img = event.currentTarget as HTMLImageElement;
  const rect = img.getBoundingClientRect();
  const x = Math.round((event.clientX - rect.left) * (screenshotWidth.value / rect.width));
  const y = Math.round((event.clientY - rect.top) * (screenshotHeight.value / rect.height));
  mouseCoord.value = { x, y };
}

function handleMouseLeave() {
  mouseCoord.value = null;
  // 鼠标离开时取消拖拽
  if (isDragging.value) {
    isDragging.value = false;
    dragStart.value = null;
    dragEnd.value = null;
  }
}

// 文本输入
async function handleTextInput() {
  if (!textInputValue.value.trim()) {
    ElMessage.warning('请输入文本内容');
    return;
  }
  await executeOperation('input', { x: 0, y: 0, text: textInputValue.value });
  textInputValue.value = '';
}

// 按键操作
function handleOpenKeyPressDialog() {
  keyPressDialogVisible.value = true;
}

async function handleKeyPress(key: string) {
  await executeOperation('press', { key });
}

// 解锁屏幕
async function handleUnlockScreen() {
  if (!unlockPassword.value.trim()) {
    ElMessage.warning('请输入解锁密码');
    return;
  }
  await executeOperation('unlock_screen', { value: unlockPassword.value });
  unlockPassword.value = '';
}

// 弹窗打开时获取截图
onMounted(() => {
  if (props.visible && props.machine) {
    refreshScreenshot();
  }
});

// 监听弹窗打开
function handleDialogOpen() {
  if (props.machine) {
    refreshScreenshot();
  }
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    :title="`设备调试 - ${machine?.asset_number || machine?.ip || machine?.id}`"
    width="900px"
    :close-on-click-modal="false"
    @open="handleDialogOpen"
  >
    <!-- 设备信息 -->
    <div class="debug-header">
      <ElTag v-if="deviceInfo" type="success">{{ deviceInfo.status }}</ElTag>
      <ElTag v-if="deviceInfo" type="info">{{ deviceInfo.type }}</ElTag>
      <span class="device-id">设备SN: {{ machine?.device_sn || machine?.id }}</span>
    </div>

    <!-- 三栏布局 -->
    <div class="debug-content">
      <!-- 左侧：操作历史 -->
      <div class="debug-history">
        <div class="history-title">📋 操作历史</div>
        <div class="history-list">
          <div
            v-for="(record, index) in operationHistory"
            :key="index"
            class="history-item"
          >
            <span class="history-status">
              <template v-if="record.status === 'pending'">⏳</template>
              <template v-else-if="record.status === 'success'">
                <span class="status-success">✓</span>
              </template>
              <template v-else>
                <span class="status-failed">✗</span>
              </template>
            </span>
            <span class="history-params">{{ record.params }}</span>
            <span class="history-time">{{ record.time }}</span>
          </div>
          <div v-if="operationHistory.length === 0" class="history-empty">
            暂无操作记录
          </div>
        </div>
      </div>

      <!-- 中间：截图预览 -->
      <div class="debug-screenshot" :class="{ operating: isOperating }">
        <!-- 坐标显示 -->
        <div v-if="mouseCoord" class="coord-display">
          X: {{ mouseCoord.x }}, Y: {{ mouseCoord.y }}
        </div>

        <!-- 截图区域 -->
        <div class="screenshot-wrapper">
          <img
            v-if="screenshotBase64"
            :src="`data:image/png;base64,${screenshotBase64}`"
            class="screenshot-img"
            draggable="false"
            @mousedown="handleDragStart"
            @mousemove="handleDragMove"
            @mouseup="handleDragEnd"
            @mouseleave="handleMouseLeave"
          />
          <div v-else class="screenshot-placeholder">
            <span v-if="screenshotLoading">加载中...</span>
            <span v-else>暂无截图</span>
          </div>

          <!-- 点击指示器 -->
          <div
            v-if="clickIndicator.show"
            class="click-indicator"
            :style="{
              left: `${(clickIndicator.x / screenshotWidth) * 100}%`,
              top: `${(clickIndicator.y / screenshotHeight) * 100}%`,
            }"
          />

          <!-- 拖拽轨迹指示器 -->
          <div
            v-if="isDragging && dragStart && dragEnd"
            class="drag-track"
          >
            <div
              class="drag-point drag-point-start"
              :style="{
                left: `${(dragStart.x / screenshotWidth) * 100}%`,
                top: `${(dragStart.y / screenshotHeight) * 100}%`,
              }"
            />
            <div
              class="drag-line-visual"
              :style="{
                left: `${(dragStart.x / screenshotWidth) * 100}%`,
                top: `${(dragStart.y / screenshotHeight) * 100}%`,
                width: `${Math.sqrt(
                  Math.pow((dragEnd.x - dragStart.x) / screenshotWidth * 100, 2) +
                  Math.pow((dragEnd.y - dragStart.y) / screenshotHeight * 100, 2)
                )}%`,
                transform: `rotate(${Math.atan2(
                  (dragEnd.y - dragStart.y) / screenshotHeight,
                  (dragEnd.x - dragStart.x) / screenshotWidth
                ) * 180 / Math.PI}deg)`,
              }"
            />
            <div
              class="drag-point drag-point-end"
              :style="{
                left: `${(dragEnd.x / screenshotWidth) * 100}%`,
                top: `${(dragEnd.y / screenshotHeight) * 100}%`,
              }"
            />
          </div>
        </div>
      </div>

      <!-- 右侧：工具栏 -->
      <div class="debug-toolbar">
        <!-- 刷新截图 -->
        <ElButton
          type="primary"
          class="toolbar-btn"
          :disabled="isOperating"
          :loading="screenshotLoading"
          @click="refreshScreenshot()"
        >
          🔄 刷新截图
        </ElButton>

        <!-- 文本输入卡片 -->
        <div class="toolbar-card">
          <div class="card-title">⌨️ 文本输入</div>
          <ElInput
            v-model="textInputValue"
            placeholder="输入文本内容..."
            :disabled="isOperating"
            size="small"
          />
          <ElButton
            type="primary"
            size="small"
            class="send-btn"
            :disabled="isOperating || !textInputValue.trim()"
            @click="handleTextInput"
          >
            发送
          </ElButton>
        </div>

        <!-- 按键操作 -->
        <ElButton class="outline-btn toolbar-btn" :disabled="isOperating" @click="handleOpenKeyPressDialog">
          🎹 按键操作
        </ElButton>

        <!-- 解锁屏幕卡片 -->
        <div class="toolbar-card">
          <div class="card-title">🔓 解锁屏幕</div>
          <ElInput
            v-model="unlockPassword"
            placeholder="输入解锁密码..."
            :disabled="isOperating"
            size="small"
          />
          <ElButton
            type="primary"
            size="small"
            class="send-btn"
            :disabled="isOperating || !unlockPassword.trim()"
            @click="handleUnlockScreen"
          >
            解锁
          </ElButton>
        </div>

        <!-- 操作提示 -->
        <div class="tip-section">
          💡 点击截图发送点击指令<br>
          拖拽（按住拖动）执行滑动操作<br>
          鼠标悬停显示实时坐标
        </div>
      </div>
    </div>

    <!-- 子弹窗 -->
    <KeyPressDialog
      v-model:visible="keyPressDialogVisible"
      :disabled="isOperating"
      :device-type="machine?.device_type"
      @press="handleKeyPress"
    />
  </ElDialog>
</template>

<style scoped>
.debug-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.device-id {
  font-size: 12px;
  color: #666;
}

.debug-content {
  display: flex;
  gap: 16px;
  height: 500px;
}

/* 左侧操作历史 */
.debug-history {
  width: 240px;
  background: #f5f5f5;
  border-radius: 8px;
  overflow: hidden;
}

.history-title {
  padding: 12px;
  font-size: 14px;
  font-weight: 500;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}

.history-list {
  padding: 8px;
  height: calc(100% - 40px);
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  font-size: 12px;
  border-radius: 4px;
  margin-bottom: 4px;
  background: #fff;
  white-space: nowrap;
}

.history-status {
  flex-shrink: 0;
}

.status-success {
  color: #22c55e;
}

.status-failed {
  color: #ef4444;
}

.history-type {
  flex-shrink: 0;
  font-weight: 500;
  color: #333;
}

.history-params {
  flex-shrink: 0;
  color: #666;
}

.history-time {
  flex-shrink: 0;
  margin-left: auto;
  color: #999;
}

.history-empty {
  text-align: center;
  color: #999;
  padding: 20px;
}

/* 中间截图 */
.debug-screenshot {
  flex: 1;
  background: #1a1a1a;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.debug-screenshot.operating {
  cursor: wait;
}

.coord-display {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 4px;
}

.screenshot-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.screenshot-img {
  max-width: 100%;
  max-height: 100%;
  cursor: crosshair;
}

.screenshot-placeholder {
  color: #666;
  font-size: 14px;
}

.click-indicator {
  position: absolute;
  width: 32px;
  height: 32px;
  background: rgba(24, 144, 255, 0.8);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  animation: clickPulse 0.5s ease-out;
}

@keyframes clickPulse {
  0% {
    transform: translate(-50%, -50%) scale(0);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0;
  }
}

/* 拖拽轨迹 */
.drag-track {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.drag-point {
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  border: 3px solid #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
}

.drag-point-start {
  background: #22c55e;
}

.drag-point-end {
  background: #ef4444;
}

.drag-line-visual {
  position: absolute;
  height: 4px;
  background: linear-gradient(90deg, #22c55e, #ef4444);
  transform-origin: left center;
  border-radius: 2px;
  pointer-events: none;
}

/* 右侧工具栏 */
.debug-toolbar {
  width: 200px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 工具栏按钮 */
.toolbar-btn {
  width: 100%;
  padding: 12px;
  font-size: 14px;
}

.toolbar-btn :deep(.el-button__content) {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 工具栏卡片 */
.toolbar-card {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  padding: 12px;
}

.card-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

/* 发送按钮 */
.send-btn {
  width: 100%;
  margin-top: 6px;
}

/* 白色背景+边框按钮 */
.outline-btn {
  background: #fff;
  border: 1px solid #e5e5e5;
  color: #333;
}

.outline-btn:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #d5d5d5;
}

/* 操作提示 */
.tip-section {
  background: #f0f7ff;
  border: 1px solid #3b82f6;
  border-radius: 6px;
  padding: 10px;
  font-size: 12px;
  color: #333;
  line-height: 1.5;
}
</style>