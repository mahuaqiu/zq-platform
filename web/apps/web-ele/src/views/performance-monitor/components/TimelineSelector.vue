<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { PerformanceCollect, PerformanceVersion } from '#/api/core/performance-monitor';
import { VERSION_COLORS } from '../types';

interface Props {
  collects: PerformanceCollect[];
  versions: PerformanceVersion[];
  currentCollectId?: string;
  selectedWindow?: [Date, Date];
  totalDuration?: number; // 总时间范围（分钟）
  // 新增：实际时间范围
  actualStartTime?: Date; // 实际采集开始时间
  actualEndTime?: Date; // 实际采集结束时间
}

const props = withDefaults(defineProps<Props>(), {
  totalDuration: 60,
});

const emit = defineEmits<{
  (e: 'window-change', range: [Date, Date]): void;
  (e: 'version-click', versionId: string): void;
  (e: 'collect-click', collectId: string): void;
}>();

const timelineRef = ref<HTMLDivElement>();
const isDragging = ref(false);
const dragType = ref<'window' | 'left' | 'right'>('window');
const windowStart = ref(0); // 左侧位置百分比（默认从0开始显示全部数据）
const windowWidth = ref(1); // 窗口宽度百分比（默认100%）

// 计算时间范围基准 - 基于当前查看的采集
const timeRange = computed(() => {
  // 优先使用传入的实际时间范围（当前采集数据的实际时间）
  if (props.actualStartTime && props.actualEndTime) {
    return {
      start: props.actualStartTime.getTime(),
      end: props.actualEndTime.getTime(),
    };
  }

  // 如果有当前采集ID，找对应的采集记录时间
  if (props.currentCollectId) {
    const currentCollect = props.collects.find(c => c.id === props.currentCollectId);
    if (currentCollect?.start_time) {
      const startTime = new Date(currentCollect.start_time).getTime();
      const endTime = currentCollect.end_time
        ? new Date(currentCollect.end_time).getTime()
        : new Date().getTime();
      return { start: startTime, end: endTime };
    }
  }

  // 如果没有正在采集，使用最近一个采集的时间范围
  if (props.collects.length > 0) {
    const latestCollect = props.collects[0];
    if (latestCollect?.start_time) {
      const startTime = new Date(latestCollect.start_time).getTime();
      const endTime = latestCollect.end_time
        ? new Date(latestCollect.end_time).getTime()
        : new Date().getTime();
      return { start: startTime, end: endTime };
    }
  }

  // 最后使用默认范围（5分钟）
  const now = new Date();
  const totalMs = 5 * 60 * 1000;
  return {
    start: now.getTime() - totalMs,
    end: now.getTime(),
  };
});

// 时间刻度 - 基于实际时间范围
const timeLabels = computed(() => {
  const labels: string[] = [];
  const totalMs = timeRange.value.end - timeRange.value.start;
  for (let i = 0; i <= 5; i++) {
    const time = new Date(timeRange.value.start + i * totalMs / 5);
    labels.push(
      time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    );
  }
  return labels;
});

// 版本标记点位置 - 基于实际时间范围
const versionMarkers = computed(() => {
  return props.versions.map((v, i) => {
    // 根据版本的采集时间计算位置
    const collect = props.collects.find((c) =>
      v.collect_ids.includes(c.id),
    );
    if (!collect?.start_time) return null;

    const startTime = new Date(collect.start_time).getTime();
    const totalMs = timeRange.value.end - timeRange.value.start;
    const position = (startTime - timeRange.value.start) / totalMs;

    return {
      id: v.id,
      name: v.name,
      position: Math.max(0, Math.min(1, position)),
      color: VERSION_COLORS[i % VERSION_COLORS.length],
    };
  }).filter(Boolean);
});

// 采集标记点位置 - 基于实际时间范围
const collectMarkers = computed(() => {
  return props.collects.map((c) => {
    // 已在版本中的采集不显示
    const inVersion = props.versions.some((v) => v.collect_ids.includes(c.id));
    if (inVersion) return null;

    const startTime = new Date(c.start_time).getTime();
    const totalMs = timeRange.value.end - timeRange.value.start;
    const position = (startTime - timeRange.value.start) / totalMs;

    return {
      id: c.id,
      name: c.name,
      position: Math.max(0, Math.min(1, position)),
      color: '#909399',
    };
  }).filter(Boolean);
});

// 当前采集位置
const currentMarker = computed(() => {
  if (!props.currentCollectId) return null;
  // 当前采集显示在最右侧
  return {
    id: props.currentCollectId,
    position: 1,
    color: '#67c23a',
    isCurrent: true,
  };
});

function handleMouseDown(e: MouseEvent, type: 'window' | 'left' | 'right') {
  e.preventDefault();
  isDragging.value = true;
  dragType.value = type;
}

function handleMouseMove(e: MouseEvent) {
  if (!isDragging.value || !timelineRef.value) return;

  const rect = timelineRef.value.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width;

  if (dragType.value === 'window') {
    // 移动窗口
    const newStart = Math.max(0, Math.min(1 - windowWidth.value, x - windowWidth.value / 2));
    windowStart.value = newStart;
  } else if (dragType.value === 'left') {
    // 调整左侧
    const newStart = Math.max(0, Math.min(windowStart.value + windowWidth.value - 0.1, x));
    windowWidth.value = windowStart.value + windowWidth.value - newStart;
    windowStart.value = newStart;
  } else if (dragType.value === 'right') {
    // 调整右侧
    const newWidth = Math.max(0.1, Math.min(1 - windowStart.value, x - windowStart.value));
    windowWidth.value = newWidth;
  }

  // 触发事件
  emitWindowChange();
}

function handleMouseUp() {
  isDragging.value = false;
}

function emitWindowChange() {
  const totalMs = timeRange.value.end - timeRange.value.start;
  const startDate = new Date(timeRange.value.start + windowStart.value * totalMs);
  const endDate = new Date(timeRange.value.start + (windowStart.value + windowWidth.value) * totalMs);

  emit('window-change', [startDate, endDate]);
}

function handleVersionClick(versionId: string) {
  emit('version-click', versionId);
}

function handleCollectClick(collectId: string) {
  emit('collect-click', collectId);
}

onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
});

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
});
</script>

<template>
  <div class="timeline-selector">
    <!-- 时间轴主体 -->
    <div ref="timelineRef" class="timeline-track">
      <!-- 可选择窗口区域 -->
      <div
        class="time-window"
        :style="{
          left: `${windowStart * 100}%`,
          width: `${windowWidth * 100}%`,
        }"
        @mousedown="handleMouseDown($event, 'window')"
      >
        <!-- 左侧调整手柄 -->
        <div
          class="window-handle left"
          @mousedown.stop="handleMouseDown($event, 'left')"
        ></div>
        <!-- 右侧调整手柄 -->
        <div
          class="window-handle right"
          @mousedown.stop="handleMouseDown($event, 'right')"
        ></div>
      </div>

      <!-- 版本标记点 -->
      <div
        v-for="marker in versionMarkers"
        :key="marker!.id"
        class="marker version-marker"
        :style="{ left: `${marker!.position * 100}%`, background: marker!.color }"
        :title="marker!.name"
        @click="handleVersionClick(marker!.id)"
      ></div>

      <!-- 采集标记点 -->
      <div
        v-for="marker in collectMarkers"
        :key="marker!.id"
        class="marker collect-marker"
        :style="{ left: `${marker!.position * 100}%` }"
        :title="marker!.name"
        @click="handleCollectClick(marker!.id)"
      ></div>

      <!-- 当前采集点 -->
      <div
        v-if="currentMarker"
        class="marker current-marker"
        :style="{ left: `${currentMarker.position * 100}%`, background: currentMarker.color }"
      ></div>

      <!-- 时间刻度（在底部） -->
      <div class="time-labels">
        <span v-for="(label, i) in timeLabels" :key="i" class="time-label">
          {{ label }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-selector {
  flex: 1;
}
.timeline-track {
  position: relative;
  height: 40px;
  background: #f0f0f0;
  border-radius: 4px;
  cursor: pointer;
}
.time-window {
  position: absolute;
  top: 5px;
  height: 10px;
  background: rgba(64, 158, 255, 0.3);
  border: 2px solid #409eff;
  border-radius: 2px;
  cursor: move;
}
.window-handle {
  position: absolute;
  top: 0;
  width: 8px;
  height: 100%;
  background: #409eff;
  cursor: ew-resize;
  border-radius: 2px;
}
.window-handle.left {
  left: -4px;
}
.window-handle.right {
  right: -4px;
}
.marker {
  position: absolute;
  top: 2px;
  border-radius: 50%;
  border: 1px solid #fff;
  cursor: pointer;
  transition: transform 0.2s;
}
.marker:hover {
  transform: scale(1.2);
}
.version-marker {
  width: 8px;
  height: 8px;
}
.collect-marker {
  width: 8px;
  height: 8px;
  background: #909399;
}
.current-marker {
  width: 8px;
  height: 8px;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.time-labels {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 20px;
  display: flex;
  justify-content: space-between;
  padding: 0 10px;
}
.time-label {
  font-size: 10px;
  color: #999;
}
</style>