<script setup lang="ts">
import { ref, watch } from 'vue';
import { ElDialog, ElInput, ElButton, ElColorPicker } from 'element-plus';
import { createMarker, deleteMarker } from '#/api/core/performance-monitor';
import type { MarkerResponse } from '#/api/core/performance-monitor';

interface Props {
  collectId: string;
  markers: MarkerResponse[];
  clickedTime?: number; // 从图表点击接收的时间点
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

const showAddDialog = ref(false);
const newMarker = ref({
  name: '',
  start_time: 0,
  end_time: 0,
  color: '#409eff',
  note: '',
});

// 监听图表点击时间点，自动填充并打开对话框
watch(
  () => props.clickedTime,
  (time) => {
    if (time !== undefined && time >= 0) {
      newMarker.value.start_time = time;
      newMarker.value.name = ''; // 清空名称让用户输入
      showAddDialog.value = true; // 自动打开对话框
    }
  }
);

async function handleAddMarker() {
  if (!newMarker.value.name || newMarker.value.start_time < 0) {
    return;
  }
  await createMarker({
    collect_id: props.collectId,
    name: newMarker.value.name,
    start_time: newMarker.value.start_time,
    end_time: newMarker.value.end_time || undefined,
    color: newMarker.value.color,
    note: newMarker.value.note || undefined,
  });
  showAddDialog.value = false;
  resetForm();
  emit('refresh');
}

async function handleDeleteMarker(markerId: string) {
  await deleteMarker(markerId);
  emit('refresh');
}

function resetForm() {
  newMarker.value = {
    name: '',
    start_time: 0,
    end_time: 0,
    color: '#409eff',
    note: '',
  };
}
</script>

<template>
  <div class="marker-manager">
    <span class="marker-label">标记：</span>
    <span
      v-for="marker in markers"
      :key="marker.id"
      class="marker-tag"
      :style="{ borderColor: marker.color, color: marker.color, background: marker.color + '15' }"
    >
      {{ marker.name }} ({{ marker.start_time }}s)
      <button class="marker-delete" @click="handleDeleteMarker(marker.id)">×</button>
    </span>
    <button class="add-marker-btn" @click="showAddDialog = true">+ 添加标记</button>

    <ElDialog v-model="showAddDialog" title="添加标记" width="400px">
      <div class="form-item">
        <label>标记名称</label>
        <ElInput v-model="newMarker.name" placeholder="如：发起共享" />
      </div>
      <div class="form-item">
        <label>开始时间（秒）</label>
        <ElInput v-model.number="newMarker.start_time" type="number" placeholder="0" />
      </div>
      <div class="form-item">
        <label>结束时间（秒）</label>
        <ElInput v-model.number="newMarker.end_time" type="number" placeholder="可选" />
      </div>
      <div class="form-item">
        <label>颜色</label>
        <ElColorPicker v-model="newMarker.color" />
      </div>
      <div class="form-item">
        <label>备注</label>
        <ElInput v-model="newMarker.note" placeholder="可选" />
      </div>
      <template #footer>
        <ElButton @click="showAddDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleAddMarker">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.marker-manager {
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 12px 15px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.marker-label {
  font-size: 13px;
  color: #333;
  font-weight: bold;
}
.marker-tag {
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid;
  display: flex;
  align-items: center;
  gap: 5px;
}
.marker-delete {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
  opacity: 0.6;
}
.marker-delete:hover {
  opacity: 1;
}
.add-marker-btn {
  background: white;
  border: 1px solid #409eff;
  color: #409eff;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.add-marker-btn:hover {
  background: #409eff;
  color: white;
}
.form-item {
  margin-bottom: 15px;
}
.form-item label {
  display: block;
  margin-bottom: 5px;
  font-size: 13px;
  color: #666;
}
</style>