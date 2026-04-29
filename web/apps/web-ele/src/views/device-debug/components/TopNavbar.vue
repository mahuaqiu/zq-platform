<script lang="ts" setup>
import type { WebSocketStatus } from '../types';
import { isDesktopDevice } from '../utils';

import { computed } from 'vue';

import { ElButton, ElTag, ElSelect, ElOption } from 'element-plus';

interface Props {
  deviceType: string;
  assetNumber: string;
  deviceSn?: string;
  resolution?: string;
  wsStatus: WebSocketStatus;
  fps: number;
  screenCount?: number;  // 新增：屏幕数量
  currentScreen?: number; // 新增：当前选中屏幕
  mouseCoord?: { x: number; y: number } | null; // 新增：鼠标坐标
  navbarFixed?: boolean; // 新增：导航栏是否固定
  deviceModel?: string; // 设备型号（如 iPhone 15 Pro）
  osVersion?: string;   // 系统版本（如 iOS 17.2、Windows 11 Pro）
}

interface Emits {
  (e: 'back'): void;
  (e: 'disconnect'): void;
  (e: 'reconnect'): void;
  (e: 'keypress'): void;
  (e: 'input'): void;
  (e: 'install'): void;
  (e: 'screenshot'): void;
  (e: 'screenChange', screenIndex: number): void;  // 新增：屏幕切换
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isDesktop = computed(() => isDesktopDevice(props.deviceType));

// 屏幕选项
const screenOptions = computed(() => {
  const count = props.screenCount || 1;
  return Array.from({ length: count }, (_, i) => ({
    value: i,
    label: i === 0 ? '主屏幕' : `副屏幕 ${i}`
  }));
});

// 当前选中的屏幕索引
const selectedScreen = computed({
  get: () => props.currentScreen || 0,
  set: (val) => emit('screenChange', val)
});

const wsStatusDisplay = computed(() => {
  switch (props.wsStatus) {
    case 'connecting':
      return { text: '连接中', type: 'warning' as const };
    case 'connected':
      return { text: 'WebSocket 已连接', type: 'success' as const };
    case 'disconnected':
      return { text: '已断开', type: 'info' as const };
    case 'error':
      return { text: '连接错误', type: 'danger' as const };
    default:
      return { text: '未知', type: 'info' as const };
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

function handleInstall() {
  emit('install');
}

function handleScreenshot() {
  emit('screenshot');
}
</script>

<template>
  <div class="top-navbar" :class="{ 'navbar-fixed': navbarFixed }">
    <!-- 设备信息 -->
    <div class="navbar-left">
      <button class="back-btn" @click="handleBack">
        ← 返回设备列表
      </button>
      <span class="device-icon">{{ isDesktop ? '💻' : '📱' }}</span>
      <div class="device-info">
        <div class="device-name">{{ deviceDisplayName }}</div>
        <div class="device-meta">{{ deviceDetailDisplay }}</div>
      </div>
      <ElTag type="success" size="small" class="online-tag">在线</ElTag>
      <!-- 坐标显示占位容器 -->
      <div v-if="mouseCoord" class="coord-display">
        <span class="coord-value">({{ mouseCoord.x }}, {{ mouseCoord.y }})</span>
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
      <button class="toolbar-btn light" @click="handleInstall">
        📦 安装 APP
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
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  height: 56px;
  min-height: 56px;
}

.top-navbar.navbar-fixed {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 24px;
  position: relative;
}

.back-btn {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
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
  background: #dcfce7;
  color: #166534;
  border-color: #dcfce7;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.ws-status {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #666;
  font-size: 14px;
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
  font-size: 13px;
  color: #333;
  padding: 8px 16px;
  background: #f5f5f5;
  border-radius: 6px;
}

.screen-select {
  font-size: 13px;
  width: 100px;
}

.screen-select :deep(.el-input__wrapper) {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  box-shadow: none;
  padding: 0 12px;
  min-height: 34px;
}

.screen-select :deep(.el-input__wrapper:hover),
.screen-select :deep(.el-input__wrapper.is-focus) {
  background: #f5f5f5;
  border-color: #1890ff;
  box-shadow: none;
}

.screen-select :deep(.el-input__inner) {
  color: #333;
  font-size: 13px;
}

.screen-select :deep(.el-select__caret) {
  color: #666;
}

.disconnect-btn {
  background: #fee2e2;
  color: #b91c1c;
  padding: 8px 20px;
  border-radius: 6px;
  border: 1px solid #fecaca;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.disconnect-btn:hover {
  background: #fecaca;
}

.navbar-center {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  justify-content: center;
}

.toolbar-btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.toolbar-btn.orange {
  background: #f59e0b;
  color: #fff;
}

.toolbar-btn.orange:hover {
  background: #d97706;
}

.toolbar-btn.gray {
  background: #6b7280;
  color: #fff;
}

.toolbar-btn.gray:hover {
  background: #4b5563;
}

.toolbar-btn.light {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
}

.toolbar-btn.light:hover {
  background: #e8e8e8;
}

.coord-display {
  position: absolute;
  right: -100px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 6px 14px;
  font-size: 12px;
  border-radius: 4px;
}

.coord-value {
  color: #3b82f6;
  font-weight: 600;
}
</style>

<style>
/* 屏幕选择下拉菜单样式（非 scoped，用于 popper-class） */
.screen-dropdown {
  border-radius: 6px !important;
}

.screen-dropdown .el-select-dropdown__item {
  font-size: 13px;
  color: #333;
  padding: 0 16px;
  height: 34px;
  line-height: 34px;
  display: flex;
  align-items: center;
}

.screen-dropdown .el-select-dropdown__item:hover {
  background: #f5f5f5;
}

.screen-dropdown .el-select-dropdown__item.selected {
  color: #1890ff;
  font-weight: 500;
}
</style>