<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue';
import * as echarts from 'echarts';
import { ElDialog, ElInput, ElButton, ElColorPicker, ElDatePicker, ElMessage, ElMessageBox, ElTooltip } from 'element-plus';
import { createMarker, deleteMarker } from '#/api/core/performance-monitor';
import type { MarkerResponse } from '#/api/core/performance-monitor';

interface Props {
  duration: number; // 总时长（秒）
  startTime?: number; // 选中的开始时间（相对于采集开始的偏移秒数）
  endTime?: number; // 选中的结束时间（相对于采集开始的偏移秒数）
  collectionStartTime?: Date | number | string; // 采集开始时间戳
  previewData?: number[]; // 数据预览（可选，显示在导航条背景）
  collectId?: string; // 采集ID（用于标记操作）
  markers?: MarkerResponse[]; // 标记列表
}

const props = withDefaults(defineProps<Props>(), {
  startTime: 0,
  endTime: 0,
  collectionStartTime: () => new Date(),
  previewData: () => [],
  markers: () => [],
});

const emit = defineEmits<{
  (e: 'rangeChange', range: [number, number]): void;
  (e: 'refreshMarkers'): void;
}>();

// 快速选择按钮配置 - 15分钟、60分钟、12小时
const quickButtons = [
  { label: '15分钟', value: 15 * 60 },
  { label: '60分钟', value: 60 * 60 },
  { label: '12小时', value: 12 * 3600 },
];

// 根据范围计算初始激活按钮（允许±10秒的误差）
function getActiveButtonFromRange(start: number, end: number, duration: number): number {
  if (duration <= 0) return -1;
  const range = end - start;
  const tolerance = 10; // 允许10秒误差

  // 判断是否是从末尾开始的范围
  const isEndRange = Math.abs(end - duration) <= tolerance;

  if (isEndRange && Math.abs(range - 15 * 60) <= tolerance) return 15 * 60;
  if (isEndRange && Math.abs(range - 60 * 60) <= tolerance) return 60 * 60;
  if (isEndRange && Math.abs(range - 12 * 3600) <= tolerance) return 12 * 3600;
  return -1;
}

const activeButton = ref(getActiveButtonFromRange(props.startTime, props.endTime, props.duration));
const chartRef = ref<HTMLDivElement>();
const trackRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

// 当前选中的时间（秒）
const currentStartTime = ref(props.startTime);
const currentEndTime = ref(props.endTime);

// 标记相关
const showAddDialog = ref(false);
const newMarker = ref({
  name: '',
  start_time: null as Date | null,  // 绝对时间
  end_time: null as Date | null,    // 绝对时间
  color: '#409eff',
  note: '',
});

// 计算采集时间范围（用于限制日期选择）
const collectionTimeRange = computed(() => {
  const baseTime = new Date(props.collectionStartTime);
  const endTime = new Date(baseTime.getTime() + props.duration * 1000);
  return { start: baseTime, end: endTime };
});

// 禁用不在采集时间范围内的日期
function getDisabledDate(date: Date): boolean {
  const { start, end } = collectionTimeRange.value;
  return date < start || date > end;
}

// 过滤有效标记
const validMarkers = computed(() => {
  if (!props.markers || !Array.isArray(props.markers)) return [];
  return props.markers.filter((m) => m.name && m.name.trim() !== '');
});

// 格式化时间戳为 YYYY-MM-DD HH:MM:SS 或 HH:MM:SS
function formatTime(offsetSeconds: number, short: boolean = false): string {
  const baseTime = new Date(props.collectionStartTime);
  const time = new Date(baseTime.getTime() + offsetSeconds * 1000);
  const year = time.getFullYear();
  const month = String(time.getMonth() + 1).padStart(2, '0');
  const day = String(time.getDate()).padStart(2, '0');
  const hour = String(time.getHours()).padStart(2, '0');
  const minute = String(time.getMinutes()).padStart(2, '0');
  const second = String(time.getSeconds()).padStart(2, '0');
  if (short) {
    return `${hour}:${minute}:${second}`;
  }
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

// 格式化时间范围（结束时间只显示时分秒）
function formatTimeRange(): string {
  const startTimeStr = formatTime(currentStartTime.value);
  const endTimeStr = formatTime(currentEndTime.value, true);
  return `${startTimeStr} ~ ${endTimeStr}`;
}

// 格式化标记的时间区间tooltip
function getMarkerTooltip(marker: MarkerResponse): string {
  const startTimeStr = formatTime(marker.start_time);
  const endTimeStr = marker.end_time ? formatTime(marker.end_time, true) : '未结束';
  const duration = marker.end_time
    ? `${marker.end_time - marker.start_time}秒`
    : '未结束';
  const note = marker.note ? `\n备注: ${marker.note}` : '';
  return `${startTimeStr}~${endTimeStr}\n时长: ${duration}${note}`;
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

// 快速选择
function handleQuickSelect(value: number) {
  activeButton.value = value;
  currentStartTime.value = Math.max(0, props.duration - value);
  currentEndTime.value = props.duration;
  emit('rangeChange', [currentStartTime.value, props.duration]);
  if (chartInstance) {
    chartInstance.setOption({
      dataZoom: [{
        start: getStartPercent(),
        end: getEndPercent(),
      }],
    });
  }
}

// 相对时间转换为绝对时间
function relativeToAbsolute(relativeSeconds: number): Date {
  const baseTime = new Date(props.collectionStartTime);
  return new Date(baseTime.getTime() + relativeSeconds * 1000);
}

// 绝对时间转换为相对时间（秒）
function absoluteToRelative(absoluteTime: Date): number {
  const baseTime = new Date(props.collectionStartTime);
  return Math.round((absoluteTime.getTime() - baseTime.getTime()) / 1000);
}

// 添加标记
function handleOpenAddMarker() {
  const startAbsolute = relativeToAbsolute(currentStartTime.value);
  const endAbsolute = relativeToAbsolute(currentEndTime.value);

  newMarker.value = {
    name: '',
    start_time: startAbsolute,
    end_time: endAbsolute,
    color: '#409eff',
    note: '',
  };
  showAddDialog.value = true;
}

async function handleAddMarker() {
  if (!newMarker.value.name) {
    ElMessage.warning('请输入标记名称');
    return;
  }
  if (!props.collectId || !newMarker.value.start_time) {
    return;
  }
  // 将绝对时间转换为相对时间（秒）
  const startRelative = absoluteToRelative(newMarker.value.start_time);
  const endRelative = newMarker.value.end_time ? absoluteToRelative(newMarker.value.end_time) : undefined;

  await createMarker({
    collect_id: props.collectId,
    name: newMarker.value.name,
    start_time: startRelative,
    end_time: endRelative,
    color: newMarker.value.color,
    note: newMarker.value.note || undefined,
  });
  ElMessage.success('标记添加成功');
  showAddDialog.value = false;
  emit('refreshMarkers');
}

async function handleDeleteMarker(markerId: string, markerName: string) {
  try {
    await ElMessageBox.confirm(
      `确定要删除标记"${markerName}"吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    await deleteMarker(markerId);
    ElMessage.success('标记删除成功');
    emit('refreshMarkers');
  } catch {
    // 用户点击取消，不做任何操作
  }
}

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);

  chartInstance.on('datazoom', (params: any) => {
    activeButton.value = -1;
    const startPercent = params.start;
    const endPercent = params.end;
    const start = Math.round((startPercent / 100) * props.duration);
    const end = Math.round((endPercent / 100) * props.duration);
    currentStartTime.value = start;
    currentEndTime.value = end;
    emit('rangeChange', [start, end]);
  });

  updateChart();
}

function updateChart() {
  if (!chartInstance) return;

  const xAxisData: number[] = [];
  for (let i = 0; i <= props.duration; i += Math.max(1, Math.floor(props.duration / 100))) {
    xAxisData.push(i);
  }

  let previewData = props.previewData;
  if (previewData.length === 0) {
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
        height: 18,
        bottom: 2,
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
        textStyle: { show: false },
        brushSelect: false,
        zoomLock: false,
      },
    ],
  };

  chartInstance.setOption(option);
}

// 监听所有 props 变化，立即更新按钮状态
watch(
  () => [props.startTime, props.endTime, props.duration] as const,
  ([start, end, duration]) => {
    currentStartTime.value = start;
    currentEndTime.value = end;
    activeButton.value = getActiveButtonFromRange(start, end, duration);
    updateChart();
  },
  { immediate: true }
);

watch(() => props.startTime, (v) => {
  currentStartTime.value = v;
  // 更新按钮激活状态
  activeButton.value = getActiveButtonFromRange(v, props.endTime, props.duration);
  if (chartInstance) {
    chartInstance.setOption({
      dataZoom: [{ start: getStartPercent() }],
    });
  }
});

watch(() => props.endTime, (v) => {
  currentEndTime.value = v;
  // 更新按钮激活状态
  activeButton.value = getActiveButtonFromRange(props.startTime, v, props.duration);
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
      <!-- 左侧：时间显示 -->
      <div class="time-display">
        <span class="time-range">{{ formatTimeRange() }}</span>
      </div>

      <!-- 中间左侧：ECharts 导航条 -->
      <div class="navigator-wrapper">
        <div ref="trackRef" class="navigator-track">
          <div ref="chartRef" class="chart-container"></div>
        </div>
      </div>

      <!-- 中间右侧：快速选择按钮 -->
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

      <!-- 右侧：标记区域 -->
      <div v-if="collectId" class="marker-area">
        <ElTooltip
          v-for="marker in validMarkers"
          :key="marker.id"
          :content="getMarkerTooltip(marker)"
          placement="top"
          effect="dark"
        >
          <span
            class="marker-tag"
            :style="{
              borderColor: marker.color,
              color: marker.color,
              background: marker.color + '15',
            }"
          >
            {{ marker.name }}
            <button class="marker-delete" @click.stop="handleDeleteMarker(marker.id, marker.name)">×</button>
          </span>
        </ElTooltip>
        <button class="add-marker-btn" @click="handleOpenAddMarker">+标记</button>
      </div>
    </div>

    <!-- 添加标记弹窗 -->
    <ElDialog v-model="showAddDialog" title="添加标记" width="400px">
      <div class="form-item">
        <label>标记名称</label>
        <ElInput v-model="newMarker.name" placeholder="如：发起共享" />
      </div>
      <div class="form-item">
        <label>开始时间</label>
        <ElDatePicker
          v-model="newMarker.start_time"
          type="datetime"
          placeholder="选择开始时间"
          format="YYYY-MM-DD HH:mm:ss"
          :disabled-date="getDisabledDate"
          style="width: 100%"
        />
      </div>
      <div class="form-item">
        <label>结束时间</label>
        <ElDatePicker
          v-model="newMarker.end_time"
          type="datetime"
          placeholder="选择结束时间（可选）"
          format="YYYY-MM-DD HH:mm:ss"
          :disabled-date="getDisabledDate"
          style="width: 100%"
        />
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
.time-navigator {
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
}

.navigator-container {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 28px;
}

/* 左侧时间显示 */
.time-display {
  display: flex;
  flex-shrink: 0;
  align-items: center;
}

.time-range {
  font-size: 11px;
  font-weight: 500;
  color: #409eff;
  white-space: nowrap;
}

/* 导航条容器 */
.navigator-wrapper {
  display: flex;
  flex: 0 0 30%;
  min-width: 150px;
}

.navigator-track {
  position: relative;
  width: 100%;
  height: 20px;
}

.chart-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  width: 100%;
  height: 20px;
}

/* 快速选择按钮样式 */
.quick-buttons {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
}

.quick-btn {
  padding: 3px 10px;
  font-size: 12px;
  color: #666;
  white-space: nowrap;
  cursor: pointer;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 3px;
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

/* 右侧标记区域 */
.marker-area {
  display: flex;
  flex: 1;
  gap: 6px;
  align-items: center;
  margin-left: auto;
  min-width: 100px;
}

.marker-tag {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  border: 1px solid;
  display: flex;
  align-items: center;
  gap: 4px;
}

.marker-delete {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
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
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
}

.add-marker-btn:hover {
  background: #409eff;
  color: white;
}

/* 弹窗表单 */
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