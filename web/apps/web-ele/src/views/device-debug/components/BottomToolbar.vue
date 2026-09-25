<script lang="ts" setup>
import type { OperationRecord } from '../types';

import { computed } from 'vue';

import { isDesktopDevice } from '../utils';

interface Props {
  deviceType: string;
  operationHistory: OperationRecord[];
  clickCount: number;
  swipeCount: number;
}

interface Emits {
  (e: 'keypress'): void;
  (e: 'input'): void;
  (e: 'screenshot'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isDesktop = computed(() => isDesktopDevice(props.deviceType));

function handleKeyPress() {
  emit('keypress');
}

function handleInput() {
  emit('input');
}

function handleScreenshot() {
  emit('screenshot');
}
</script>

<template>
  <div class="bottom-toolbar">
    <!-- 左侧操作按钮 -->
    <div class="toolbar-left">
      <button class="toolbar-btn orange" @click="handleKeyPress">
        ⌨ 按键操作
      </button>
      <button v-if="isDesktop" class="toolbar-btn gray" @click="handleInput">
        📝 输入文本
      </button>
      <div class="toolbar-divider"></div>
      <button class="toolbar-btn light" @click="handleScreenshot">
        📷 截图保存
      </button>
    </div>

    <!-- 右侧统计 -->
    <div class="toolbar-right">
      <span class="stats-display">
        已操作: {{ clickCount }} 次点击, {{ swipeCount }} 次滑动
      </span>
    </div>
  </div>
</template>

<style scoped>
.bottom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  min-height: 56px;
  padding: 0 32px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
}

.toolbar-left {
  display: flex;
  gap: 16px;
  align-items: center;
}

.toolbar-btn {
  padding: 10px 20px;
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

.toolbar-btn.purple {
  color: #fff;
  background: #9b59b6;
}

.toolbar-btn.purple:hover {
  background: #8e44ad;
}

.toolbar-btn.light {
  color: #333;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
}

.toolbar-btn.light:hover {
  background: #e8e8e8;
}

.toolbar-divider {
  width: 1px;
  height: 32px;
  background: #e8e8e8;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.stats-display {
  font-size: 13px;
  color: #666;
}
</style>
