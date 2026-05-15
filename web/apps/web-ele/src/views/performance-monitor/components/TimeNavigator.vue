<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

interface Props {
  duration: number; // 总时长（秒）
  startTime?: number; // 选中的开始时间（相对于采集开始的偏移秒数）
  endTime?: number; // 选中的结束时间（相对于采集开始的偏移秒数）
  collectionStartTime?: Date | number | string; // 采集开始时间戳
}

const props = withDefaults(defineProps<Props>(), {
  startTime: 0,
  endTime: 0,
  collectionStartTime: () => new Date(),
});

const emit = defineEmits<{
  (e: 'rangeChange', range: [number, number]): void;
}>();

// 快速选择按钮配置
const quickButtons = [
  { label: '全部', value: 0 },
  { label: '5分钟', value: 5 * 60 },
  { label: '30分钟', value: 30 * 60 },
  { label: '60分钟', value: 60 * 60 },
];

const activeButton = ref(0);
const navigatorRef = ref<HTMLDivElement>();
const isDraggingLeft = ref(false);
const isDraggingRight = ref(false);
const isDraggingRange = ref(false); // 拖拽整个选区
const localStartTime = ref(props.startTime);
const localEndTime = ref(props.endTime);
const dragStartX = ref(0);
const dragStartLeft = ref(0);
const dragStartRight = ref(0);

// 计算选中区间宽度百分比
const rangePercent = computed(() => {
  return ((localEndTime.value - localStartTime.value) / props.duration) * 100;
});

// 是否使用合并显示模式（把手距离 < 10%）
const isMergedMode = computed(() => {
  return rangePercent.value < 10;
});

// 格式化时间戳为 YYYY-MM-DD HH:MM:SS
function formatTime(offsetSeconds: number): string {
  const baseTime = new Date(props.collectionStartTime);
  const time = new Date(baseTime.getTime() + offsetSeconds * 1000);
  const year = time.getFullYear();
  const month = String(time.getMonth() + 1).padStart(2, '0');
  const day = String(time.getDate()).padStart(2, '0');
  const hour = String(time.getHours()).padStart(2, '0');
  const minute = String(time.getMinutes()).padStart(2, '0');
  const second = String(time.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

// 格式化合并时间范围
function formatMergedTime(): string {
  const start = formatTime(localStartTime.value);
  const end = new Date(
    new Date(props.collectionStartTime).getTime() + localEndTime.value * 1000,
  );
  const hour = String(end.getHours()).padStart(2, '0');
  const minute = String(end.getMinutes()).padStart(2, '0');
  const second = String(end.getSeconds()).padStart(2, '0');
  return `${start} ~ ${hour}:${minute}:${second}`;
}

// 计算选中区间位置（百分比）
const leftPercent = computed(
  () => (localStartTime.value / props.duration) * 100,
);
const rightPercent = computed(
  () => (localEndTime.value / props.duration) * 100,
);

// 快速选择
function handleQuickSelect(value: number) {
  activeButton.value = value;
  if (value === 0) {
    // 全部
    localStartTime.value = 0;
    localEndTime.value = props.duration;
  } else {
    // 最近N秒
    localEndTime.value = props.duration;
    localStartTime.value = Math.max(0, props.duration - value);
  }
  emit('rangeChange', [localStartTime.value, localEndTime.value]);
}

// 拖拽处理
function handleMouseDown(e: MouseEvent, side: 'left' | 'range' | 'right') {
  e.preventDefault();
  if (side === 'left') {
    isDraggingLeft.value = true;
  } else if (side === 'right') {
    isDraggingRight.value = true;
  } else {
    isDraggingRange.value = true;
    dragStartX.value = e.clientX;
    dragStartLeft.value = localStartTime.value;
    dragStartRight.value = localEndTime.value;
  }
}

function handleMouseMove(e: MouseEvent) {
  if (!navigatorRef.value) return;
  if (
    !isDraggingLeft.value &&
    !isDraggingRight.value &&
    !isDraggingRange.value
  ) {
    return;
  }

  const rect = navigatorRef.value.getBoundingClientRect();
  const trackWidth = rect.width;
  const x = e.clientX - rect.left;
  const percent = Math.max(0, Math.min(100, (x / trackWidth) * 100));
  const time = Math.round((percent / 100) * props.duration);

  // 严格边界保护：确保时间值在有效范围内
  const minTime = 0;
  const maxTime = props.duration;
  const minGap = 5; // 最小间隔（秒）

  if (isDraggingLeft.value) {
    // 左边界：不能小于0，不能超过endTime-5
    const maxAllowed = Math.max(minTime, localEndTime.value - minGap);
    localStartTime.value = Math.max(minTime, Math.min(time, maxAllowed));
    activeButton.value = -1; // 取消快速选择
  } else if (isDraggingRight.value) {
    // 右边界：不能超过duration，不能小于startTime+5
    const minAllowed = Math.min(maxTime, localStartTime.value + minGap);
    localEndTime.value = Math.min(maxTime, Math.max(time, minAllowed));
    activeButton.value = -1; // 取消快速选择
  } else if (isDraggingRange.value) {
    // 拖拽整个选区
    const deltaX = e.clientX - dragStartX.value;
    const deltaTime = Math.round((deltaX / trackWidth) * props.duration);
    const rangeWidth = dragStartRight.value - dragStartLeft.value;

    let newStart = dragStartLeft.value + deltaTime;
    let newEnd = dragStartRight.value + deltaTime;

    // 边界保护
    if (newStart < minTime) {
      newStart = minTime;
      newEnd = minTime + rangeWidth;
    }
    if (newEnd > maxTime) {
      newEnd = maxTime;
      newStart = maxTime - rangeWidth;
    }

    localStartTime.value = newStart;
    localEndTime.value = newEnd;
    activeButton.value = -1; // 取消快速选择
  }
}

function handleMouseUp() {
  if (isDraggingLeft.value || isDraggingRight.value || isDraggingRange.value) {
    emit('rangeChange', [localStartTime.value, localEndTime.value]);
    isDraggingLeft.value = false;
    isDraggingRight.value = false;
    isDraggingRange.value = false;
  }
}

// 全局事件监听
onMounted(() => {
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
});

onUnmounted(() => {
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
});

// 同步 props
watch(
  () => props.startTime,
  (v) => (localStartTime.value = v),
);
watch(
  () => props.endTime,
  (v) => (localEndTime.value = v),
);
watch(
  () => props.duration,
  () => {
    // duration 变化时重置到全部
    if (activeButton.value === 0) {
      localStartTime.value = 0;
      localEndTime.value = props.duration;
    }
  },
);
</script>

<template>
  <div class="time-navigator">
    <div class="navigator-container">
      <!-- 左侧快速选择按钮 -->
      <div class="quick-buttons">
        <button
          v-for="btn in quickButtons"
          :key="btn.value"
          class="quick-btn"
          :class="{ active: activeButton === btn.value }"
          @click="handleQuickSelect(btn.value)"
        >
          {{ btn.label }}
        </button>
      </div>

      <!-- 右侧导航条 -->
      <div class="navigator-wrapper">
        <!-- 合并模式：顶部时间范围标签 -->
        <div v-if="isMergedMode" class="merged-time-label">
          {{ formatMergedTime() }}
        </div>

        <div
          ref="navigatorRef"
          class="navigator-track"
          :class="{ 'merged-mode': isMergedMode }"
        >
          <!-- 背景轨道 -->
          <div class="track-background"></div>

          <!-- 选中区间 -->
          <div
            class="selected-range"
            :style="{
              left: `${leftPercent}%`,
              width: `${rightPercent - leftPercent}%`,
            }"
            @mousedown="handleMouseDown($event, 'range')"
          >
            <!-- 左把手 -->
            <div
              class="handle left"
              @mousedown.stop="handleMouseDown($event, 'left')"
            >
              <div class="handle-inner"></div>
            </div>
            <!-- 右把手 -->
            <div
              class="handle right"
              @mousedown.stop="handleMouseDown($event, 'right')"
            >
              <div class="handle-inner"></div>
            </div>
          </div>

          <!-- 分开模式：把手上方的时间标签 -->
          <template v-if="!isMergedMode">
            <div
              class="time-tag time-tag-left"
              :style="{ left: `${leftPercent}%` }"
            >
              {{ formatTime(localStartTime) }}
            </div>
            <div
              class="time-tag time-tag-right"
              :style="{ left: `${rightPercent}%` }"
            >
              {{ formatTime(localEndTime) }}
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-navigator {
  padding: 15px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 12px;
}

.navigator-container {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

/* 快速选择按钮样式 */
.quick-buttons {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 8px;
}

.quick-btn {
  padding: 8px 16px;
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
  cursor: pointer;
  background: white;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  transition: all 0.2s;
}

.quick-btn:hover {
  color: #409eff;
  background-color: #ecf5ff;
  border-color: #c6e2ff;
}

.quick-btn.active {
  color: white;
  background: #409eff;
  border-color: #409eff;
}

/* 导航条容器 */
.navigator-wrapper {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

/* 合并时间标签 */
.merged-time-label {
  align-self: flex-start;
  padding: 2px 8px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #303133;
  background: white;
  border-radius: 3px;
  box-shadow: 0 1px 4px rgb(0 0 0 / 10%);
}

/* 导航条轨道 */
.navigator-track {
  position: relative;
  height: 30px;
  cursor: default;
}

.navigator-track.merged-mode {
  height: 30px;
}

/* 背景轨道 */
.track-background {
  position: absolute;
  top: 50%;
  right: 0;
  left: 0;
  height: 6px;
  background: #e8e8e8;
  border-radius: 3px;
  transform: translateY(-50%);
}

/* 选中区间 */
.selected-range {
  position: absolute;
  top: 50%;
  height: 6px;
  cursor: move;
  background: #409eff;
  border-radius: 3px;
  transform: translateY(-50%);
}

/* 把手 */
.handle {
  position: absolute;
  top: 50%;
  width: 14px;
  height: 16px;
  cursor: ew-resize;
  background: white;
  border: 2px solid #409eff;
  border-radius: 4px;
  transform: translateY(-50%);
}

.handle.left {
  left: -7px;
}

.handle.right {
  right: -7px;
}

.handle-inner {
  width: 4px;
  height: 8px;
  margin: 3px auto 0;
  background: #409eff;
  border-radius: 2px;
}

/* 时间标签（分开模式） */
.time-tag {
  position: absolute;
  top: -20px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 500;
  color: white;
  white-space: nowrap;
  background: #409eff;
  border-radius: 3px;
  transform: translateX(-50%);
}

.time-tag-left {
  left: 0;
}

.time-tag-right {
  left: 100%;
}
</style>
