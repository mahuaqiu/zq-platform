<script setup lang="ts">
import type { PerformanceVersion } from '#/api/core/performance-monitor';

import { computed, ref, watch } from 'vue';

import {
  ElButton,
  ElCheckbox,
  ElDialog,
  ElInput,
  ElMessage,
  ElTag,
} from 'element-plus';

import { VERSION_COLORS } from '../types';

interface SelectedVersion {
  id: string;
  name: string;
  color: string;
  createTime?: string;
}

const props = defineProps<{
  selectedIds: string[];
  versions: PerformanceVersion[];
}>();

const emit = defineEmits<{
  (e: 'update:selectedIds', value: string[]): void;
}>();

// 弹窗状态
const showDialog = ref(false);
const searchKeyword = ref('');

// 已选版本列表（带颜色）
const selectedVersions = computed<SelectedVersion[]>(() => {
  const selected: SelectedVersion[] = [];
  props.selectedIds.forEach((id, index) => {
    const version = props.versions.find((item) => item.id === id);
    if (!version) return;
    selected.push({
      id: version.id,
      name: version.name,
      color: VERSION_COLORS[index % VERSION_COLORS.length] ?? '#409eff',
      createTime: version.sys_create_datetime,
    });
  });
  return selected;
});

// 可选版本列表（过滤后的）
const filteredVersions = computed(() => {
  if (!searchKeyword.value) return props.versions;
  const keyword = searchKeyword.value.toLowerCase();
  return props.versions.filter((v) => v.name.toLowerCase().includes(keyword));
});

// 弹窗内的临时选择状态
const tempSelectedIds = ref<string[]>([]);

// 移除已选版本
const handleRemove = (id: string) => {
  emit(
    'update:selectedIds',
    props.selectedIds.filter((i) => i !== id),
  );
};

// 打开弹窗
const handleOpenDialog = () => {
  // 初始化临时选择为当前已选
  tempSelectedIds.value = [...props.selectedIds];
  searchKeyword.value = '';
  showDialog.value = true;
};

// 弹窗内切换选择
const handleToggleSelect = (id: string) => {
  const index = tempSelectedIds.value.indexOf(id);
  if (index === -1) {
    if (tempSelectedIds.value.length >= 6) {
      ElMessage.warning('最多选择 6 个版本');
      return;
    }
    tempSelectedIds.value.push(id);
  } else {
    tempSelectedIds.value.splice(index, 1);
  }
};

// 确认添加
const handleConfirm = () => {
  emit('update:selectedIds', tempSelectedIds.value);
  showDialog.value = false;
};

// 格式化完整时间（带时分秒）
const formatDateTime = (dateStr?: string) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
};

// 格式化时间区间
const formatTimeRange = (startTime?: string, endTime?: string) => {
  if (!startTime) return '';
  const start = formatDateTime(startTime);
  const end = endTime ? formatDateTime(endTime) : '进行中';
  return `${start} ~ ${end}`;
};

// 格式化相对时间区间（从time_ranges）
const formatRelativeTimeRange = (version: PerformanceVersion) => {
  const timeRanges = version.time_ranges;
  if (!timeRanges) return '';

  const ranges: string[] = [];
  for (const range of Object.values(timeRanges)) {
    const start = range.start;
    const end = range.end;
    if (end !== undefined) {
      ranges.push(`相对时间 ${start}-${end}秒`);
    } else {
      ranges.push(`相对时间 ${start}秒起`);
    }
  }
  return ranges.join('；');
};

// Tooltip内容：显示采集时间 + 标记的相对时间区间
const getVersionTooltip = (version: PerformanceVersion) => {
  const parts: string[] = [];

  // 采集时间范围
  const absoluteTime = formatTimeRange(version.start_time, version.end_time);
  if (absoluteTime) {
    parts.push(`采集时间: ${absoluteTime}`);
  }

  // 标记的相对时间区间
  const relativeTime = formatRelativeTimeRange(version);
  if (relativeTime) {
    parts.push(`标记区间: ${relativeTime}`);
  }

  return parts.join('\n') || '无时间信息';
};

// 监听弹窗打开，重置搜索
watch(showDialog, (val) => {
  if (val) {
    searchKeyword.value = '';
  }
});
</script>

<template>
  <div class="version-selector">
    <!-- 已选版本卡片 -->
    <ElTag
      v-for="version in selectedVersions"
      :key="version.id"
      :color="version.color"
      effect="dark"
      class="version-tag"
      closable
      @close="handleRemove(version.id)"
    >
      {{ version.name }}
    </ElTag>

    <!-- 添加按钮（缩小） -->
    <ElButton
      v-if="selectedIds.length < 6"
      size="small"
      class="add-btn"
      @click="handleOpenDialog"
    >
      +添加
    </ElButton>

    <!-- 版本选择弹窗 -->
    <ElDialog
      v-model="showDialog"
      title="选择版本"
      width="500px"
      class="version-select-dialog"
    >
      <!-- 搜索框 -->
      <div class="search-area">
        <ElInput
          v-model="searchKeyword"
          placeholder="搜索版本名称..."
          clearable
          prefix-icon="Search"
        />
      </div>

      <!-- 版本列表 -->
      <div class="version-list">
        <div
          v-for="version in filteredVersions"
          :key="version.id"
          class="version-item"
          :class="{ selected: tempSelectedIds.includes(version.id) }"
          @click="handleToggleSelect(version.id)"
        >
          <ElCheckbox
            :model-value="tempSelectedIds.includes(version.id)"
            @click.stop="handleToggleSelect(version.id)"
          />
          <span class="version-name">{{ version.name }}</span>
          <!-- 悬停tooltip显示标记区间 -->
          <span
            class="version-time-range"
            :title="getVersionTooltip(version)"
          >
            {{ formatTimeRange(version.start_time, version.end_time) }}
          </span>
          <!-- 显示相对时间区间标签 -->
          <span v-if="version.time_ranges" class="relative-time-tag">
            {{ formatRelativeTimeRange(version) }}
          </span>
        </div>

        <!-- 无结果 -->
        <div v-if="filteredVersions.length === 0" class="no-result">
          无匹配版本
        </div>
      </div>

      <!-- 底部计数 -->
      <div class="select-count">
        已选 {{ tempSelectedIds.length }} / 6 个版本
      </div>

      <template #footer>
        <ElButton @click="showDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleConfirm">确定添加</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.version-selector {
  display: flex;
  gap: 8px;
  align-items: center;
  flex: 1;
}

.version-tag {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 6px;
}

.add-btn {
  border: 1px dashed var(--el-color-primary);
  color: var(--el-color-primary);
  background: transparent;
  padding: 4px 8px;
  font-size: 12px;
}

.add-btn:hover {
  background: var(--el-color-primary-light-9);
}

/* 弹窗样式 */
.search-area {
  margin-bottom: 12px;
}

.version-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
}

.version-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.version-item:hover {
  background: #f5f5f5;
}

.version-item.selected {
  background: var(--el-color-primary-light-9);
}

.version-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  flex: 1;
}

.version-time-range {
  font-size: 11px;
  color: #999;
  white-space: nowrap;
  cursor: help;
}

.relative-time-tag {
  font-size: 11px;
  color: #409eff;
  background: #ecf5ff;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  margin-left: 8px;
}

.no-result {
  padding: 20px;
  text-align: center;
  color: #999;
}

.select-count {
  margin-top: 12px;
  font-size: 13px;
  color: #666;
}
</style>
