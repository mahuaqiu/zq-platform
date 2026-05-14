<script setup lang="ts">
import { ref, watch, computed, onMounted, nextTick } from 'vue';
import type { PerformanceData } from '../types';

interface Top10ItemInternal {
  name: string;
  value: number;
}

const props = defineProps<{
  data: PerformanceData[];
  clickedTime?: number;
  type?: 'cpu' | 'gpu';
}>();

const emit = defineEmits<{
  (e: 'type-change', type: 'cpu' | 'gpu'): void;
}>();

const currentTime = ref<number>(0);
const top1to5 = ref<Top10ItemInternal[]>([]);
const top6to10 = ref<Top10ItemInternal[]>([]);

// TOP前三的渐变色组合（从深到浅）
const gradientPairs = [
  ['#409eff', '#66b1ff'], // TOP1: 蓝色渐变
  ['#67c23a', '#85ce61'], // TOP2: 绿色渐变
  ['#e6a23c', '#ebb563'], // TOP3: 橙色渐变
];

// TOP4-10的纯色
const solidColors = [
  '#f56c6c',  // TOP4: 红色
  '#909399',  // TOP5: 灰色
  '#b37feb',  // TOP6: 紫色
  '#91d5ff',  // TOP7: 浅蓝
  '#ff85c0',  // TOP8: 粉色
  '#87e8de',  // TOP9: 青色
  '#95de64',  // TOP10: 浅绿
];

// 监听点击时刻变化
watch(
  () => props.clickedTime,
  (time) => {
    if (time !== undefined) {
      currentTime.value = time;
      updateTop10Data(time);
    }
  },
  { immediate: true }
);

// 监听数据变化
watch(
  () => props.data,
  (data) => {
    if (data.length > 0 && currentTime.value === 0) {
      // 初始化时使用最新数据
      const lastData = data[data.length - 1];
      if (lastData) {
        currentTime.value = lastData.relative_time;
        updateTop10Data(lastData.relative_time);
      }
    }
  },
  { immediate: true }
);

function updateTop10Data(time: number) {
  // 找到最接近的数据
  const closestData =
    props.data.find((d) => d.relative_time === time) ||
    props.data.reduce(
      (prev, curr) =>
        Math.abs(curr.relative_time - time) < Math.abs(prev.relative_time - time) ? curr : prev,
      props.data[0]
    );

  const top10List = props.type === 'gpu' ? closestData?.top10_gpu : closestData?.top10_cpu;
  const valueKey = props.type === 'gpu' ? 'gpu' : 'cpu';

  if (top10List) {
    const items = top10List.slice(0, 10).map((p) => ({
      name: p.name,
      value: p[valueKey] || 0,
    }));

    top1to5.value = items.slice(0, 5);
    top6to10.value = items.slice(5, 10);
  } else {
    top1to5.value = [];
    top6to10.value = [];
  }
}

// 切换类型
function handleTypeChange(type: 'cpu' | 'gpu') {
  emit('type-change', type);
  updateTop10Data(currentTime.value);
}

// TOP前三的渐变背景
function getGradientStyle(idx: number): string {
  if (idx < 3) {
    return `linear-gradient(90deg, ${gradientPairs[idx][0]}, ${gradientPairs[idx][1]})`;
  }
  return solidColors[idx] || '#909399';
}

// TOP4-10的纯色
function getSolidColor(idx: number): string {
  return solidColors[idx] || '#909399';
}

// 计算进度条宽度（基于最大值）
function getBarWidth(item: Top10ItemInternal, max: number): number {
  if (max <= 0) return 0;
  return Math.round((item.value / max) * 100);
}

// 获取 TOP1-5 的最大值
const top1to5Max = computed(() => {
  const values = top1to5.value.map((item) => item.value);
  return Math.max(...values, 0.01);
});

// 获取 TOP6-10 的最大值
const top6to10Max = computed(() => {
  const values = top6to10.value.map((item) => item.value);
  // 使用TOP1-5的最大值作为参照，保持视觉一致性
  return Math.max(...values, top1to5Max.value);
});
</script>

<template>
  <div class="top10-list">
    <div class="top10-header">
      <h4 class="top10-title">进程 TOP10 排名</h4>
      <div class="top10-controls">
        <span class="time-badge">最新时刻</span>
        <div class="type-switch">
          <button
            :class="['switch-btn', type === 'cpu' ? 'active' : '']"
            @click="handleTypeChange('cpu')"
          >
            CPU TOP10
          </button>
          <button
            :class="['switch-btn', type === 'gpu' ? 'active' : '']"
            @click="handleTypeChange('gpu')"
          >
            GPU TOP10
          </button>
        </div>
      </div>
    </div>

    <!-- 双列布局 -->
    <div class="top10-grid">
      <!-- 左侧 TOP1-5 -->
      <div class="top-column">
        <!-- TOP前三：渐变进度条，百分比在进度条内 -->
        <div v-for="(item, idx) in top1to5.slice(0, 3)" :key="item.name" class="top-item top-3">
          <div class="process-name bold">{{ item.name }}</div>
          <div class="bar-container bar-20">
            <div
              class="bar-fill"
              :style="{
                width: getBarWidth(item, top1to5Max) + '%',
                background: getGradientStyle(idx)
              }"
            >
              <span class="bar-value">{{ item.value.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
        <!-- TOP4-5：纯色进度条，百分比在进度条外 -->
        <div v-for="(item, idx) in top1to5.slice(3, 5)" :key="item.name" class="top-item secondary">
          <div class="process-name">{{ item.name }}</div>
          <div class="bar-container bar-16">
            <div
              class="bar-fill"
              :style="{
                width: getBarWidth(item, top1to5Max) + '%',
                background: getSolidColor(idx + 3)
              }"
            ></div>
          </div>
          <span class="item-value">{{ item.value.toFixed(1) }}%</span>
        </div>
      </div>

      <!-- 右侧 TOP6-10 -->
      <div class="top-column">
        <div v-for="(item, idx) in top6to10" :key="item.name" class="top-item secondary">
          <div class="process-name">{{ item.name }}</div>
          <div class="bar-container bar-16">
            <div
              class="bar-fill"
              :style="{
                width: getBarWidth(item, top6to10Max) + '%',
                background: getSolidColor(idx + 5)
              }"
            ></div>
          </div>
          <span class="item-value">{{ item.value.toFixed(1) }}%</span>
        </div>
      </div>
    </div>

    <!-- 提示 -->
    <div class="top10-hint">
      点击上方CPU/GPU折线图的任意数据点，TOP10自动切换为该时刻的进程排名
    </div>
  </div>
</template>

<style scoped>
.top10-list {
  background: white;
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 15px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.top10-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.top10-title {
  margin: 0;
  color: #333;
  font-size: 15px;
}

.top10-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.time-badge {
  background: #f5f5f5;
  border: 1px solid #ddd;
  color: #666;
  padding: 5px 12px;
  border-radius: 5px;
  font-size: 12px;
}

.type-switch {
  display: flex;
  gap: 5px;
}

.switch-btn {
  background: #909399;
  color: white;
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  border: none;
  transition: background 0.2s;
}

.switch-btn.active {
  background: #409eff;
}

.switch-btn:hover:not(.active) {
  background: #73767a;
}

.top10-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.top-column {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

/* TOP前三样式 */
.top-item.top-3 {
  display: flex;
  align-items: center;
  gap: 8px;
}

.top-item.top-3 .process-name {
  width: 90px;
  font-size: 12px;
  color: #333;
}

.process-name.bold {
  font-weight: bold;
}

.bar-container.bar-20 {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 4px;
  position: relative;
}

.bar-container.bar-20 .bar-fill {
  height: 100%;
  border-radius: 4px;
  position: relative;
}

.bar-container.bar-20 .bar-value {
  position: absolute;
  right: 5px;
  top: 4px;
  font-size: 11px;
  color: white;
  font-weight: bold;
}

/* TOP4-10样式（次要） */
.top-item.secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.top-item.secondary .process-name {
  width: 90px;
  color: #666;
  font-weight: normal;
}

.bar-container.bar-16 {
  flex: 1;
  height: 16px;
  background: #f0f0f0;
  border-radius: 4px;
}

.bar-container.bar-16 .bar-fill {
  height: 100%;
  border-radius: 4px;
}

.item-value {
  font-size: 11px;
  color: #999;
  width: 45px;
  text-align: right;
}

.top10-hint {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #ddd;
  font-size: 12px;
  color: #666;
  text-align: center;
}
</style>