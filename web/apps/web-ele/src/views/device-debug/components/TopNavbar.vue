<script lang="ts" setup>
import type { WebSocketStatus } from '../types';

import { computed } from 'vue';

import { ElButton, ElOption, ElSelect, ElTag } from 'element-plus';

import { isDesktopDevice } from '../utils';

interface Props {
  deviceType: string;
  assetNumber: string;
  deviceSn?: string;
  resolution?: string;
  wsStatus: WebSocketStatus;
  fps: number;
  screenCount?: number; // 新增：屏幕数量
  currentScreen?: number; // 新增：当前选中屏幕
  mouseCoord?: null | { x: number; y: number }; // 新增：鼠标坐标
  navbarFixed?: boolean; // 新增：导航栏是否固定
  deviceModel?: string; // 设备型号（如 iPhone 15 Pro）
  osVersion?: string; // 系统版本（如 iOS 17.2、Windows 11 Pro）
}

interface Emits {
  (e: 'back'): void;
  (e: 'disconnect'): void;
  (e: 'reconnect'): void;
  (e: 'keypress'): void;
  (e: 'input'): void;
  (e: 'unlock'): void;
  (e: 'screenshot'): void;
  (e: 'screenChange', screenIndex: number): void; // 新增：屏幕切换
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isDesktop = computed(() => isDesktopDevice(props.deviceType));

// 屏幕选项
const screenOptions = computed(() => {
  const count = props.screenCount || 1;
  return Array.from({ length: count }, (_, i) => ({
    value: i,
    label: i === 0 ? '主屏幕' : `副屏幕 ${i}`,
  }));
});

// 当前选中的屏幕索引
const selectedScreen = computed({
  get: () => props.currentScreen || 0,
  set: (val) => emit('screenChange', val),
});

const wsStatusDisplay = computed(() => {
  switch (props.wsStatus) {
    case 'connected': {
      return { text: 'WebSocket 已连接', type: 'success' as const };
    }
    case 'connecting': {
      return { text: '连接中', type: 'warning' as const };
    }
    case 'disconnected': {
      return { text: '已断开', type: 'info' as const };
    }
    case 'error': {
      return { text: '连接错误', type: 'danger' as const };
    }
    default: {
      return { text: '未知', type: 'info' as const };
    }
  }
});

const wsConnected = computed(() => props.wsStatus === 'connected');

// 设备型号显示：优先使用 deviceModel，否则使用 assetNumber
const deviceDisplayName = computed(() => {
  if (props.deviceModel) {
    return props.deviceModel;
  }
  return props.assetNumber;
});

// 设备详情显示：系统版本 + 分辨率
const deviceDetailDisplay = computed(() => {
  const parts: string[] = [];
  if (props.osVersion) {
    parts.push(props.osVersion);
  }
  if (props.resolution) {
    parts.push(props.resolution);
  }
  return parts.join(' | ') || props.deviceSn || '未知设备';
});

function handleBack() {
  emit('back');
}

function handleDisconnect() {
  emit('disconnect');
}

function handleReconnect() {
  emit('reconnect');
}

function handleKeyPress() {
  emit('keypress');
}

function handleInput() {
  emit('input');
}

function handleUnlock() {
  emit('unlock');
}

function handleScreenshot() {
  emit('screenshot');
}
</script>

<template>
  <div class="top-navbar" :class="{ 'navbar-fixed': navbarFixed }">
    <!-- 设备信息 -->
    <div class="navbar-left">
      <button class="back-btn" @click="handleBack">← 返回设备列表</button>
      <span class="device-icon">{{ isDesktop ? '💻' : '📱' }}</span>
      <div class="device-info">
        <div class="device-name">{{ deviceDisplayName }}</div>
        <div class="device-meta">{{ deviceDetailDisplay }}</div>
      </div>
      <ElTag type="success" size="small" class="online-tag">在线</ElTag>
      <!-- 坐标显示占位容器 -->
      <div v-if="mouseCoord" class="coord-display">
        <span class="coord-value"
          >({{ mouseCoord.x }}, {{ mouseCoord.y }})</span
        >
      </div>
    </div>

    <!-- 中间操作按钮（桌面端） -->
    <div v-if="isDesktop" class="navbar-center">
      <button class="toolbar-btn light" @click="handleKeyPress">
        ⌨ 按键操作
      </button>
      <button class="toolbar-btn light" @click="handleInput">
        📝 输入文本
      </button>
      <button
        v-if="props.deviceType === 'harmony_pc'"
        class="toolbar-btn light"
        @click="handleUnlock"
      >
        🔓 解锁屏幕
      </button>
      <button class="toolbar-btn light" @click="handleScreenshot">
        📷 截图保存
      </button>
    </div>

    <!-- 连接状态和操作 -->
    <div class="navbar-right">
      <!-- 屏幕选择（仅桌面端且多屏时显示） -->
      <ElSelect
        v-if="isDesktop && screenOptions.length > 1"
        v-model="selectedScreen"
        size="small"
        class="screen-select"
        popper-class="screen-dropdown"
      >
        <ElOption
          v-for="opt in screenOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </ElSelect>
      <div class="ws-status">
        <span v-if="wsConnected" class="ws-dot connected">●</span>
        <span v-else class="ws-dot disconnected">●</span>
        <span class="ws-text">{{ wsStatusDisplay.text }}</span>
      </div>
      <span v-if="fps > 0" class="fps-display">{{ fps }} fps</span>
      <button
        v-if="wsStatus === 'connected'"
        class="disconnect-btn"
        @click="handleDisconnect"
      >
        断开
      </button>
      <ElButton
        v-if="wsStatus === 'disconnected' || wsStatus === 'error'"
        size="small"
        type="primary"
        @click="handleReconnect"
      >
        重连
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.top-navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  min-height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.top-navbar.navbar-fixed {
  position: fixed;
  top: 0;
  right: 0;
  left: 0;
  z-index: 1000;
}

.navbar-left {
  position: relative;
  display: flex;
  gap: 24px;
  align-items: center;
}

.back-btn {
  padding: 8px 16px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #e8e8e8;
}

.device-icon {
  font-size: 24px;
}

.device-info {
  display: flex;
  flex-direction: column;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  color: #111;
}

.device-meta {
  font-size: 12px;
  color: #666;
}

.online-tag {
  color: #166534;
  background: #dcfce7;
  border-color: #dcfce7;
}

.navbar-right {
  display: flex;
  gap: 24px;
  align-items: center;
}

.ws-status {
  display: flex;
  gap: 4px;
  align-items: center;
  font-size: 14px;
  color: #666;
}

.ws-dot.connected {
  color: #22c55e;
}

.ws-dot.disconnected {
  color: #999;
}

.ws-text {
  font-size: 13px;
}

.fps-display {
  padding: 8px 16px;
  font-size: 13px;
  color: #333;
  background: #f5f5f5;
  border-radius: 6px;
}

.screen-select {
  width: 100px;
  font-size: 13px;
}

.screen-select :deep(.el-input__wrapper) {
  min-height: 34px;
  padding: 0 12px;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  box-shadow: none;
}

.screen-select :deep(.el-input__wrapper:hover),
.screen-select :deep(.el-input__wrapper.is-focus) {
  background: #f5f5f5;
  border-color: #1890ff;
  box-shadow: none;
}

.screen-select :deep(.el-input__inner) {
  font-size: 13px;
  color: #333;
}

.screen-select :deep(.el-select__caret) {
  color: #666;
}

.disconnect-btn {
  padding: 8px 20px;
  font-size: 14px;
  color: #b91c1c;
  cursor: pointer;
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  transition: all 0.2s;
}

.disconnect-btn:hover {
  background: #fecaca;
}

.navbar-center {
  display: flex;
  flex: 1;
  gap: 12px;
  align-items: center;
  justify-content: center;
}

.toolbar-btn {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  border-radius: 6px;
  transition: all 0.2s;
}

.toolbar-btn.orange {
  color: #fff;
  background: #f59e0b;
}

.toolbar-btn.orange:hover {
  background: #d97706;
}

.toolbar-btn.gray {
  color: #fff;
  background: #6b7280;
}

.toolbar-btn.gray:hover {
  background: #4b5563;
}

.toolbar-btn.light {
  color: #333;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
}

.toolbar-btn.light:hover {
  background: #e8e8e8;
}

.coord-display {
  position: absolute;
  right: -100px;
  padding: 6px 14px;
  font-size: 12px;
  color: #fff;
  background: rgb(0 0 0 / 80%);
  border-radius: 4px;
}

.coord-value {
  font-weight: 600;
  color: #3b82f6;
}
</style>

<style>
/* 屏幕选择下拉菜单样式（非 scoped，用于 popper-class） */
.screen-dropdown {
  border-radius: 6px !important;
}

.screen-dropdown .el-select-dropdown__item {
  display: flex;
  align-items: center;
  height: 34px;
  padding: 0 16px;
  font-size: 13px;
  line-height: 34px;
  color: #333;
}

.screen-dropdown .el-select-dropdown__item:hover {
  background: #f5f5f5;
}

.screen-dropdown .el-select-dropdown__item.selected {
  font-weight: 500;
  color: #1890ff;
}
</style>
