<script lang="ts" setup>
import { ref, watch } from 'vue';

import { ElDialog, ElButton, ElMessage } from 'element-plus';

const props = defineProps<{
  visible: boolean;
  logUrl: string | null;
  caseName: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const dialogVisible = ref(props.visible);

watch(
  () => props.visible,
  (val) => {
    dialogVisible.value = val;
  },
);

watch(dialogVisible, (val) => {
  emit('update:visible', val);
});

// 打开新窗口查看日志
function openInNewWindow() {
  if (props.logUrl) {
    window.open(props.logUrl, '_blank');
  } else {
    ElMessage.warning('暂无日志地址');
  }
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    :title="`日志详情 - ${caseName}`"
    width="80%"
    top="5vh"
  >
    <div class="log-container">
      <div v-if="logUrl" class="log-iframe-wrapper">
        <iframe :src="logUrl" class="log-iframe" frameborder="0"></iframe>
      </div>
      <div v-else class="log-empty">
        <p>暂无日志内容</p>
      </div>
    </div>
    <template #footer>
      <ElButton @click="dialogVisible = false">关闭</ElButton>
      <ElButton type="primary" @click="openInNewWindow">新窗口打开</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.log-container {
  min-height: 400px;
}

.log-iframe-wrapper {
  width: 100%;
  height: 70vh;
}

.log-iframe {
  width: 100%;
  height: 100%;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: #999;
  background: #fafafa;
  border-radius: 4px;
}
</style>