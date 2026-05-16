<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import * as echarts from 'echarts';

interface Props {
  duration: number; // 总时长（秒）
  startTime?: number; // 选中的开始时间（相对于采集开始的偏移秒数）
  endTime?: number; // 选中的结束时间（相对于采集开始的偏移秒数）
  collectionStartTime?: Date | number | string; // 采集开始时间戳
  previewData?: number[]; // 数据预览（可选，显示在导航条背景）
}

const props = withDefaults(defineProps<Props>(), {
  startTime: 0,
  endTime: 0,
  collectionStartTime: () => new Date(),
  previewData: () => [],
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

// 根据范围计算初始激活按钮
function getActiveButtonFromRange(start: number, end: number, duration: number): number {
  if (duration <= 0) return 0;
  if (start === 0 && end === duration) return 0;
  const range = end - start;
  if (end === duration && range === 5 * 60) return 5 * 60;
  if (end === duration && range === 30 * 60) return 30 * 60;
  if (end === duration && range === 60 * 60) return 60 * 60;
  return -1;
}

const activeButton = ref(getActiveButtonFromRange(props.startTime, props.endTime, props.duration));
const chartRef = ref<HTMLDivElement>();
const trackRef = ref<HTMLDivElement>(); // 轨道容器引用
let chartInstance: echarts.ECharts | null = null;

// 当前选中的时间（秒）- 用于时间标签显示
const currentStartTime = ref(props.startTime);
const currentEndTime = ref(props.endTime);

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

// 计算时间标签位置百分比
function getStartPercent(): number {
  if (props.duration <= 0) return 0;
  return (currentStartTime.value / props.duration) * 100;
}
function getEndPercent(): number {
  if (props.duration <= 0) return 100;
  return (currentEndTime.value / props.duration) * 100;
}

// 判断是否需要合并显示（距离小于 15%）
const isMergedMode = computed(() => {
  return getEndPercent() - getStartPercent() < 15;
});

// 格式化合并时间范围
function formatMergedTime(): string {
  const start = formatTime(currentStartTime.value);
  const endTime = new Date(
    new Date(props.collectionStartTime).getTime() + currentEndTime.value * 1000,
  );
  const hour = String(endTime.getHours()).padStart(2, '0');
  const minute = String(endTime.getMinutes()).padStart(2, '0');
  const second = String(endTime.getSeconds()).padStart(2, '0');
  return `${start} ~ ${hour}:${minute}:${second}`;
}

// 快速选择
function handleQuickSelect(value: number) {
  activeButton.value = value;
  if (value === 0) {
    currentStartTime.value = 0;
    currentEndTime.value = props.duration;
    emit('rangeChange', [0, props.duration]);
  } else {
    currentStartTime.value = Math.max(0, props.duration - value);
    currentEndTime.value = props.duration;
    emit('rangeChange', [currentStartTime.value, props.duration]);
  }
  // 同步更新图表
  if (chartInstance) {
    chartInstance.setOption({
      dataZoom: [{
        start: getStartPercent(),
        end: getEndPercent(),
      }],
    });
  }
}

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);

  // 监听 dataZoom 事件
  chartInstance.on('datazoom', (params: any) => {
    // 取消快速选择按钮激活状态
    activeButton.value = -1;

    // 获取百分比范围
    const startPercent = params.start;
    const endPercent = params.end;

    // 计算实际时间范围（秒）
    const start = Math.round((startPercent / 100) * props.duration);
    const end = Math.round((endPercent / 100) * props.duration);

    // 更新本地时间显示
    currentStartTime.value = start;
    currentEndTime.value = end;

    emit('rangeChange', [start, end]);
  });

  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  // 生成 X 轴数据（时间刻度）
  const xAxisData: number[] = [];
  for (let i = 0; i <= props.duration; i += Math.max(1, Math.floor(props.duration / 100))) {
    xAxisData.push(i);
  }

  // 生成预览数据（如果没有传入，生成模拟数据）
  let previewData = props.previewData;
  if (previewData.length === 0) {
    // 模拟随机数据用于预览
    previewData = xAxisData.map(() => 30 + Math.random() * 40);
  }

  const option: echarts.EChartsOption = {
    animation: false,
    grid: {
      left: 5,
      right: 5,
      top: 5,
      bottom: 5,
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    series: [
      {
        type: 'line',
        data: previewData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#ccc',
          width: 1,
        },
        areaStyle: {
          color: '#eee',
        },
      },
    ],
    dataZoom: [
      {
        type: 'slider',
        xAxisIndex: 0,
        start: getStartPercent(),
        end: getEndPercent(),
        height: 20,
        bottom: 0,
        borderColor: '#ddd',
        backgroundColor: '#e8e8e8',
        fillerColor: 'rgba(64, 158, 255, 0.15)',
        handleStyle: {
          color: '#fff',
          borderColor: '#409eff',
          borderWidth: 1,
        },
        moveHandleStyle: {
          color: '#409eff',
          opacity: 0.3,
        },
        selectedDataBackground: {
          lineStyle: { color: '#409eff' },
          areaStyle: { color: 'rgba(64, 158, 255, 0.2)' },
        },
        dataBackground: {
          lineStyle: { color: '#ccc' },
          areaStyle: { color: '#eee' },
        },
        textStyle: { show: false }, // 不显示内置的文字
        brushSelect: false,
        zoomLock: false,
      },
    ],
  };

  chartInstance.setOption(option);
}

// 监听 props 变化
watch(() => props.duration, () => {
  currentStartTime.value = props.startTime;
  currentEndTime.value = props.endTime;
  updateChart();
});

watch(() => props.startTime, (v) => {
  currentStartTime.value = v;
  if (chartInstance) {
    chartInstance.setOption({
      dataZoom: [{ start: getStartPercent() }],
    });
  }
});

watch(() => props.endTime, (v) => {
  currentEndTime.value = v;
  if (chartInstance) {
    chartInstance.setOption({
      dataZoom: [{ end: getEndPercent() }],
    });
  }
});

watch(() => props.previewData, updateChart, { deep: true });

onMounted(() => {
  initChart();
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
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

      <!-- 右侧 ECharts 导航条 -->
      <div class="navigator-wrapper">
        <div ref="trackRef" class="navigator-track">
          <!-- 合并模式：居中显示时间范围 -->
          <div v-if="isMergedMode" class="merged-time-label">
            {{ formatMergedTime() }}
          </div>
          <!-- 分开模式：两个时间标签跟随把手 -->
          <template v-else>
            <div
              class="time-tag-left"
              :class="{ 'at-boundary': getStartPercent() < 8 }"
              :style="{ left: getStartPercent() + '%' }"
            >
              {{ formatTime(currentStartTime) }}
            </div>
            <div
              class="time-tag-right"
              :class="{ 'at-boundary': getEndPercent() > 92 }"
              :style="{ left: getEndPercent() + '%' }"
            >
              {{ formatTime(currentEndTime) }}
            </div>
          </template>
          <!-- ECharts 容器 -->
          <div ref="chartRef" class="chart-container"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-navigator {
  padding: 16px;
  background: white;
  border-radius: 8px;
}

.navigator-container {
  display: flex;
  gap: 16px;
  align-items: center;
}

/* 快速选择按钮样式 */
.quick-buttons {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.quick-btn {
  padding: 6px 16px;
  font-size: 13px;
  color: #666;
  white-space: nowrap;
  cursor: pointer;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  transition: all 0.2s;
}

.quick-btn:hover {
  color: #409eff;
  border-color: #409eff;
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
  min-width: 0;
}

.navigator-track {
  position: relative;
  width: 100%;
  height: 42px;
}

/* 合并时间标签 */
.merged-time-label {
  position: absolute;
  top: 0;
  left: 50%;
  padding: 2px 8px;
  font-size: 11px;
  color: #409eff;
  background: #fff;
  border-radius: 3px;
  box-shadow: 0 1px 3px rgb(0 0 0 / 10%);
  transform: translateX(-50%);
  z-index: 10;
  white-space: nowrap;
}

/* 时间标签 - 跟随把手 */
.time-tag-left,
.time-tag-right {
  position: absolute;
  top: 0;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 500;
  color: #409eff;
  white-space: nowrap;
  background: #fff;
  border-radius: 3px;
  transform: translateX(-50%);
  z-index: 10;
}

/* 边界处理：左标签靠近左边界时，左对齐 */
.time-tag-left.at-boundary {
  transform: translateX(0);
  left: 0;
}

/* 边界处理：右标签靠近右边界时，右对齐 */
.time-tag-right.at-boundary {
  transform: translateX(-100%);
}

.chart-container {
  position: absolute;
  top: 22px;
  left: 0;
  right: 0;
  width: 100%;
  height: 20px;
}
</style>