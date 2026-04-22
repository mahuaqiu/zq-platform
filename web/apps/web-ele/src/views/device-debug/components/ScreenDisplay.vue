<script lang="ts" setup>
import type { WebSocketStatus, ScreenSize } from '../types';

import { computed } from 'vue';

interface Props {
  screenshotUrl: string;
  screenSize: ScreenSize;
  wsStatus: WebSocketStatus;
  mouseCoord: { x: number; y: number } | null;
  clickIndicator: { x: number; y: number; show: boolean };
  isDragging: boolean;
  dragStart: { x: number; y: number } | null;
  dragEnd: { x: number; y: number } | null;
}

interface Emits {
  (e: 'mousedown', event: MouseEvent): void;
  (e: 'mousemove', event: MouseEvent): void;
  (e: 'mouseup', event: MouseEvent): void;
  (e: 'mouseleave'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isConnected = computed(() => props.wsStatus === 'connected');

function handleMouseDown(event: MouseEvent) {
  emit('mousedown', event);
}

function handleMouseMove(event: MouseEvent) {
  emit('mousemove', event);
}

function handleMouseUp(event: MouseEvent) {
  emit('mouseup', event);
}

function handleMouseLeave() {
  emit('mouseleave');
}

// 计算指示器位置百分比
function getIndicatorPercent(coord: number, size: number): string {
  if (size === 0) return '0%';
  return `${(coord / size) * 100}%`;
}
</script>

<template>
  <div class="screen-display">
    <!-- LIVE 标识 -->
    <div v-if="isConnected" class="live-badge live-active">
      LIVE
    </div>
    <div v-else class="live-badge live-inactive">
      LIVE
    </div>

    <!-- 坐标显示 -->
    <div v-if="mouseCoord" class="coord-display">
      X: {{ mouseCoord.x }}, Y: {{ mouseCoord.y }}
    </div>

    <!-- 断开提示 -->
    <div v-if="wsStatus === 'disconnected'" class="disconnect-banner">
      连接已断开
    </div>

    <!-- 屏幕区域 -->
    <div class="screen-wrapper">
      <img
        v-if="screenshotUrl"
        :src="screenshotUrl"
        class="screen-img"
        draggable="false"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseLeave"
      />
      <div v-else class="screen-placeholder">
        <span v-if="wsStatus === 'connecting'">连接中...</span>
        <span v-else>暂无画面</span>
      </div>

      <!-- 点击指示器 -->
      <div
        v-if="clickIndicator.show"
        class="click-indicator"
        :style="{
          left: getIndicatorPercent(clickIndicator.x, screenSize.width),
          top: getIndicatorPercent(clickIndicator.y, screenSize.height),
        }"
      />

      <!-- 拖拽轨迹 -->
      <div
        v-if="isDragging && dragStart && dragEnd"
        class="drag-track"
      >
        <div
          class="drag-point drag-start"
          :style="{
            left: getIndicatorPercent(dragStart.x, screenSize.width),
            top: getIndicatorPercent(dragStart.y, screenSize.height),
          }"
        />
        <div
          class="drag-point drag-end"
          :style="{
            left: getIndicatorPercent(dragEnd.x, screenSize.width),
            top: getIndicatorPercent(dragEnd.y, screenSize.height),
          }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.screen-display {
  position: relative;
  width: 100%;
  height: 100%;
  background: #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
}

.live-active {
  background: #22c55e;
  color: #fff;
}

.live-inactive {
  background: #d4d4d4;
  color: #666;
}

.coord-display {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 4px;
}

.disconnect-banner {
  position: absolute;
  top: 50px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 8px 24px;
  font-size: 14px;
  border-radius: 8px;
}

.screen-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.screen-img {
  max-width: 100%;
  max-height: 100%;
  cursor: crosshair;
}

.screen-placeholder {
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

.drag-start {
  background: #22c55e;
}

.drag-end {
  background: #ef4444;
}
</style>