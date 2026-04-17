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
  { value: 'Home', label: 'Home', desc: '返回主页' },
  { value: 'Back', label: 'Back', desc: '返回上一页' },
  { value: 'Enter', label: 'Enter', desc: '确认' },
  { value: 'Power', label: 'Power', desc: '电源键' },
  { value: 'Volume Up', label: '音量+', desc: '音量增加' },
  { value: 'Volume Down', label: '音量-', desc: '音量减少' },
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
    title="按键操作"
    width="360px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="key-grid">
      <div
        v-for="key in keys"
        :key="key.value"
        class="key-item"
        :class="{ disabled: disabled }"
        @click="!disabled && handleKeyPress(key.value)"
      >
        <div class="key-label">{{ key.label }}</div>
        <div class="key-desc">{{ key.desc }}</div>
      </div>
    </div>

    <template #footer>
      <ElButton @click="handleClose">取消</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.key-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.key-item {
  padding: 12px 8px;
  text-align: center;
  background: #f5f5f5;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.key-item:hover:not(.disabled) {
  background: #1890ff;
}

.key-item:hover:not(.disabled) .key-label,
.key-item:hover:not(.disabled) .key-desc {
  color: #fff;
}

.key-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.key-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.key-desc {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
</style>