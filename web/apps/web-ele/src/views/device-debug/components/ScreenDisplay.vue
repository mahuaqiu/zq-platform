<script lang="ts" setup>
import type { ScreenSize, WebSocketStatus } from '../types';

import { onMounted, onUnmounted, ref } from 'vue';

import { calculateContainRenderArea } from '../utils';

interface Props {
  screenshotUrl: string;
  screenSize: ScreenSize;
  wsStatus: WebSocketStatus;
  mouseCoord: null | { x: number; y: number };
  isInScreen: boolean;
  clickIndicator: { show: boolean; x: number; y: number };
  isDragging: boolean;
  dragStart: null | { x: number; y: number };
  dragEnd: null | { x: number; y: number };
  /** 渲染模式：H264(MSE) 时为 true，渲染 <video>；JPEG/MJPEG 时为 false，渲染 <img> */
  videoMode?: boolean;
}

interface Emits {
  (e: 'pointerdown', event: PointerEvent): void;
  (e: 'pointermove', event: PointerEvent): void;
  (e: 'pointerup', event: PointerEvent): void;
  (e: 'pointercancel', event: PointerEvent): void;
  (e: 'pointerleave'): void;
  (e: 'wheel', event: WheelEvent): void;
  (e: 'contextmenu', event: MouseEvent): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();
const screenWrapperRef = ref<HTMLElement | null>(null);
const wrapperSize = ref({ width: 0, height: 0 });
let resizeObserver: null | ResizeObserver = null;

// MSE 方案渲染的 <video> 元素。
// MSE 解码器（useMseDecoder）需要绑定此元素，由父组件通过 ref 拿到后传入 useWebSocket.attachVideoEl。
const videoRef = ref<HTMLVideoElement | null>(null);

defineExpose({ videoRef });

function handlePointerDown(event: PointerEvent) {
  // 阻止图片/视频默认拖拽与文本选择
  event.preventDefault();
  // 捕获指针：按住拖拽移出画面区域后事件继续派发，拖拽不中断
  try {
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  } catch {
    // 老浏览器不支持捕获时由 pointerleave 兜底
  }
  emit('pointerdown', event);
}

function handlePointerMove(event: PointerEvent) {
  emit('pointermove', event);
}

function handlePointerUp(event: PointerEvent) {
  emit('pointerup', event);
}

function handlePointerCancel(event: PointerEvent) {
  emit('pointercancel', event);
}

function handleWheel(event: WheelEvent) {
  emit('wheel', event);
}

function handlePointerLeave() {
  emit('pointerleave');
}

function handleContextMenu(event: MouseEvent) {
  event.preventDefault();
  emit('contextmenu', event);
}

// 计算指示器位置百分比
function getIndicatorStyle(coord: {
  x: number;
  y: number;
}): Record<string, string> {
  const { width, height } = wrapperSize.value;
  const { width: sourceWidth, height: sourceHeight } = props.screenSize;

  if (width <= 0 || height <= 0 || sourceWidth <= 0 || sourceHeight <= 0) {
    return { left: '0px', top: '0px' };
  }

  const renderInfo = calculateContainRenderArea(
    width,
    height,
    sourceWidth,
    sourceHeight,
    0,
    0,
  );
  const scaleX = renderInfo.renderedWidth / sourceWidth;
  const scaleY = renderInfo.renderedHeight / sourceHeight;

  return {
    left: `${renderInfo.offsetX + coord.x * scaleX}px`,
    top: `${renderInfo.offsetY + coord.y * scaleY}px`,
  };
}

onMounted(() => {
  const wrapper = screenWrapperRef.value;
  if (!wrapper) return;

  const updateSize = () => {
    wrapperSize.value = {
      width: wrapper.clientWidth,
      height: wrapper.clientHeight,
    };
  };
  updateSize();
  if (typeof ResizeObserver === 'undefined') return;
  resizeObserver = new ResizeObserver(updateSize);
  resizeObserver.observe(wrapper);
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});
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
        ref="screenWrapperRef"
        :class="{ 'cursor-crosshair': props.isInScreen }"
        @contextmenu="handleContextMenu"
      >
        <!-- H264 (MSE) 模式：渲染 <video>。Pointer Events 统一鼠标/触摸输入 -->
        <video
          v-if="props.videoMode"
          ref="videoRef"
          class="screen-img"
          autoplay
          muted
          playsinline
          @pointerdown="handlePointerDown"
          @pointermove="handlePointerMove"
          @pointerup="handlePointerUp"
          @pointercancel="handlePointerCancel"
          @pointerleave="handlePointerLeave"
          @wheel="handleWheel"
          @contextmenu="handleContextMenu"
        ></video>
        <!-- JPEG/MJPEG 模式：渲染 <img> -->
        <img
          v-else-if="screenshotUrl"
          :src="screenshotUrl"
          class="screen-img"
          draggable="false"
          @pointerdown="handlePointerDown"
          @pointermove="handlePointerMove"
          @pointerup="handlePointerUp"
          @pointercancel="handlePointerCancel"
          @pointerleave="handlePointerLeave"
          @wheel="handleWheel"
          @contextmenu="handleContextMenu"
        />
        <div v-else class="screen-placeholder">
          <div class="placeholder-icon">🖥</div>
          <div class="placeholder-text">实时屏幕推流画面</div>
        </div>

        <!-- 点击指示器 -->
        <div
          v-if="clickIndicator.show"
          class="click-indicator"
          :style="getIndicatorStyle(clickIndicator)"
        ></div>

        <!-- 拖拽轨迹 -->
        <div v-if="isDragging && dragStart && dragEnd" class="drag-track">
          <div
            class="drag-point drag-start"
            :style="{
              ...getIndicatorStyle(dragStart),
            }"
          ></div>
          <div
            class="drag-point drag-end"
            :style="{
              ...getIndicatorStyle(dragEnd),
            }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.screen-display {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 0;
  background: #f0f2f5;
}

.disconnect-banner {
  position: absolute;
  top: 50px;
  left: 50%;
  z-index: 10;
  padding: 8px 24px;
  font-size: 14px;
  color: #fff;
  background: rgb(0 0 0 / 80%);
  border-radius: 8px;
  transform: translateX(-50%);
}

.screen-card {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #fff;
  border-radius: 0;
  box-shadow: 0 1px 3px rgb(0 0 0 / 8%);
}

.screen-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  cursor: default; /* 默认为普通鼠标 */
  background: #fff;
}

.screen-wrapper.cursor-crosshair {
  cursor: crosshair; /* 在屏幕区域内时为十字鼠标 */
}

.screen-img {
  /* video 默认 display:inline 会留 baseline 间隙，统一改为 block */
  display: block;
  max-width: 100%;
  max-height: 100%;

  /* 阻止触摸设备上的默认行为 */
  touch-action: none;
  user-select: none;
  object-fit: contain;
  -webkit-user-drag: none;
}

.screen-placeholder {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: center;
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
  background: rgb(24 144 255 / 80%);
  border-radius: 50%;
  box-shadow: 0 2px 8px rgb(0 0 0 / 30%);
  transform: translate(-50%, -50%);
  animation: click-pulse 0.5s ease-out;
}

@keyframes click-pulse {
  0% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(0);
  }

  100% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(1);
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
  border: 3px solid #fff;
  border-radius: 50%;
  box-shadow: 0 2px 8px rgb(0 0 0 / 50%);
  transform: translate(-50%, -50%);
}

.drag-start {
  background: #22c55e;
}

.drag-end {
  background: #ef4444;
}
</style>
