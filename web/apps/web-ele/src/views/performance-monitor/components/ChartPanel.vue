<script setup lang="ts">
import { ref, onMounted, watch, computed, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries, ChartTag } from '../types';
import type { PerformanceData } from '#/api/core/performance-monitor';

// 定义 Props 类型
interface Props {
  title: string;
  series: ChartSeries[];
  showTop10?: boolean;
  height?: number;
  timeRange?: [number, number];
  tags?: ChartTag[];
  // 新增 Props
  rawData?: PerformanceData[]; // 原始数据（用于 Tooltip 显示进程明细）
  enableTagClick?: boolean; // 是否允许点击添加标签
  collectId?: string; // 采集ID（用于标签操作）
  showActualTime?: boolean; // 是否显示实际时间
}

const props = withDefaults(defineProps<Props>(), {
  showTop10: false,
  height: 200,
  enableTagClick: false,
  showActualTime: false,
});

// 定义 Events
const emit = defineEmits<{
  (e: 'point-click', data: { time: number; collectId: string }): void;
  (e: 'tag-delete', tagId: string): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

const chartHeight = computed(() => props.height || 200);

// 主单位（取第一个 series 的单位）
const mainUnit = computed(() => {
  return props.series[0]?.unit || '%';
});

// 当前值显示（取最新数据点）
const currentValues = computed(() => {
  return props.series.map((s) => {
    const lastData = s.data[s.data.length - 1];
    const unit = s.unit || '%';
    let displayValue = '-';
    if (lastData?.value !== undefined) {
      if (unit === 'GB') {
        displayValue = lastData.value.toFixed(1) + ' GB';
      } else if (unit === 'MB') {
        displayValue = Math.round(lastData.value) + ' MB';
      } else {
        displayValue = lastData.value.toFixed(1) + '%';
      }
    }
    return {
      name: s.name,
      value: displayValue,
      color: s.color,
    };
  });
});

function initChart() {
  if (!chartRef.value) return;
  chartInstance = echarts.init(chartRef.value);

  // 绑定点击事件
  if (props.enableTagClick) {
    chartInstance.on('click', (params: any) => {
      if (params.componentType === 'series') {
        const dataIndex = params.dataIndex;
        const time = props.series[0]?.data[dataIndex]?.time;
        if (time !== undefined && props.collectId) {
          emit('point-click', { time, collectId: props.collectId });
        }
      }
    });
  }

  updateChart();
}

function formatDateTime(timestamp: string): string {
  const date = new Date(timestamp);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function updateChart() {
  if (!chartInstance) return;

  const xAxisData = props.series[0]?.data.map((d) => d.time) || [];

  const seriesConfig = props.series.map((s) => ({
    name: s.name,
    type: 'line',
    data: s.data.map((d) => d.value),
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    smooth: true,
    symbol: 'none',
  }));

  // 标签区间标记
  const markAreas: any[] = [];
  if (props.tags) {
    props.tags.forEach((tag) => {
      markAreas.push([
        {
          xAxis: tag.start,
          itemStyle: {
            color:
              tag.type === 'peak'
                ? 'rgba(103,194,126,0.15)'
                : 'rgba(245,108,108,0.15)',
          },
        },
        { xAxis: tag.start + tag.duration },
      ]);
    });
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const dataIndex = params[0].dataIndex;
        const relativeTime = params[0].axisValue;
        const rawDataPoint = props.rawData?.[dataIndex];

        let html = `<div style="font-size:12px;padding:4px 8px;">`;

        // 相对时间
        html += `<div><span style="color:#666">相对时间:</span> <b>${relativeTime}秒</b></div>`;

        // 实际时间（如果有原始数据）
        if (rawDataPoint?.timestamp && props.showActualTime) {
          html += `<div><span style="color:#666">实际时间:</span> <b style="color:#409eff">${formatDateTime(rawDataPoint.timestamp)}</b></div>`;
        }

        html += `<div style="margin-top:4px;padding-top:4px;border-top:1px dashed #eee">`;

        // 曲线值
        params.forEach((p: any, idx: number) => {
          const series = props.series[idx];
          const unit = series?.unit || '%';
          let displayValue = '-';
          if (p.value !== undefined) {
            if (unit === 'GB') {
              displayValue = p.value.toFixed(1) + ' GB';
            } else if (unit === 'MB') {
              displayValue = Math.round(p.value) + ' MB';
            } else {
              displayValue = p.value.toFixed(1) + '%';
            }
          }
          html += `<div><span style="color:${p.color}">${p.seriesName}:</span> <b>${displayValue}</b></div>`;
        });

        // 进程明细（如果有原始数据）
        if (rawDataPoint?.target_processes?.length) {
          html += `<div style="margin-top:4px;padding-top:4px;border-top:1px dashed #eee">`;
          html += `<div style="color:#999;font-size:11px">进程明细:</div>`;
          rawDataPoint.target_processes.forEach((p) => {
            html += `<div style="font-size:11px"><span style="color:#999">${p.name}</span> CPU ${p.total_cpu.toFixed(1)}%, Mem ${p.total_memory.toFixed(0)}MB</div>`;
            // 实例明细
            if (p.instances?.length) {
              p.instances.forEach((inst) => {
                html += `<div style="font-size:10px;color:#666;padding-left:8px">PID ${inst.pid}: CPU ${inst.cpu.toFixed(1)}%</div>`;
              });
            }
          });
          html += `</div>`;
        }

        html += `</div></div>`;
        return html;
      },
    },
    legend: {
      show: false,
    },
    grid: {
      left: 40,
      right: 10,
      top: 5,
      bottom: 20,
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: { formatter: (v: number) => `${v}s` },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v: number) => {
          if (mainUnit.value === 'GB') {
            return `${v} GB`;
          } else if (mainUnit.value === 'MB') {
            return `${v} MB`;
          }
          return `${v}%`;
        },
      },
    },
    series: seriesConfig,
  };

  // 添加标签区间标记
  if (markAreas.length > 0 && seriesConfig.length > 0) {
    (option as any).series[0].markArea = {
      data: markAreas,
    };
  }

  chartInstance.setOption(option);
}

watch(() => props.series, updateChart, { deep: true });
watch(() => props.timeRange, updateChart);
watch(() => props.tags, updateChart, { deep: true });
watch(() => props.rawData, updateChart, { deep: true });

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
  <div class="chart-panel">
    <div class="chart-title">{{ title }}</div>
    <div
      ref="chartRef"
      class="chart-container"
      :style="{ height: chartHeight + 'px' }"
    >
      <!-- 当前值叠加在图表右上角 -->
      <div class="chart-values-overlay">
        <div
          v-for="cv in currentValues"
          :key="cv.name"
          class="overlay-value"
          :style="{ color: cv.color }"
        >
          {{ cv.name }}: {{ cv.value }}
        </div>
      </div>
    </div>
    <!-- 标签列表显示 -->
    <div v-if="tags?.length" class="tags-list">
      <div
        v-for="tag in tags"
        :key="tag.name"
        class="tag-item"
        :class="tag.type === 'peak' ? 'tag-peak' : 'tag-mean'"
      >
        <span class="tag-name">{{ tag.name }}</span>
        <span class="tag-range">{{ tag.start }}s - {{ tag.start + tag.duration }}s</span>
        <button class="tag-delete" @click="emit('tag-delete', tag.name)">×</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-panel {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
}
.chart-title {
  font-size: 15px;
  font-weight: 700;
  color: #333;
  margin-bottom: 8px;
}
.chart-container {
  width: 100%;
  background: #f8f9fa;
  border-radius: 4px;
  position: relative;
}
.chart-values-overlay {
  position: absolute;
  top: 4px;
  right: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  z-index: 10;
  pointer-events: none;
}
.overlay-value {
  font-size: 10px;
  line-height: 1.4;
}
.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.tag-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.tag-peak {
  background: rgba(103, 194, 126, 0.15);
  border: 1px solid rgba(103, 194, 126, 0.4);
  color: #67c23a;
}
.tag-mean {
  background: rgba(245, 108, 108, 0.15);
  border: 1px solid rgba(245, 108, 108, 0.4);
  color: #f56c6c;
}
.tag-name {
  font-weight: 600;
}
.tag-range {
  color: #666;
}
.tag-delete {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
}
.tag-delete:hover {
  opacity: 0.7;
}
</style>