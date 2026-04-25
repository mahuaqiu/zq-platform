<script lang="ts" setup>
import type { WebSocketStatus } from '../types';
import { isDesktopDevice } from '../utils';

import { computed } from 'vue';

import { ElButton, ElTag } from 'element-plus';

interface Props {
  deviceType: string;
  assetNumber: string;
  deviceSn?: string;
  wsStatus: WebSocketStatus;
  fps: number;
}

interface Emits {
  (e: 'back'): void;
  (e: 'disconnect'): void;
  (e: 'reconnect'): void;
  (e: 'fullscreen'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isDesktop = computed(() => isDesktopDevice(props.deviceType));

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

function handleBack() {
  emit('back');
}

function handleDisconnect() {
  emit('disconnect');
}

function handleReconnect() {
  emit('reconnect');
}

function handleFullscreen() {
  emit('fullscreen');
}
</script>

<template>
  <div class="top-navbar">
    <!-- 设备信息 -->
    <div class="navbar-left">
      <button class="back-btn" @click="handleBack">
        ← 返回设备列表
      </button>
      <span class="device-icon">{{ isDesktop ? '💻' : '📱' }}</span>
      <div class="device-info">
        <div class="device-name">{{ assetNumber }}</div>
        <div class="device-meta">{{ deviceSn || '未知设备' }}</div>
      </div>
      <ElTag type="success" size="small" class="online-tag">在线</ElTag>
    </div>

    <!-- 连接状态和操作 -->
    <div class="navbar-right">
      <div class="ws-status">
        <span v-if="wsConnected" class="ws-dot connected">●</span>
        <span v-else class="ws-dot disconnected">●</span>
        <span class="ws-text">{{ wsStatusDisplay.text }}</span>
      </div>
      <span v-if="fps > 0" class="fps-display">{{ fps }} fps</span>
      <button v-if="isDesktop" class="fullscreen-btn" @click="handleFullscreen">
        ⛶ 全屏
      </button>
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

.navbar-left {
  display: flex;
  align-items: center;
  gap: 24px;
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

.fullscreen-btn {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.fullscreen-btn:hover {
  background: #e8e8e8;
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
</style>