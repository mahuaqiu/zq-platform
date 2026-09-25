<script setup lang="ts">
import type { WorkerFileEntry } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import { useAccessStore } from '@vben/stores';

import dayjs from 'dayjs';
import {
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElDialog,
  ElMessage,
  ElMessageBox,
  ElProgress,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  deleteWorkerFileApi,
  getWorkerFileDownloadUrl,
  listWorkerFilesApi,
  uploadWorkerFileApi,
} from '#/api/core/env-machine';

interface Props {
  visible: boolean;
  machineId: string;
  machineName: string;
  ip?: string;
  port?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{ 'update:visible': [value: boolean] }>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const loading = ref(false);
const entries = ref<WorkerFileEntry[]>([]);
/** 相对根目录的路径分段 */
const crumbs = ref<string[]>([]);

const uploading = ref(false);
const uploadProgress = ref(0);
const uploadLabel = ref('');
let uploadAbort: AbortController | null = null;
const fileInputRef = ref<HTMLInputElement>();

const currentPath = computed(() => crumbs.value.join('/'));

async function loadList() {
  if (!props.machineId) return;
  loading.value = true;
  try {
    const res = await listWorkerFilesApi(
      props.machineId,
      currentPath.value || undefined,
    );
    entries.value = res.entries;
  } catch {
    entries.value = [];
  } finally {
    loading.value = false;
  }
}

function enterDir(row: WorkerFileEntry) {
  crumbs.value.push(row.name);
  loadList();
}

function jumpTo(index: number) {
  // -1 = 根目录
  crumbs.value = index < 0 ? [] : crumbs.value.slice(0, index + 1);
  loadList();
}

function formatSize(size: number): string {
  if (!size) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatTime(mtime: number): string {
  return mtime ? dayjs(mtime * 1000).format('YYYY-MM-DD HH:mm') : '—';
}

function rowPath(row: WorkerFileEntry): string {
  return [...crumbs.value, row.name].join('/');
}

function handleDownload(row: WorkerFileEntry) {
  const token = useAccessStore().accessToken ?? '';
  window.open(getWorkerFileDownloadUrl(props.machineId, rowPath(row), token));
}

async function handleDelete(row: WorkerFileEntry) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除「${row.name}」吗?${row.is_dir ? '(仅可删除空目录)' : ''}`,
    '删除确认',
    { type: 'warning' },
  ).catch(() => false);
  if (!confirmed) return;
  await deleteWorkerFileApi(props.machineId, rowPath(row));
  ElMessage.success('已删除');
  loadList();
}

function triggerUpload() {
  fileInputRef.value?.click();
}

async function handleFileChosen(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file || !props.machineId) return;

  // 同名预检:存在则确认覆盖(worker 端 409 兜底)
  let overwrite = false;
  const exists = entries.value.some((e) => e.name === file.name && !e.is_dir);
  if (exists) {
    const confirmed = await ElMessageBox.confirm(
      `「${file.name}」已存在,是否覆盖?`,
      '覆盖确认',
      { type: 'warning' },
    ).catch(() => false);
    if (!confirmed) return;
    overwrite = true;
  }

  uploading.value = true;
  uploadProgress.value = 0;
  uploadLabel.value = file.name;
  uploadAbort = new AbortController();
  try {
    await uploadWorkerFileApi(props.machineId, {
      path: currentPath.value || undefined,
      name: file.name,
      file,
      overwrite,
      signal: uploadAbort.signal,
      onUploadProgress: (e) => {
        if (e.total) {
          uploadProgress.value = Math.round((e.loaded / e.total) * 100);
          uploadLabel.value = `${file.name}(${formatSize(e.loaded)} / ${formatSize(e.total)})`;
        }
      },
    });
    ElMessage.success('上传完成');
    loadList();
  } catch {
    // 取消或失败:全局拦截器已提示,静默
  } finally {
    uploading.value = false;
    uploadAbort = null;
  }
}

function cancelUpload() {
  uploadAbort?.abort();
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      crumbs.value = [];
      loadList();
    }
  },
);
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    :title="`文件管理 — ${machineName}${ip ? ` (${ip}:${port})` : ''}`"
    width="1000px"
    destroy-on-close
  >
    <div class="fm-toolbar">
      <ElBreadcrumb separator="/">
        <ElBreadcrumbItem>
          <a class="fm-crumb" @click="jumpTo(-1)">collected</a>
        </ElBreadcrumbItem>
        <ElBreadcrumbItem v-for="(c, i) in crumbs" :key="i">
          <a class="fm-crumb" @click="jumpTo(i)">{{ c }}</a>
        </ElBreadcrumbItem>
      </ElBreadcrumb>
      <div class="fm-actions">
        <ElButton size="small" :disabled="loading" @click="loadList">
          刷新
        </ElButton>
        <ElButton
          size="small"
          type="primary"
          :disabled="uploading"
          @click="triggerUpload"
        >
          上传文件
        </ElButton>
      </div>
    </div>

    <input
      ref="fileInputRef"
      class="fm-hidden-input"
      type="file"
      @change="handleFileChosen"
    />

    <div v-if="uploading" class="fm-upload-bar">
      <span class="fm-upload-label">↑ {{ uploadLabel }}</span>
      <ElProgress
        class="fm-upload-progress"
        :percentage="uploadProgress"
        :stroke-width="8"
      />
      <ElButton size="small" @click="cancelUpload">取消</ElButton>
    </div>

    <ElTable v-loading="loading" :data="entries" size="small" height="420px">
      <ElTableColumn prop="name" label="名称" min-width="280">
        <template #default="{ row }">
          <a v-if="row.is_dir" class="fm-dir" @click="enterDir(row)">{{
            row.name
          }}</a>
          <span v-else>{{ row.name }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="大小" width="100">
        <template #default="{ row }">
          <span :class="{ 'fm-muted': row.is_dir }">{{
            formatSize(row.size)
          }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="修改时间" width="160">
        <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="130">
        <template #default="{ row }">
          <a v-if="!row.is_dir" class="env-link" @click="handleDownload(row)">
            下载
          </a>
          <a class="env-link-danger" @click="handleDelete(row)">删除</a>
        </template>
      </ElTableColumn>
      <template #empty>空目录</template>
    </ElTable>

    <div class="fm-footer">
      共 {{ entries.length }} 项 · 下载/上传经平台流式代理,限速 1 MB/s(worker
      端可配)
    </div>
  </ElDialog>
</template>

<style scoped>
.fm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.fm-crumb {
  font-weight: 500;
  cursor: pointer;
}

.fm-actions {
  display: flex;
  gap: 8px;
}

.fm-hidden-input {
  display: none;
}

.fm-upload-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: var(--el-color-warning-light-9);
  border-radius: 4px;
}

.fm-upload-label {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  white-space: nowrap;
}

.fm-upload-progress {
  flex: 1;
}

.fm-dir {
  color: var(--el-color-primary);
  cursor: pointer;
}

.fm-muted {
  color: var(--el-text-color-placeholder);
}

.fm-footer {
  padding-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.env-link {
  margin-right: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
}

.env-link-danger {
  color: var(--el-color-danger);
}
</style>
