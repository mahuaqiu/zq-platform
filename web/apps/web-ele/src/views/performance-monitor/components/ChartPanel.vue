<script setup lang="ts">
import { ref, onMounted, watch, computed, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries, ChartTag } from '../types';
import type {
  PerformanceData,
  MarkerResponse,
} from '#/api/core/performance-monitor';

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
  chartType?: 'cpu' | 'gpu' | 'memory' | 'commitMemory'; // 图表类型，用于区分 tooltip
  markers?: MarkerResponse[]; // 标记列表（v0.3.0）
}

const props = withDefaults(defineProps<Props>(), {
  showTop10: false,
  height: 200,
  enableTagClick: false,
  showActualTime: false,
  chartType: 'cpu',
  markers: () => [],
});

// 定义 Events（改造为双区域tooltip）
const emit = defineEmits<{
  (e: 'point-click', data: { time: number; collectId: string }): void;
  (e: 'tag-delete', tagId: string): void;
  (e: 'mini-tooltip-show', data: {
    position: { x: number; y: number };
    data: PerformanceData | undefined;
    seriesData: { name: string; value: number; color: string; unit: string }[];
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
    containerRect: DOMRect;
  }): void;
  (e: 'mini-tooltip-hide'): void;
  (e: 'detail-click', data: {
    data: PerformanceData | undefined;
    seriesData: { name: string; value: number; color: string; unit: string }[];
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory';
    chartKey: string;
  }): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

const chartHeight = computed(() => props.height || 200);

// 主单位（取第一个 series 的单位）
const mainUnit = computed(() => {
  return props.series[0]?.unit || '%';
});

// 计算X轴间隔（根据数据量智能调整）
const xAxisInterval = computed(() => {
  const dataLength = props.series[0]?.data.length || 0;
  // 数据量少于10个，全部显示
  if (dataLength <= 10) return 0;
  // 数据量10-30，间隔1个显示
  if (dataLength <= 30) return 1;
  // 数据量30-60，间隔2个显示
  if (dataLength <= 60) return 2;
  // 数据量60-120，间隔3个显示
  if (dataLength <= 120) return 3;
  // 数据量120-300，间隔5个显示
  if (dataLength <= 300) return 5;
  // 数据量300-600，间隔10个显示
  if (dataLength <= 600) return 10;
  // 数据量更大，间隔15个显示
  return 15;
});
// 当前值显示（右上角叠加）
const currentValues = computed(() => {
  return props.series.map((s) => {
    const lastData = s.data[s.data.length - 1];
    const unit = s.unit || '%';
    let displayValue = '-';
    if (lastData?.value !== undefined) {
      if (unit === 'GB') {
        displayValue = lastData.value.toFixed(1);
      } else if (unit === 'MB') {
        displayValue = Math.round(lastData.value).toString();
      } else {
        displayValue = lastData.value.toFixed(1);
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

  // 监听鼠标移动事件，传递数据给外部 mini tooltip
  chartInstance.on('mousemove', (params: any) => {
    if (params.componentType === 'series') {
      const dataIndex = params.dataIndex;
      const rawDataPoint = props.rawData?.[dataIndex];

      // 构建主曲线数据
      const seriesData = props.series.map((s) => ({
        name: s.name,
        value: s.data[dataIndex]?.value || 0,
        color: s.color,
        unit: s.unit || '%',
      }));

      emit('mini-tooltip-show', {
        position: { x: params.event.offsetX, y: params.event.offsetY },
        data: rawDataPoint,
        seriesData,
        chartType: props.chartType,
        containerRect: chartRef.value!.getBoundingClientRect(),
      });
    }
  });

  // 监听鼠标离开事件
  chartInstance.on('mouseout', () => {
    emit('mini-tooltip-hide');
  });

  // 监听点击事件，传递数据给外部 detail panel
  chartInstance.on('click', (params: any) => {
    if (params.componentType === 'series') {
      const dataIndex = params.dataIndex;
      const rawDataPoint = props.rawData?.[dataIndex];

      // 构建主曲线数据
      const seriesData = props.series.map((s) => ({
        name: s.name,
        value: s.data[dataIndex]?.value || 0,
        color: s.color,
        unit: s.unit || '%',
      }));

      emit('detail-click', {
        data: rawDataPoint,
        seriesData,
        chartType: props.chartType,
        chartKey: props.chartType,  // 用 chartType 作为标识
      });
    }
  });

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

// 计算Y轴范围（智能分段，根据数据范围动态调整）
const yAxisConfig = computed(() => {
  const unit = mainUnit.value;
  const allValues = props.series.flatMap((s) => s.data.map((d) => d.value));

  if (allValues.length === 0) {
    return { min: 0, max: 100, interval: 20 };
  }

  const maxValue = Math.max(...allValues);
  const minValue = Math.min(...allValues);
  const range = maxValue - minValue;

  if (unit === '%') {
    // 百分比：从0开始，根据最大值智能分段
    if (maxValue <= 10) {
      return { min: 0, max: 10, interval: 2 };
    } else if (maxValue <= 20) {
      return { min: 0, max: 20, interval: 4 };
    } else if (maxValue <= 50) {
      return { min: 0, max: 50, interval: 10 };
    } else if (maxValue <= 100) {
      return { min: 0, max: 100, interval: 20 };
    } else {
      const roundedMax = Math.ceil(maxValue / 20) * 20;
      return { min: 0, max: roundedMax, interval: 20 };
    }
  } else if (unit === 'MB') {
    // MB单位：智能计算范围，数据集中在某个区间时不从0开始
    // 当数据波动小于最大值的20%时，Y轴从最小值附近开始
    if (range < maxValue * 0.3 && minValue > 200) {
      // 计算合适的Y轴范围
      const padding = range * 0.2; // 上下留20%空间
      let baseMin = Math.floor((minValue - padding) / 50) * 50;
      let baseMax = Math.ceil((maxValue + padding) / 50) * 50;

      // 确保最小值不小于0
      if (baseMin < 0) baseMin = 0;

      // 计算合适的间隔（约4-5个刻度）
      const diff = baseMax - baseMin;
      let interval = Math.ceil(diff / 4 / 50) * 50;
      if (interval < 50) interval = 50;
      if (interval > 500) interval = Math.ceil(interval / 100) * 100;

      return { min: baseMin, max: baseMax, interval };
    }

    // 数据波动大或最小值较小，从0开始
    if (maxValue <= 100) {
      return { min: 0, max: 100, interval: 25 };
    } else if (maxValue <= 200) {
      return { min: 0, max: 200, interval: 50 };
    } else if (maxValue <= 500) {
      return { min: 0, max: 500, interval: 100 };
    } else if (maxValue <= 1000) {
      return { min: 0, max: 1000, interval: 200 };
    } else if (maxValue <= 2000) {
      return { min: 0, max: 2000, interval: 400 };
    } else if (maxValue <= 5000) {
      return { min: 0, max: 5000, interval: 1000 };
    } else if (maxValue <= 10000) {
      return { min: 0, max: 10000, interval: 2000 };
    } else {
      const roundedMax = Math.ceil(maxValue / 2000) * 2000;
      return {
        min: 0,
        max: roundedMax,
        interval: Math.ceil(roundedMax / 5 / 100) * 100,
      };
    }
  } else if (unit === 'GB') {
    // GB单位：智能计算范围
    if (range < maxValue * 0.3 && minValue > 0.5) {
      const padding = range * 0.2;
      let baseMin = Math.floor((minValue - padding) * 10) / 10;
      let baseMax = Math.ceil((maxValue + padding) * 10) / 10;
      if (baseMin < 0) baseMin = 0;
      const diff = baseMax - baseMin;
      let interval = Math.ceil((diff * 10) / 4) / 10;
      if (interval < 0.1) interval = 0.1;
      return { min: baseMin, max: baseMax, interval };
    }

    if (maxValue <= 1) {
      return { min: 0, max: 1, interval: 0.2 };
    } else if (maxValue <= 2) {
      return { min: 0, max: 2, interval: 0.5 };
    } else if (maxValue <= 5) {
      return { min: 0, max: 5, interval: 1 };
    } else if (maxValue <= 10) {
      return { min: 0, max: 10, interval: 2 };
    } else if (maxValue <= 20) {
      return { min: 0, max: 20, interval: 4 };
    } else {
      const roundedMax = Math.ceil(maxValue / 4) * 4;
      return { min: 0, max: roundedMax, interval: 4 };
    }
  }

  return {
    min: 0,
    max: Math.ceil(maxValue * 1.2),
    interval: Math.ceil(maxValue / 5),
  };
});

function updateChart() {
  if (!chartInstance) return;

  const xAxisData = props.series[0]?.data.map((d) => d.time) || [];

  // 当数据为空时，清空图表防止旧数据残留
  if (xAxisData.length === 0) {
    chartInstance.clear();
    return;
  }

  const seriesConfig = props.series.map((s) => ({
    name: s.name,
    type: 'line',
    data: s.data.map((d) => d.value),
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    smooth: false,
    symbol: 'none',
  }));

  // 标记圆点显示
  if (props.markers && props.markers.length > 0 && seriesConfig.length > 0) {
    const markPointData: any[] = [];

    props.markers.forEach((marker) => {
      // 找到标记起点对应的 dataIndex
      const dataIndex = props.series[0]?.data.findIndex(
        (d) => d.time === marker.start_time,
      );
      if (dataIndex !== undefined && dataIndex >= 0) {
        const yValue = props.series[0].data[dataIndex].value;
        markPointData.push({
          coord: [dataIndex, yValue],
          symbol: 'circle',
          symbolSize: 10,
          itemStyle: {
            color: marker.color,
            borderColor: 'white',
            borderWidth: 2,
          },
          label: {
            show: true,
            formatter: marker.name,
            position: 'top',
            color: marker.color,
            fontSize: 10,
          },
        });
      }
    });

    if (markPointData.length > 0) {
      seriesConfig[0].markPoint = { data: markPointData };
    }
  }

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
      show: false  // 完全禁用原 tooltip，使用外部组件控制
    },
    legend: {
      show: false,
    },
    grid: {
      left: 40,
      right: 15,
      top: 25,
      bottom: 25,
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: {
        formatter: (v: number) => `${v}s`,
        interval: xAxisInterval.value,
      },
    },
    yAxis: {
      type: 'value',
      min: yAxisConfig.value.min,
      max: yAxisConfig.value.max,
      interval: yAxisConfig.value.interval,
      splitNumber: 4, // 固定分成4段，避免太密集
      axisLabel: {
        formatter: (v: number) => {
          // Y轴不显示单位，单位在标题上显示
          if (mainUnit.value === 'GB') {
            return v.toFixed(v < 1 ? 1 : 0);
          } else if (mainUnit.value === 'MB') {
            return Math.round(v);
          }
          return v;
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
watch(() => props.markers, updateChart, { deep: true });

onMounted(() => {
  initChart();
});

onUnmounted(() => {
  if (chartInstance) {
    try {
      // 检查 DOM 元素是否仍然存在
      if (chartRef.value && document.body.contains(chartRef.value)) {
        chartInstance.dispose();
      }
    } catch (e) {
      // 忽略 dispose 错误
      console.warn('Chart dispose error:', e);
    }
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
        <span class="tag-range"
          >{{ tag.start }}s - {{ tag.start + tag.duration }}s</span
        >
        <button class="tag-delete" @click="emit('tag-delete', tag.name)">
          ×
        </button>
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
