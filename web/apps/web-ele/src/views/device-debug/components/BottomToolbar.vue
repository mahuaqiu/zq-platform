<script lang="ts" setup>
import type { OperationRecord } from '../types';
import { isDesktopDevice } from '../utils';

import { computed } from 'vue';

import { ElButton } from 'element-plus';

interface Props {
  deviceType: string;
  operationHistory: OperationRecord[];
  clickCount: number;
  swipeCount: number;
}

interface Emits {
  (e: 'keypress'): void;
  (e: 'input'): void;
  (e: 'install'): void;
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

function handleInstall() {
  emit('install');
}

function handleScreenshot() {
  emit('screenshot');
}
</script>

<template>
  <div class="bottom-toolbar">
    <!-- 左侧操作按钮 -->
    <div class="toolbar-left">
      <ElButton size="small" @click="handleKeyPress">
        按键操作
      </ElButton>
      <ElButton v-if="isDesktop" size="small" @click="handleInput">
        输入文本
      </ElButton>
      <ElButton size="small" @click="handleInstall">
        安装 APP
      </ElButton>
    </div>

    <!-- 右侧截图和统计 -->
    <div class="toolbar-right">
      <ElButton size="small" type="primary" @click="handleScreenshot">
        截图保存
      </ElButton>
      <span class="stats-display">
        点击: {{ clickCount }} | 滑动: {{ swipeCount }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.bottom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  height: 56px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stats-display {
  font-size: 12px;
  color: #666;
}
</style>