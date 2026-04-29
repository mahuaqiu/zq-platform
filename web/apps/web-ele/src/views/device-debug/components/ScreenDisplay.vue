<script lang="ts" setup>
import type { WebSocketStatus, ScreenSize } from '../types';

interface Props {
  screenshotUrl: string;
  screenSize: ScreenSize;
  wsStatus: WebSocketStatus;
  mouseCoord: { x: number; y: number } | null;
  isInScreen: boolean;
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
  (e: 'contextmenu', event: MouseEvent): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

function handleMouseDown(event: MouseEvent) {
  // 阻止图片默认拖拽行为
  event.preventDefault();
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

function handleContextMenu(event: MouseEvent) {
  event.preventDefault();
  emit('contextmenu', event);
}

// 触摸事件处理（移动端浏览器）
function handleTouchStart(event: TouchEvent) {
  // 阻止默认行为（如缩放、滚动）
  event.preventDefault();
  // 将触摸事件转换为鼠标事件
  if (event.touches.length === 1) {
    const touch = event.touches[0]!;
    const mouseEvent = new MouseEvent('mousedown', {
      clientX: touch.clientX,
      clientY: touch.clientY,
      button: 0,
      bubbles: true
    });
    emit('mousedown', mouseEvent);
  }
}

function handleTouchMove(event: TouchEvent) {
  if (event.touches.length === 1) {
    const touch = event.touches[0]!;
    const mouseEvent = new MouseEvent('mousemove', {
      clientX: touch.clientX,
      clientY: touch.clientY,
      bubbles: true
    });
    emit('mousemove', mouseEvent);
  }
}

function handleTouchEnd(event: TouchEvent) {
  if (event.changedTouches.length === 1) {
    const touch = event.changedTouches[0]!;
    const mouseEvent = new MouseEvent('mouseup', {
      clientX: touch.clientX,
      clientY: touch.clientY,
      button: 0,
      bubbles: true
    });
    emit('mouseup', mouseEvent);
  }
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
      <!-- 屏幕区域 -->
      <div
        class="screen-wrapper"
        :class="{ 'cursor-crosshair': props.isInScreen }"
        @contextmenu="handleContextMenu"
      >
        <img
          v-if="screenshotUrl"
          :src="screenshotUrl"
          class="screen-img"
          draggable="false"
          @mousedown="handleMouseDown"
          @mousemove="handleMouseMove"
          @mouseup="handleMouseUp"
          @mouseleave="handleMouseLeave"
          @touchstart="handleTouchStart"
          @touchmove="handleTouchMove"
          @touchend="handleTouchEnd"
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
  min-height: 0;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
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
  width: 100%;
  height: 100%;
  background: #fff;
  border-radius: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  position: relative;
  overflow: hidden;
}

.screen-wrapper {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  cursor: default; /* 默认为普通鼠标 */
  overflow: hidden;
}

.screen-wrapper.cursor-crosshair {
  cursor: crosshair; /* 在屏幕区域内时为十字鼠标 */
}

.screen-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  /* 阻止触摸设备上的默认行为 */
  touch-action: none;
  user-select: none;
  -webkit-user-drag: none;
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