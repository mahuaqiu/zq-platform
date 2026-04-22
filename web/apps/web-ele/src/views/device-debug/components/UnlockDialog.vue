<script lang="ts" setup>
import { ref, computed } from 'vue';

import { ElDialog, ElInput, ElButton } from 'element-plus';

interface Props {
  visible: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', password?: string): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const password = ref('');

function handleConfirm() {
  emit('confirm', password.value);
  password.value = '';
}

function handleCancel() {
  password.value = '';
  dialogVisible.value = false;
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    title="解锁屏幕"
    width="400px"
    :close-on-click-modal="false"
  >
    <div class="unlock-content">
      <div class="unlock-tip">
        如果设备无密码锁，可直接解锁
      </div>
      <ElInput
        v-model="password"
        placeholder="输入解锁密码（可选）"
        type="password"
        show-password
      />
    </div>
    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton type="primary" @click="handleConfirm">确认解锁</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.unlock-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.unlock-tip {
  font-size: 12px;
  color: #666;
}
</style>