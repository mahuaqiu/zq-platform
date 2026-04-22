<script lang="ts" setup>
import { ref, computed } from 'vue';

import { ElDialog, ElInput, ElButton, ElMessage } from 'element-plus';

interface Props {
  visible: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'send', text: string): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const textValue = ref('');

function handleSend() {
  if (!textValue.value.trim()) {
    ElMessage.warning('请输入文本内容');
    return;
  }
  emit('send', textValue.value);
  textValue.value = '';
}

function handleCancel() {
  textValue.value = '';
  dialogVisible.value = false;
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    title="输入文本"
    width="400px"
    :close-on-click-modal="false"
  >
    <ElInput
      v-model="textValue"
      placeholder="输入要发送的文本..."
      type="textarea"
      :rows="4"
    />
    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton type="primary" :disabled="!textValue.trim()" @click="handleSend">
        发送
      </ElButton>
    </template>
  </ElDialog>
</template>