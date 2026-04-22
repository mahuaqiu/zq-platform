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
      return { text: '连接中', type: 'warning' };
    case 'connected':
      return { text: '已连接', type: 'success' };
    case 'disconnected':
      return { text: '已断开', type: 'info' };
    case 'error':
      return { text: '连接错误', type: 'danger' };
    default:
      return { text: '未知', type: 'info' };
  }
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

function handleFullscreen() {
  emit('fullscreen');
}
</script>

<template>
  <div class="top-navbar">
    <!-- 设备信息 -->
    <div class="navbar-left">
      <ElButton size="small" @click="handleBack">
        返回
      </ElButton>
      <span class="device-icon">{{ isDesktop ? '💻' : '📱' }}</span>
      <span class="device-name">{{ assetNumber }}</span>
      <span v-if="deviceSn" class="device-sn">| {{ deviceSn }}</span>
      <ElTag type="success" size="small">在线</ElTag>
    </div>

    <!-- 连接状态和操作 -->
    <div class="navbar-right">
      <ElTag :type="wsStatusDisplay.type" size="small">
        {{ wsStatusDisplay.text }}
      </ElTag>
      <span v-if="fps > 0" class="fps-display">{{ fps }} fps</span>
      <ElButton v-if="isDesktop" size="small" @click="handleFullscreen">
        全屏
      </ElButton>
      <ElButton
        v-if="wsStatus === 'connected'"
        size="small"
        type="danger"
        @click="handleDisconnect"
      >
        断开
      </ElButton>
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
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  height: 56px;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-icon {
  font-size: 18px;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  color: #111;
}

.device-sn {
  font-size: 14px;
  color: #666;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fps-display {
  font-size: 12px;
  color: #666;
  padding: 2px 8px;
  background: #f5f5f5;
  border-radius: 4px;
}
</style>