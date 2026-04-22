<script lang="ts" setup>
import { ref, computed } from 'vue';

import { ElDialog, ElButton, ElMessage, ElProgress } from 'element-plus';

interface Props {
  visible: boolean;
  deviceType: string;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'upload', file: File): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const selectedFile = ref<File | null>(null);
const isUploading = ref(false);
const uploadProgress = ref(0);

const allowedExtensions = computed(() => {
  switch (props.deviceType) {
    case 'android':
      return '.apk';
    case 'ios':
      return '.ipa';
    case 'windows':
      return '.exe';
    case 'mac':
      return '.dmg, .pkg';
    default:
      return '';
  }
});

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
  }
}

function handleDrop(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    selectedFile.value = event.dataTransfer.files[0];
  }
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择安装包文件');
    return;
  }

  isUploading.value = true;
  uploadProgress.value = 0;

  // 模拟上传进度（实际需要调用后端 API）
  emit('upload', selectedFile.value);

  // 清理状态
  selectedFile.value = null;
  isUploading.value = false;
  uploadProgress.value = 0;
  dialogVisible.value = false;
}

function handleCancel() {
  selectedFile.value = null;
  dialogVisible.value = false;
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    title="安装 APP"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="install-content">
      <!-- 文件上传区域 -->
      <div
        class="upload-area"
        @drop="handleDrop"
        @dragover.prevent
      >
        <div class="upload-icon">📦</div>
        <div class="upload-text">
          拖拽文件到此处，或点击选择
        </div>
        <input
          type="file"
          :accept="allowedExtensions"
          class="file-input"
          @change="handleFileSelect"
        />
      </div>

      <!-- 已选文件 -->
      <div v-if="selectedFile" class="selected-file">
        <span class="file-name">{{ selectedFile.name }}</span>
        <span class="file-size">{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB</span>
      </div>

      <!-- 支持格式提示 -->
      <div class="format-tip">
        支持格式: {{ allowedExtensions }}
      </div>

      <!-- 上传进度 -->
      <ElProgress v-if="isUploading" :percentage="uploadProgress" />
    </div>

    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton
        type="primary"
        :disabled="!selectedFile || isUploading"
        @click="handleUpload"
      >
        上传并安装
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.install-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s;
}

.upload-area:hover {
  border-color: #3b82f6;
}

.upload-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.upload-text {
  font-size: 14px;
  color: #666;
}

.file-input {
  display: none;
}

.selected-file {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.file-name {
  font-size: 14px;
  color: #111;
}

.file-size {
  font-size: 12px;
  color: #666;
}

.format-tip {
  font-size: 12px;
  color: #999;
}
</style>