<script lang="ts" setup>
import type { WebSocketStatus, ScreenSize } from '../types';

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
    <!-- 断开提示 -->
    <div v-if="wsStatus === 'disconnected'" class="disconnect-banner">
      连接已断开
    </div>

    <!-- 屏幕卡片区域 -->
    <div class="screen-card">
      <!-- 坐标显示 -->
      <div v-if="mouseCoord" class="coord-display">
        坐标: <span class="coord-value">({{ mouseCoord.x }}, {{ mouseCoord.y }})</span>
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
          <div class="placeholder-icon">🖥</div>
          <div class="placeholder-text">实时屏幕推流画面</div>
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
  </div>
</template>

<style scoped>
.screen-display {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
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
  z-index: 10;
}

.screen-card {
  width: 94%;
  height: 94%;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  position: relative;
  overflow: hidden;
}

.coord-display {
  position: absolute;
  bottom: 16px;
  right: 16px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 10px 16px;
  font-size: 14px;
  border-radius: 6px;
  z-index: 10;
}

.coord-value {
  color: #3b82f6;
}

.screen-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
  cursor: crosshair;
}

.screen-img {
  max-width: 100%;
  max-height: 100%;
}

.screen-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #e8e8e8;
}

.placeholder-icon {
  font-size: 48px;
  color: #fff;
}

.placeholder-text {
  font-size: 18px;
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