<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElTag, ElButton, ElButtonGroup } from 'element-plus';
import type { CompareTag } from '../types';
import AddTagDialog from './AddTagDialog.vue';

const props = defineProps<{
  timeRange: { start: Date; end: Date };
  tags: CompareTag[];
}>();

const emit = defineEmits<{
  (e: 'timeRangeChange', range: { start: Date; end: Date }): void;
  (e: 'addTag', tag: { name: string; type: 'peak' | 'stable'; start_time: string; end_time: string; note?: string }): void;
  (e: 'removeTag', tagId: string): void;
}>();

const showAddDialog = ref(false);

// Format time range display
const timeRangeText = computed(() => {
  const start = props.timeRange.start;
  const end = props.timeRange.end;
  const formatDate = (d: Date) => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hour = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hour}:${min}`;
  };
  return `${formatDate(start)} ~ ${formatDate(end).split(' ')[1]}`;
});

// Quick buttons
const quickRanges = [
  { label: '15分钟', minutes: 15 },
  { label: '60分钟', minutes: 60 },
  { label: '12小时', minutes: 720 },
];

const handleQuickRange = (minutes: number) => {
  const duration = minutes * 60 * 1000;
  const mid = props.timeRange.start.getTime() + (props.timeRange.end.getTime() - props.timeRange.start.getTime()) / 2;
  emit('timeRangeChange', {
    start: new Date(mid - duration / 2),
    end: new Date(mid + duration / 2),
  });
};

// Add tag
const handleAddTag = (data: { name: string; type: 'peak' | 'stable'; start_time: string; end_time: string; note?: string }) => {
  emit('addTag', data);
  showAddDialog.value = false;
};

// Remove tag
const handleRemoveTag = (tagId: string) => {
  emit('removeTag', tagId);
};
</script>

<template>
  <div class="compare-time-navigator">
    <!-- Time range display -->
    <span class="time-range-text">{{ timeRangeText }}</span>

    <!-- dataZoom placeholder -->
    <div class="datazoom-bar" :style="{ width: '25%' }"></div>

    <!-- Quick buttons -->
    <ElButtonGroup>
      <ElButton
        v-for="range in quickRanges"
        :key="range.minutes"
        size="small"
        @click="handleQuickRange(range.minutes)"
      >
        {{ range.label }}
      </ElButton>
    </ElButtonGroup>

    <!-- Tags -->
    <div class="tag-list">
      <ElTag
        v-for="tag in tags"
        :key="tag.id"
        :type="tag.type === 'peak' ? 'danger' : 'success'"
        effect="plain"
        closable
        @close="handleRemoveTag(tag.id)"
      >
        {{ tag.name }}（{{ tag.type === 'peak' ? '冲高' : '稳态' }}）
      </ElTag>

      <ElButton size="small" type="primary" plain @click="showAddDialog = true">
        +标签
      </ElButton>
    </div>

    <!-- Add tag dialog -->
    <AddTagDialog
      :visible="showAddDialog"
      @update:visible="showAddDialog = $event"
      @submit="handleAddTag"
    />
  </div>
</template>

<style scoped>
.compare-time-navigator {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.time-range-text {
  font-size: 11px;
  color: #409eff;
  font-weight: 500;
  min-width: 140px;
}

.datazoom-bar {
  height: 18px;
  background: #e8e8e8;
  border-radius: 3px;
  min-width: 150px;
}

.tag-list {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-left: auto;
}
</style>