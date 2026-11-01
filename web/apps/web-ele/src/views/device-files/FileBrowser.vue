<script setup lang="ts">
import type { WorkerFileEntry } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import { useAccessStore } from '@vben/stores';

import {
  ArrowDown,
  Close,
  CopyDocument,
  Delete,
  Document,
  Download,
  FolderOpened,
  InfoFilled,
  Picture,
  Refresh,
  Search,
  Upload,
} from '@element-plus/icons-vue';
import dayjs from 'dayjs';
import {
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  deleteWorkerFileApi,
  getWorkerFileDownloadUrl,
  listWorkerFilesApi,
  uploadWorkerFileDirectApi,
} from '#/api/core/env-machine';

import { filesFromDataTransfer, filesFromInput } from './upload';

interface Props {
  ip: string;
  machineId: string;
  port: string;
}

const props = defineProps<Props>();

const loading = ref(false);
const entries = ref<WorkerFileEntry[]>([]);
const truncated = ref(false);
/** worker 端目录条目超过上限被截断 */
const loadFailed = ref(false);
/** 相对根目录的路径分段 */
const crumbs = ref<string[]>([]);
/** worker 端产物根目录绝对路径(/files/list 的 root 字段,老版本 worker 无) */
const workerRoot = ref('');
const filterText = ref('');
const dragging = ref(false);
const selectedRows = ref<WorkerFileEntry[]>([]);

/** 与 worker files.max_upload_size_mb(1GB) 对齐 */
const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024;

interface UploadItem {
  controller: AbortController | null;
  /** 相对当前目录的目标子目录,'' 表示当前目录 */
  dir: string;
  error: string;
  file: File;
  id: number;
  lastLoaded: number;
  lastTime: number;
  loaded: number;
  name: string;
  size: number;
  speed: number;
  status: 'canceled' | 'done' | 'failed' | 'uploading' | 'waiting';
}

const queueItems = ref<UploadItem[]>([]);
let queueSeq = 0;
let uploading = false;

const currentPath = computed(() => crumbs.value.join('/'));
const workerPath = computed(() => {
  if (!workerRoot.value) return '';
  const sub = currentPath.value
    ? `\\${currentPath.value.replaceAll('/', '\\')}`
    : '';
  return `${workerRoot.value}${sub}`;
});
const filteredEntries = computed(() => {
  const kw = filterText.value.trim().toLowerCase();
  if (!kw) return entries.value;
  return entries.value.filter((e) => e.name.toLowerCase().includes(kw));
});

async function loadList() {
  if (!props.machineId) return;
  loading.value = true;
  try {
    const res = await listWorkerFilesApi(
      props.machineId,
      currentPath.value || undefined,
    );
    entries.value = res.entries;
    truncated.value = res.truncated === true;
    workerRoot.value = res.root || '';
    loadFailed.value = false;
    selectedRows.value = [];
  } catch {
    // 全局拦截器已 toast 错误;这里标记失败态,空态给重试入口
    entries.value = [];
    loadFailed.value = true;
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

function iconType(row: WorkerFileEntry): string {
  if (row.is_dir) return 'dir';
  const ext = row.name.split('.').pop()?.toLowerCase() ?? '';
  if (['7z', 'gz', 'rar', 'tar', 'zip'].includes(ext)) return 'archive';
  if (['bmp', 'gif', 'jpeg', 'jpg', 'png', 'webp'].includes(ext)) {
    return 'image';
  }
  if (['csv', 'xls', 'xlsx'].includes(ext)) return 'sheet';
  if (['har', 'json', 'log', 'txt', 'yaml', 'yml'].includes(ext)) return 'log';
  return 'file';
}

async function copyPath() {
  if (!workerPath.value) return;
  // navigator.clipboard 仅在安全上下文(HTTPS/localhost)可用,
  // 内网 HTTP 部署下为 undefined 或直接拒绝,退回 execCommand 兜底
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(workerPath.value);
      ElMessage.success('已复制路径');
      return;
    } catch {
      // 落到下方 execCommand 兜底
    }
  }
  const textarea = document.createElement('textarea');
  textarea.value = workerPath.value;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.append(textarea);
  textarea.select();
  const ok = document.execCommand('copy');
  textarea.remove();
  if (ok) {
    ElMessage.success('已复制路径');
  } else {
    ElMessage.error('复制失败,请手动选择路径复制');
  }
}

function handleDownload(row: WorkerFileEntry) {
  const token = useAccessStore().accessToken ?? '';
  window.open(
    getWorkerFileDownloadUrl(props.machineId, rowPath(row), token, {
      zip: row.is_dir,
    }),
  );
}

async function handleDelete(row: WorkerFileEntry) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除「${row.name}」吗?${row.is_dir ? '(目录将连同全部内容一起删除)' : ''}`,
    '删除确认',
    { type: 'warning' },
  ).catch(() => false);
  if (!confirmed) return;
  try {
    await deleteWorkerFileApi(props.machineId, rowPath(row));
    ElMessage.success('已删除');
  } catch {
    // 全局拦截器已提示(如文件正被下载时 worker 返回 409 占用)
  }
  loadList();
}

async function handleBatchDelete() {
  const rows = selectedRows.value;
  if (rows.length === 0) return;
  const confirmed = await ElMessageBox.confirm(
    `确定删除选中的 ${rows.length} 项吗?目录将连同全部内容一起删除。`,
    '批量删除确认',
    { type: 'warning' },
  ).catch(() => false);
  if (!confirmed) return;
  let ok = 0;
  for (const row of rows) {
    try {
      await deleteWorkerFileApi(props.machineId, rowPath(row));
      ok += 1;
    } catch {
      // 单项失败继续,全局拦截器已提示原因
    }
  }
  if (ok > 0) ElMessage.success(`已删除 ${ok} 项`);
  loadList();
}

// ===== 上传 =====

const fileInputRef = ref<HTMLInputElement>();
const dirInputRef = ref<HTMLInputElement>();

function handleUploadCommand(command: number | object | string) {
  const input = command === 'folder' ? dirInputRef.value : fileInputRef.value;
  input?.click();
}

function onFilesChosen(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files?.length) enqueueUploads(filesFromInput(input.files));
  // 清空原生 input 的值,避免同一文件不触发 change
  input.value = '';
}

function onDrop(event: DragEvent) {
  dragging.value = false;
  if (!event.dataTransfer) return;
  filesFromDataTransfer(event.dataTransfer).then(enqueueUploads);
}

function enqueueUploads(items: Array<{ dir: string; file: File }>) {
  if (!props.ip || !props.port) {
    ElMessage.error('执行机 IP 或端口未配置,无法上传');
    return;
  }
  for (const item of items) {
    if (item.file.size > MAX_UPLOAD_BYTES) {
      ElMessage.error(`${item.file.name} 超过大小限制(最大 1GB),已跳过`);
      continue;
    }
    queueItems.value.push({
      controller: null,
      dir: item.dir,
      error: '',
      file: item.file,
      id: ++queueSeq,
      lastLoaded: 0,
      lastTime: 0,
      loaded: 0,
      name: item.file.name,
      size: item.file.size,
      speed: 0,
      status: 'waiting',
    });
  }
  runQueue();
}

async function runQueue() {
  if (uploading) return;
  uploading = true;
  try {
    for (;;) {
      const item = queueItems.value.find((i) => i.status === 'waiting');
      if (!item) break;
      await uploadOne(item);
    }
  } finally {
    uploading = false;
    if (queueItems.value.some((i) => i.status === 'done')) loadList();
  }
}

/** 直连上传错误转可读提示 */
function uploadErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail === 'file_exists' ? '同名文件已存在' : detail;
  }
  // 无 response:网络不通/CORS 预检失败/HTTPS 页面拦 HTTP worker
  return `无法连接到执行机 ${props.ip}:${props.port},请检查网络与防火墙`;
}

async function uploadOne(item: UploadItem) {
  item.status = 'uploading';
  item.controller = new AbortController();
  const uploadPath = [currentPath.value, item.dir].filter(Boolean).join('/');
  let overwrite = false;
  for (;;) {
    try {
      await uploadWorkerFileDirectApi(
        props.ip as string,
        props.port as string,
        {
          file: item.file,
          name: item.name,
          overwrite,
          path: uploadPath || undefined,
          signal: item.controller.signal,
          onUploadProgress: (e) => {
            if (!e.total) return;
            const now = Date.now();
            if (item.lastTime && now > item.lastTime) {
              item.speed = Math.max(
                0,
                (e.loaded - item.lastLoaded) / ((now - item.lastTime) / 1000),
              );
            }
            item.lastTime = now;
            item.lastLoaded = e.loaded;
            item.loaded = e.loaded;
          },
        },
      );
      item.status = 'done';
      return;
    } catch (error: any) {
      if (error?.code === 'ERR_CANCELED') {
        item.status = 'canceled';
        return;
      }
      if (
        error?.response?.status === 409 &&
        error?.response?.data?.detail === 'file_exists'
      ) {
        // 列表预检过期:worker 409 兜底,确认覆盖后重传
        const confirmed = await ElMessageBox.confirm(
          `「${item.name}」已存在,是否覆盖?`,
          '覆盖确认',
          { type: 'warning' },
        ).catch(() => false);
        if (!confirmed) {
          item.status = 'canceled';
          return;
        }
        overwrite = true;
        continue;
      }
      item.status = 'failed';
      item.error = uploadErrorMessage(error);
      ElMessage.error(item.error);
      return;
    }
  }
}

function cancelUpload(item: UploadItem) {
  if (item.status === 'uploading' || item.status === 'waiting') {
    item.controller?.abort();
    item.status = 'canceled';
  } else {
    queueItems.value = queueItems.value.filter((i) => i.id !== item.id);
  }
}

watch(
  () => props.machineId,
  (val) => {
    if (val) {
      crumbs.value = [];
      loadList();
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="fb-page">
    <ElBreadcrumb separator="/">
      <ElBreadcrumbItem>
        <a class="fb-crumb" @click="jumpTo(-1)">collected</a>
      </ElBreadcrumbItem>
      <ElBreadcrumbItem v-for="(c, i) in crumbs" :key="i">
        <a class="fb-crumb" @click="jumpTo(i)">{{ c }}</a>
      </ElBreadcrumbItem>
    </ElBreadcrumb>
    <div v-if="workerPath" class="fb-workpath">
      <span>Worker 上的位置</span>
      <span class="fb-workpath-value" :title="workerPath">{{
        workerPath
      }}</span>
      <ElIcon class="fb-copy" title="复制路径" @click="copyPath">
        <CopyDocument />
      </ElIcon>
    </div>

    <div class="fb-toolbar">
      <div class="fb-search">
        <ElIcon class="fb-search-icon"><Search /></ElIcon>
        <input v-model="filterText" type="text" placeholder="过滤当前目录" />
      </div>
      <div class="fb-spacer"></div>
      <span class="fb-hint">支持文件夹 / 多选 / 拖拽</span>
      <ElButton
        :icon="Refresh"
        circle
        title="刷新"
        :disabled="loading"
        @click="loadList"
      />
      <ElDropdown trigger="click" @command="handleUploadCommand">
        <ElButton type="primary">
          <ElIcon style="margin-right: 4px"><Upload /></ElIcon>上传
          <ElIcon style="margin-left: 2px"><ArrowDown /></ElIcon>
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="file">上传文件（可多选）</ElDropdownItem>
            <ElDropdownItem command="folder">上传文件夹</ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>

    <input
      ref="fileInputRef"
      class="fb-hidden-input"
      type="file"
      multiple
      @change="onFilesChosen"
    />
    <input
      ref="dirInputRef"
      class="fb-hidden-input"
      type="file"
      webkitdirectory
      @change="onFilesChosen"
    />

    <div v-if="queueItems.length > 0" class="fb-uploads">
      <div v-for="item in queueItems" :key="item.id" class="fb-upl">
        <span
          class="fb-upl-name"
          :title="item.dir ? `${item.dir}/${item.name}` : item.name"
        >
          {{ item.dir ? `${item.dir}/` : '' }}{{ item.name }}
        </span>
        <span class="fb-upl-meta">
          <template v-if="item.status === 'uploading'">
            {{ formatSize(item.loaded) }} / {{ formatSize(item.size) }} ·
            {{ formatSize(item.speed) }}/s
          </template>
          <template v-else-if="item.status === 'waiting'">等待中</template>
          <template v-else-if="item.status === 'done'">
            {{ formatSize(item.size) }}
          </template>
          <template v-else-if="item.status === 'failed'">{{
            item.error
          }}</template>
          <template v-else>已取消</template>
        </span>
        <div class="fb-upl-track">
          <div
            class="fb-upl-fill"
            :class="{ 'fb-upl-fill-done': item.status === 'done' }"
            :style="{
              width:
                item.status === 'done'
                  ? '100%'
                  : item.size > 0
                    ? `${Math.round((item.loaded / item.size) * 100)}%`
                    : '0%',
            }"
          ></div>
        </div>
        <span
          class="fb-upl-state"
          :class="{
            'fb-ok': item.status === 'done',
            'fb-err': item.status === 'failed',
          }"
        >
          {{
            item.status === 'done'
              ? '已上传'
              : item.status === 'uploading'
                ? `${Math.round((item.loaded / (item.size || 1)) * 100)}%`
                : item.status === 'waiting'
                  ? '排队'
                  : item.status === 'failed'
                    ? '失败'
                    : '已取消'
          }}
        </span>
        <ElIcon class="fb-upl-cancel" @click="cancelUpload(item)">
          <Close />
        </ElIcon>
      </div>
    </div>

    <div
      class="fb-tablewrap"
      @dragover.prevent="dragging = true"
      @dragleave.self="dragging = false"
      @drop.prevent="onDrop"
    >
      <div v-if="dragging" class="fb-dropmask">松开鼠标,上传到当前目录</div>
      <ElTable
        v-loading="loading"
        :data="filteredEntries"
        size="small"
        height="440"
        row-key="name"
        @selection-change="selectedRows = $event"
      >
        <ElTableColumn type="selection" width="40" />
        <ElTableColumn prop="name" label="名称" min-width="320">
          <template #default="{ row }">
            <div class="fb-name" @click="row.is_dir && enterDir(row)">
              <ElIcon class="fb-ico" :class="`fb-ico-${iconType(row)}`">
                <FolderOpened v-if="row.is_dir" />
                <Picture v-else-if="iconType(row) === 'image'" />
                <Document v-else />
              </ElIcon>
              <a v-if="row.is_dir" class="fb-dir">{{ row.name }}/</a>
              <span v-else>{{ row.name }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="大小" width="100">
          <template #default="{ row }">
            <span :class="{ 'fb-muted': row.is_dir }">
              {{ formatSize(row.size) }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="修改时间" width="160">
          <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="90" align="center">
          <template #default="{ row }">
            <ElIcon class="fb-act" title="下载" @click="handleDownload(row)">
              <Download />
            </ElIcon>
            <ElIcon
              class="fb-act fb-act-danger"
              title="删除"
              @click="handleDelete(row)"
            >
              <Delete />
            </ElIcon>
          </template>
        </ElTableColumn>
        <template #empty>
          <div v-if="loadFailed" class="fb-empty">
            加载失败
            <a class="fb-link" @click="loadList">重试</a>
          </div>
          <div v-else class="fb-empty">空目录 — 拖拽文件或文件夹到此处上传</div>
        </template>
      </ElTable>
    </div>

    <div v-if="selectedRows.length > 0" class="fb-batchbar">
      <span
        >已选择 <b>{{ selectedRows.length }}</b> 项</span
      >
      <div class="fb-spacer"></div>
      <ElButton
        size="small"
        type="danger"
        plain
        :icon="Delete"
        @click="handleBatchDelete"
      >
        批量删除
      </ElButton>
      <ElButton size="small" text @click="selectedRows = []">清空选择</ElButton>
    </div>

    <div class="fb-foot">
      <span>
        共 {{ entries.length }} 项
        <template v-if="truncated">（目录过大,仅显示前 2000 项）</template>
      </span>
      <div class="fb-spacer"></div>
      <ElIcon><InfoFilled /></ElIcon>
      <span
        >上传直连执行机（不经平台转发）· 文件夹下载 zip 打包 · 限速 1 MB/s</span
      >
    </div>
  </div>
</template>

<style scoped>
.fb-page {
  display: flex;
  flex-direction: column;
}

.fb-crumb {
  font-weight: 500;
  cursor: pointer;
}

.fb-workpath {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 7px;
  font-size: 12px;
  color: #666;
}

.fb-workpath-value {
  max-width: 620px;
  padding: 2px 8px;
  overflow: hidden;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #333;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.fb-copy {
  color: #909399;
  cursor: pointer;
}

.fb-copy:hover {
  color: var(--el-color-primary);
}

.fb-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.fb-search {
  display: flex;
  gap: 7px;
  align-items: center;
  width: 240px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}

.fb-search-icon {
  color: var(--el-text-color-placeholder);
}

.fb-search input {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--el-text-color-primary);
  outline: none;
  border: 0;
}

.fb-search input::placeholder {
  color: var(--el-text-color-placeholder);
}

.fb-spacer {
  flex: 1;
}

.fb-hint {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.fb-hidden-input {
  display: none;
}

.fb-uploads {
  padding: 2px 12px;
  margin-top: 10px;
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.fb-upl {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 7px 0;
}

.fb-upl + .fb-upl {
  border-top: 1px dashed #ebeef5;
}

.fb-upl-name {
  width: 240px;
  overflow: hidden;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fb-upl-meta {
  width: 200px;
  flex: none;
  overflow: hidden;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fb-upl-track {
  flex: 1;
  height: 6px;
  overflow: hidden;
  background: #ebeef5;
  border-radius: 3px;
}

.fb-upl-fill {
  height: 100%;
  background: var(--el-color-primary);
  border-radius: 3px;
}

.fb-upl-fill-done {
  background: var(--el-color-success);
}

.fb-upl-state {
  width: 60px;
  flex: none;
  font-size: 12px;
  color: var(--el-text-color-regular);
  text-align: right;
}

.fb-ok {
  color: var(--el-color-success);
}

.fb-err {
  color: var(--el-color-danger);
}

.fb-upl-cancel {
  flex: none;
  padding: 2px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  border-radius: 3px;
}

.fb-upl-cancel:hover {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.fb-tablewrap {
  position: relative;
  margin-top: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
}

.fb-dropmask {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 500;
  color: var(--el-color-primary);
  pointer-events: none;
  background: rgb(64 158 255 / 8%);
  border: 2px dashed var(--el-color-primary);
  border-radius: 4px;
}

.fb-name {
  display: flex;
  gap: 9px;
  align-items: center;
}

.fb-dir {
  color: var(--el-color-primary);
  cursor: pointer;
}

.fb-dir:hover {
  text-decoration: underline;
}

.fb-ico {
  flex: none;
}

.fb-ico-dir {
  color: #e6a23c;
}

.fb-ico-log {
  color: var(--el-color-primary);
}

.fb-ico-archive,
.fb-ico-sheet {
  color: var(--el-color-success);
}

.fb-ico-image {
  color: #a855f7;
}

.fb-ico-file {
  color: var(--el-text-color-secondary);
}

.fb-muted {
  color: var(--el-text-color-placeholder);
}

.fb-act {
  padding: 4px;
  margin: 0 3px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  border: 1px solid transparent;
  border-radius: 4px;
}

.fb-act:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}

.fb-act-danger:hover {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-7);
}

.fb-batchbar {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 7px 12px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 4px;
}

.fb-foot {
  display: flex;
  gap: 6px;
  align-items: center;
  padding-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.fb-empty {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.fb-link {
  margin-left: 4px;
  color: var(--el-color-primary);
  cursor: pointer;
}
</style>
