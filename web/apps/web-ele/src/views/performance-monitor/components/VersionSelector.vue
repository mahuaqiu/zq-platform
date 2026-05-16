<script setup lang="ts">
import { computed } from 'vue';
import { ElTag, ElDropdown, ElDropdownMenu, ElDropdownItem, ElButton } from 'element-plus';
import type { PerformanceVersion } from '#/api/core/performance-monitor';
import { VERSION_COLORS } from '../types';

interface SelectedVersion {
  id: string;
  name: string;
  color: string;
}

const props = defineProps<{
  versions: PerformanceVersion[];
  selectedIds: string[];
}>();

const emit = defineEmits<{
  (e: 'update:selectedIds', value: string[]): void;
}>();

// 已选版本列表
const selectedVersions = computed<SelectedVersion[]>(() => {
  return props.selectedIds.map((id, index) => {
    const version = props.versions.find(v => v.id === id);
    if (!version) return null;
    return {
      id: version.id,
      name: version.name,
      color: VERSION_COLORS[index % VERSION_COLORS.length],
    };
  }).filter((v): v is SelectedVersion => v !== null);
});

// 可选版本（未选中的）
const availableVersions = computed(() => {
  return props.versions.filter(v => !props.selectedIds.includes(v.id));
});

// 移除版本
const handleRemove = (id: string) => {
  emit('update:selectedIds', props.selectedIds.filter(i => i !== id));
};

// 添加版本
const handleAdd = (id: string) => {
  if (props.selectedIds.length < 6) {
    emit('update:selectedIds', [...props.selectedIds, id]);
  }
};
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

    <!-- 添加版本按钮 -->
    <ElDropdown
      v-if="selectedIds.length < 6 && availableVersions.length > 0"
      trigger="click"
      @command="handleAdd"
    >
      <ElButton class="add-button" plain>
        + 添加版本
      </ElButton>
      <template #dropdown>
        <ElDropdownMenu>
          <ElDropdownItem
            v-for="version in availableVersions"
            :key="version.id"
            :command="version.id"
          >
            {{ version.name }}
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
  </div>
</template>

<style scoped>
.version-selector {
  display: flex;
  gap: 8px;
  align-items: center;
}

.version-tag {
  padding: 8px 16px;
  font-size: 12px;
}

.add-button {
  border: 2px dashed var(--el-color-primary);
  color: var(--el-color-primary);
}
</style>