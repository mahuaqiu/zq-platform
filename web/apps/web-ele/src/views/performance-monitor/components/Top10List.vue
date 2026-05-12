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

// 进度条颜色
function getBarColor(idx: number): string {
  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#b37beb', '#91d5ff', '#ff85c0', '#87e8de', '#95de64'];
  return colors[idx] || '#909399';
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
        <div v-for="(item, idx) in top1to5" :key="idx" class="top-item">
          <div class="process-name" :class="{ bold: idx < 3 }">{{ item.name }}</div>
          <div class="bar-container">
            <div
              class="bar-fill"
              :style="{
                width: getBarWidth(item, top1to5Max) + '%',
                background: `linear-gradient(90deg, ${getBarColor(idx)}, ${getBarColor(idx)}aa)`
              }"
            >
              <span v-if="idx < 3" class="bar-value">{{ item.value.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧 TOP6-10 -->
      <div class="top-column">
        <div v-for="(item, idx) in top6to10" :key="idx" class="top-item secondary">
          <div class="process-name">{{ item.name }}</div>
          <div class="bar-container">
            <div
              class="bar-fill"
              :style="{
                width: getBarWidth(item, top1to5Max) + '%',
                background: getBarColor(idx + 5)
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
.top-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.process-name {
  width: 90px;
  font-size: 12px;
  color: #333;
}
.process-name.bold {
  font-weight: bold;
}
.bar-container {
  flex: 1;
  height: 20px;
  background: #f0f0f0;
  border-radius: 4px;
  position: relative;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  position: relative;
}
.bar-value {
  position: absolute;
  right: 5px;
  top: 4px;
  font-size: 11px;
  color: white;
  font-weight: bold;
}
.top-item.secondary {
  font-size: 11px;
}
.top-item.secondary .process-name {
  color: #666;
  font-weight: normal;
}
.top-item.secondary .bar-container {
  height: 16px;
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