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
import SwipeDialog from './modules/SwipeDialog.vue';

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
const swipeDialogVisible = ref(false);

// 文本输入
const textInputValue = ref('');

// 滑动弹窗引用
const swipeDialogRef = ref<{ setFromPoint: (x: number, y: number) => void; setToPoint: (x: number, y: number) => void } | null>(null);

// 选择模式（用于在截图上选择起点/终点）
const selectMode = ref<'none' | 'from' | 'to'>('none');

// 常量
const OPERATION_TIMEOUT = 10000;
const MIN_OPERATION_INTERVAL = 300;
const SCREENSHOT_COOLDOWN = 2000;

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
      return '刷新截图';
    case 'click':
      return `点击(${params.x}, ${params.y})`;
    case 'swipe':
      return '滑动';
    case 'input':
      const text = params.text || '';
      return `输入"${text.length > 10 ? text.slice(0, 10) + '...' : text}"`;
    case 'press':
      return `${params.key}键`;
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

  // 记录操作开始（自动操作不记录）
  if (!isAuto) {
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

// 点击截图
async function handleScreenshotClick(event: MouseEvent) {
  if (isOperating.value || !screenshotBase64.value) return;
  if (selectMode.value !== 'none') {
    // 选择模式，用于设置滑动起点/终点
    handleSelectPoint(event);
    return;
  }

  const img = event.currentTarget as HTMLImageElement;
  const rect = img.getBoundingClientRect();
  const x = Math.round((event.clientX - rect.left) * (screenshotWidth.value / rect.width));
  const y = Math.round((event.clientY - rect.top) * (screenshotHeight.value / rect.height));

  // 显示点击指示器
  clickIndicator.value = { x, y, show: true };
  setTimeout(() => {
    clickIndicator.value.show = false;
  }, 500);

  await executeOperation('click', { x, y });
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
}

// 选择起点/终点
function handleSelectPoint(event: MouseEvent) {
  const img = event.currentTarget as HTMLImageElement;
  const rect = img.getBoundingClientRect();
  const x = Math.round((event.clientX - rect.left) * (screenshotWidth.value / rect.width));
  const y = Math.round((event.clientY - rect.top) * (screenshotHeight.value / rect.height));

  if (selectMode.value === 'from') {
    swipeDialogRef.value?.setFromPoint(x, y);
    selectMode.value = 'to';
    ElMessage.info('已设置起点，请点击选择终点');
  } else if (selectMode.value === 'to') {
    swipeDialogRef.value?.setToPoint(x, y);
    selectMode.value = 'none';
    ElMessage.success('起点和终点已设置');
  }
}

// 快捷滑动
async function handleQuickSwipe(direction: 'up' | 'down' | 'left' | 'right') {
  const w = screenshotWidth.value;
  const h = screenshotHeight.value;

  const presets = {
    up: { from_x: w / 2, from_y: h * 0.8, to_x: w / 2, to_y: h * 0.2 },
    down: { from_x: w / 2, from_y: h * 0.2, to_x: w / 2, to_y: h * 0.8 },
    left: { from_x: w * 0.8, from_y: h / 2, to_x: w * 0.2, to_y: h / 2 },
    right: { from_x: w * 0.2, from_y: h / 2, to_x: w * 0.8, to_y: h / 2 },
  };

  await executeOperation('swipe', { ...presets[direction], duration: 500 });
}

// 自定义滑动
function handleOpenSwipeDialog() {
  swipeDialogVisible.value = true;
}

async function handleSwipe(params: { from_x: number; from_y: number; to_x: number; to_y: number; duration: number }) {
  await executeOperation('swipe', params);
}

// 开始在截图上选择起点
function startSelectFrom() {
  selectMode.value = 'from';
  ElMessage.info('请在截图上点击选择起点');
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
      <span class="device-id">设备ID: {{ machine?.id }}</span>
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
              <template v-else-if="record.status === 'success'">✓</template>
              <template v-else>✗</template>
            </span>
            <span class="history-type">{{ record.type }}</span>
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
            @click="handleScreenshotClick"
            @mousemove="handleMouseMove"
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

        <!-- 滑动操作卡片 -->
        <div class="toolbar-card">
          <div class="card-title">👆 滑动操作</div>
          <div class="swipe-buttons">
            <ElButton type="primary" size="small" :disabled="isOperating" @click="handleQuickSwipe('up')">⬆️ 上滑</ElButton>
            <ElButton type="primary" size="small" :disabled="isOperating" @click="handleQuickSwipe('down')">⬇️ 下滑</ElButton>
          </div>
          <div class="swipe-buttons">
            <ElButton type="primary" size="small" :disabled="isOperating" @click="handleQuickSwipe('left')">⬅️ 左滑</ElButton>
            <ElButton type="primary" size="small" :disabled="isOperating" @click="handleQuickSwipe('right')">➡️ 右滑</ElButton>
          </div>
        </div>

        <!-- 自定义滑动 -->
        <ElButton class="outline-btn toolbar-btn" :disabled="isOperating" @click="handleOpenSwipeDialog">
          🎯 自定义滑动
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

        <!-- 操作提示 -->
        <div class="tip-section">
          💡 点击截图发送点击指令<br>
          鼠标悬停显示实时坐标
        </div>

        <!-- 选择起点按钮（仅在选择模式时显示） -->
        <ElButton
          v-if="selectMode !== 'none'"
          size="small"
          type="warning"
          class="toolbar-btn"
          @click="startSelectFrom"
        >
          选择起点
        </ElButton>
      </div>
    </div>

    <!-- 子弹窗 -->
    <KeyPressDialog
      v-model:visible="keyPressDialogVisible"
      :disabled="isOperating"
      @press="handleKeyPress"
    />
    <SwipeDialog
      ref="swipeDialogRef"
      v-model:visible="swipeDialogVisible"
      :screenshot-width="screenshotWidth"
      :screenshot-height="screenshotHeight"
      :disabled="isOperating"
      @swipe="handleSwipe"
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

/* 滑动按钮 */
.swipe-buttons {
  display: flex;
  gap: 4px;
}

.swipe-buttons .el-button {
  flex: 1;
  padding: 10px;
  font-size: 14px;
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