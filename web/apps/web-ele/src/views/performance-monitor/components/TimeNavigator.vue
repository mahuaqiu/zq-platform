<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';

interface Props {
  duration: number; // 总时长（秒）
  startTime?: number; // 选中的开始时间
  endTime?: number; // 选中的结束时间
}

const props = withDefaults(defineProps<Props>(), {
  startTime: 0,
  endTime: 0,
});

const emit = defineEmits<{
  (e: 'range-change', range: [number, number]): void;
}>();

const navigatorRef = ref<HTMLDivElement>();
const isDraggingLeft = ref(false);
const isDraggingRight = ref(false);
const localStartTime = ref(props.startTime);
const localEndTime = ref(props.endTime);

// 时间刻度（7个刻度点）
const timeLabels = computed(() => {
  const step = Math.ceil(props.duration / 6);
  return Array.from({ length: 7 }, (_, i) => i * step);
});

// 计算选中区间位置（百分比）
const leftPercent = computed(() => (localStartTime.value / props.duration) * 100);
const rightPercent = computed(() => (localEndTime.value / props.duration) * 100);

// 拖拽处理
function handleMouseDown(e: MouseEvent, side: 'left' | 'right') {
  e.preventDefault();
  if (side === 'left') {
    isDraggingLeft.value = true;
  } else {
    isDraggingRight.value = true;
  }
}

function handleMouseMove(e: MouseEvent) {
  if (!navigatorRef.value) return;
  if (!isDraggingLeft.value && !isDraggingRight.value) return;

  const rect = navigatorRef.value.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
  const time = Math.round((percent / 100) * props.duration);

  // 严格边界保护：确保时间值在有效范围内
  const minTime = 0;
  const maxTime = props.duration;
  const minGap = 5; // 最小间隔

  if (isDraggingLeft.value) {
    // 左边界：不能小于0，不能超过endTime-5
    const maxAllowed = Math.max(minTime, localEndTime.value - minGap);
    localStartTime.value = Math.max(minTime, Math.min(time, maxAllowed));
  } else if (isDraggingRight.value) {
    // 右边界：不能超过duration，不能小于startTime+5
    const minAllowed = Math.min(maxTime, localStartTime.value + minGap);
    localEndTime.value = Math.min(maxTime, Math.max(time, minAllowed));
  }
}

function handleMouseUp() {
  if (isDraggingLeft.value || isDraggingRight.value) {
    emit('range-change', [localStartTime.value, localEndTime.value]);
    isDraggingLeft.value = false;
    isDraggingRight.value = false;
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
watch(() => props.startTime, (v) => localStartTime.value = v);
watch(() => props.endTime, (v) => localEndTime.value = v);
</script>

<template>
  <div class="time-navigator">
    <div class="navigator-header">
      <span class="navigator-title">时间导航</span>
      <span class="navigator-duration">采集时长: {{ duration }}s</span>
    </div>
    <div ref="navigatorRef" class="navigator-track">
      <!-- 时间刻度 -->
      <div class="time-labels">
        <span v-for="t in timeLabels" :key="t" class="time-label">{{ t }}s</span>
      </div>
      <!-- 背景轨道 -->
      <div class="track-background"></div>
      <!-- 选中区间 -->
      <div class="selected-range" :style="{ left: leftPercent + '%', width: (rightPercent - leftPercent) + '%' }">
        <!-- 左手柄 -->
        <div class="handle left" @mousedown="handleMouseDown($event, 'left')">
          <div class="handle-inner"></div>
        </div>
        <!-- 右手柄 -->
        <div class="handle right" @mousedown="handleMouseDown($event, 'right')">
          <div class="handle-inner"></div>
        </div>
      </div>
      <!-- 时间标签 -->
      <div class="time-tags">
        <span class="time-tag" :style="{ left: leftPercent + '%' }">{{ localStartTime }}s</span>
        <span class="time-tag" :style="{ left: rightPercent + '%' }">{{ localEndTime }}s</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-navigator {
  background: white;
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 15px;
}
.navigator-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.navigator-title {
  font-size: 14px;
  color: #333;
  font-weight: bold;
}
.navigator-duration {
  font-size: 12px;
  color: #666;
}
.navigator-track {
  position: relative;
  height: 50px;
  background: linear-gradient(90deg, #f0f9ff 0%, #fff 50%, #f0f9ff 100%);
  border: 1px solid #ddd;
  border-radius: 8px;
}
.time-labels {
  position: absolute;
  top: 0;
  left: 10px;
  right: 10px;
  height: 15px;
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #999;
}
.track-background {
  position: absolute;
  top: 20px;
  left: 10px;
  right: 10px;
  height: 20px;
  background: #f5f5f5;
  border-radius: 4px;
}
.selected-range {
  position: absolute;
  top: 20px;
  height: 20px;
  background: rgba(64, 158, 255, 0.25);
  border-left: 4px solid #409eff;
  border-right: 4px solid #409eff;
  border-radius: 2px;
}
.handle {
  position: absolute;
  top: 2px;
  width: 16px;
  height: 16px;
  background: white;
  border: 2px solid #409eff;
  border-radius: 8px;
  cursor: ew-resize;
}
.handle.left { left: -8px; }
.handle.right { right: -8px; }
.handle-inner {
  width: 6px;
  height: 10px;
  background: #409eff;
  border-radius: 2px;
  margin: 2px auto;
}
.time-tags {
  position: absolute;
  bottom: 0;
  width: 100%;
}
.time-tag {
  position: absolute;
  background: #409eff;
  color: white;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: bold;
}
</style>