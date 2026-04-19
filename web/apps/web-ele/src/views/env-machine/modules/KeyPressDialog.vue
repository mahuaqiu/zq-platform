<script lang="ts" setup>

import { ElButton, ElDialog } from 'element-plus';

interface Props {
  visible: boolean;
  disabled?: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'press', key: string): void;
}

defineProps<Props>();
const emit = defineEmits<Emits>();

// 按键列表
const keys = [
  { value: 'Home', icon: '🏠', text: 'Home', desc: '返回主页' },
  { value: 'Back', icon: '↩️', text: 'Back', desc: '返回上一页' },
  { value: 'Enter', icon: '⏎', text: 'Enter', desc: '确认' },
  { value: 'Power', icon: '🔴', text: 'Power', desc: '电源键' },
  { value: 'Volume Up', icon: '🔊', text: 'Volume Up', desc: '音量+' },
  { value: 'Volume Down', icon: '🔉', text: 'Volume Down', desc: '音量-' },
];

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 点击按键
function handleKeyPress(key: string) {
  emit('press', key);
  handleClose();
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="🎹 按键选择"
    width="380px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="key-desc-top">选择按键类型</div>
    <div class="key-list">
      <ElButton
        v-for="key in keys"
        :key="key.value"
        type="primary"
        class="key-item-btn"
        :disabled="disabled"
        @click="handleKeyPress(key.value)"
      >
        <span class="key-icon">{{ key.icon }}</span>
        <span class="key-text">{{ key.text }}</span>
        <span class="key-desc">({{ key.desc }})</span>
      </ElButton>
    </div>
    <div class="key-tip">点击按键立即执行</div>
  </ElDialog>
</template>

<style scoped>
.key-desc-top {
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
}

.key-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.key-item-btn {
  width: 100%;
  padding: 10px;
  text-align: left;
  justify-content: flex-start;
}

.key-item-btn :deep(.el-button__content) {
  justify-content: flex-start;
}

.key-icon {
  display: inline-block;
  width: 24px;
  text-align: center;
}

.key-text {
  font-size: 13px;
  min-width: 100px;
}

.key-desc {
  font-size: 12px;
  opacity: 0.8;
}

.key-tip {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
  font-size: 12px;
  color: #999;
  text-align: center;
}
</style>