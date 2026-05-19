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
  chartType?: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo'; // 图表类型，用于区分 tooltip
  markers?: MarkerResponse[]; // 标记列表（v0.3.0）
}

const props = withDefaults(defineProps<Props>(), {
  showTop10: false,
  height: 310,
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
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
    containerRect: DOMRect;
  }): void;
  (e: 'mini-tooltip-hide'): void;
  (e: 'detail-click', data: {
    data: PerformanceData | undefined;
    seriesData: { name: string; value: number; color: string; unit: string }[];
    chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
    chartKey: string;
    position: { x: number; y: number };
    containerWidth: number;
  }): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

// 均值线显示状态（默认关闭）
const showMeanLine = ref(false);

// 切换均值线显示
function toggleMeanLine() {
  showMeanLine.value = !showMeanLine.value;
  updateChart();
}

// 使用原生 DOM 事件代替 ECharts 事件
onMounted(() => {
  if (chartRef.value) {
    // 鼠标移动事件
    chartRef.value.addEventListener('mousemove', (e) => {
      // 检查图表是否有数据
      if (!props.series.length || !chartInstance) return;

      // 获取鼠标在图表中的位置
      const offsetX = e.offsetX;
      const offsetY = e.offsetY;

      // 使用 ECharts 的 convertFromPixel 来获取数据索引
      try {
        const pointInPixel = [offsetX, offsetY];
        const pointInGrid = chartInstance.convertFromPixel('grid', pointInPixel);

        if (pointInGrid && pointInGrid[0] !== undefined) {
          // pointInGrid[0] 是 x 轴索引（ dataIndex ）
          const dataIndex = Math.round(pointInGrid[0]);

          if (dataIndex >= 0 && dataIndex < props.series[0].data.length) {
            const rawDataPoint = props.rawData?.[dataIndex];

            // 构建主曲线数据
            const seriesData = props.series.map((s) => ({
              name: s.name,
              value: s.data[dataIndex]?.value || 0,
              color: s.color,
              unit: s.unit || '%',
            }));

            emit('mini-tooltip-show', {
              position: { x: offsetX, y: offsetY },
              data: rawDataPoint,
              seriesData,
              chartType: props.chartType,
              containerRect: chartRef.value!.getBoundingClientRect(),
            });
          }
        }
      } catch (err) {
        // 忽略错误
      }
    });

    // 鼠标离开事件
    chartRef.value.addEventListener('mouseout', () => {
      emit('mini-tooltip-hide');
    });

    // 点击事件
    chartRef.value.addEventListener('click', (e) => {
      if (!props.series.length || !chartInstance) {
        return;
      }

      const offsetX = e.offsetX;
      const offsetY = e.offsetY;

      try {
        const pointInPixel = [offsetX, offsetY];
        const pointInGrid = chartInstance.convertFromPixel('grid', pointInPixel);

        if (pointInGrid && pointInGrid[0] !== undefined) {
          const dataIndex = Math.round(pointInGrid[0]);

          if (dataIndex >= 0 && dataIndex < props.series[0].data.length) {
            const rawDataPoint = props.rawData?.[dataIndex];

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
              chartKey: props.chartType,
              position: { x: offsetX, y: offsetY },
              containerWidth: chartRef.value?.offsetWidth || 800,
            });
          }
        }
      } catch (err) {
        // 忽略点击错误
      }
    });
  }
});

const chartHeight = computed(() => props.height || 310);

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

  // 绑定点击事件（仅在 enableTagClick 时）
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

// 计算Y轴范围（智能分段，根据数据范围动态调整）
const yAxisConfig = computed(() => {
  const unit = mainUnit.value;
  const allValues = props.series.flatMap((s) => s.data.map((d) => d.value));

  if (allValues.length === 0) {
    return { min: 0, max: 100, interval: 20, gridLeft: 40 };
  }

  const maxValue = Math.max(...allValues);
  const minValue = Math.min(...allValues);
  const range = maxValue - minValue;

  // 根据最大值位数动态计算 gridLeft
  // 对于大数值（如句柄数），需要更多空间
  const valueLength = Math.ceil(maxValue).toString().length;
  const gridLeft = Math.max(40, valueLength * 8 + 5);

  if (unit === '%') {
    // 百分比：从0开始，根据最大值智能分段
    if (maxValue <= 10) {
      return { min: 0, max: 10, interval: 2, gridLeft };
    } else if (maxValue <= 20) {
      return { min: 0, max: 20, interval: 4, gridLeft };
    } else if (maxValue <= 50) {
      return { min: 0, max: 50, interval: 10, gridLeft };
    } else if (maxValue <= 100) {
      return { min: 0, max: 100, interval: 20, gridLeft };
    } else {
      const roundedMax = Math.ceil(maxValue / 20) * 20;
      return { min: 0, max: roundedMax, interval: 20, gridLeft };
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

      return { min: baseMin, max: baseMax, interval, gridLeft };
    }

    // 数据波动大或最小值较小，从0开始
    if (maxValue <= 100) {
      return { min: 0, max: 100, interval: 25, gridLeft };
    } else if (maxValue <= 200) {
      return { min: 0, max: 200, interval: 50, gridLeft };
    } else if (maxValue <= 500) {
      return { min: 0, max: 500, interval: 100, gridLeft };
    } else if (maxValue <= 1000) {
      return { min: 0, max: 1000, interval: 200, gridLeft };
    } else if (maxValue <= 2000) {
      return { min: 0, max: 2000, interval: 400, gridLeft };
    } else if (maxValue <= 5000) {
      return { min: 0, max: 5000, interval: 1000, gridLeft };
    } else if (maxValue <= 10000) {
      return { min: 0, max: 10000, interval: 2000, gridLeft };
    } else {
      const roundedMax = Math.ceil(maxValue / 2000) * 2000;
      return {
        min: 0,
        max: roundedMax,
        interval: Math.ceil(roundedMax / 5 / 100) * 100,
        gridLeft,
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
      return { min: baseMin, max: baseMax, interval, gridLeft };
    }

    if (maxValue <= 1) {
      return { min: 0, max: 1, interval: 0.2, gridLeft };
    } else if (maxValue <= 2) {
      return { min: 0, max: 2, interval: 0.5, gridLeft };
    } else if (maxValue <= 5) {
      return { min: 0, max: 5, interval: 1, gridLeft };
    } else if (maxValue <= 10) {
      return { min: 0, max: 10, interval: 2, gridLeft };
    } else if (maxValue <= 20) {
      return { min: 0, max: 20, interval: 4, gridLeft };
    } else {
      const roundedMax = Math.ceil(maxValue / 4) * 4;
      return { min: 0, max: roundedMax, interval: 4, gridLeft };
    }
  }

  // 其他单位（如"个"）：从0开始，大数值使用缩写
  return {
    min: 0,
    max: Math.ceil(maxValue * 1.2),
    interval: Math.ceil(maxValue / 5),
    gridLeft,
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
    // 大数据模式优化（超过2000个点时自动启用）
    large: true,
    largeThreshold: 2000,
    // 渐进式渲染（超过3000个点时启用，每帧渲染400个点）
    progressive: 400,
    progressiveThreshold: 3000,
    progressiveChunkMode: 'mod',  // 交错渲染，体感更流畅
    // 均值线（当开启时显示）
    markLine: showMeanLine.value ? {
      silent: true,
      symbol: 'none',
      label: { show: false }, // 不显示均值数值
      lineStyle: {
        color: s.color,
        type: 'dashed',
        width: 1,
        opacity: 0.6,
      },
      data: [{ type: 'average' }],
    } : undefined,
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
    // 工具栏配置 - 右上角
    toolbox: {
      show: true,
      right: 10,
      top: 5,
      orient: 'horizontal',
      itemSize: 14,
      itemGap: 8,
      feature: {
        // 均值线开关
        myMeanLine: {
          show: true,
          title: showMeanLine.value ? '隐藏均值线' : '显示均值线',
          icon: 'path://M512 0c282.77 0 512 229.23 512 512s-229.23 512-512 512S0 794.77 0 512S229.23 0 512 0zm0 64C264.58 64 64 264.58 64 512s200.58 448 448 448 448-200.58 448-448S759.42 64 512 64zm-32 192h64v384h-64V256zm0 448h64v64h-64v-64z',
          onclick: toggleMeanLine,
        },
        saveAsImage: {
          show: true,
          title: '保存为图片',
          type: 'png',
          pixelRatio: 2,
          name: props.title || '性能监控图表',
        },
      },
    },
    // 图例配置（点击可隐藏/显示线条）- 右上角，toolbox左边
    legend: {
      show: true,
      type: 'scroll',
      orient: 'horizontal',
      right: 70,
      top: 5,
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 8,
      textStyle: {
        color: '#666',
        fontSize: 12,
      },
      data: props.series.map(s => s.name),
    },
    tooltip: {
      show: false  // 禁用原 tooltip，使用原生 DOM 事件
    },
    grid: {
      left: yAxisConfig.value.gridLeft,
      right: 15,
      top: 30,
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
          // 大数值（如句柄数）使用缩写格式
          if (v >= 10000) {
            return (v / 1000).toFixed(1) + 'k';
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

  // 使用 notMerge: true 完全替换旧配置，避免旧数据线残留
  chartInstance.setOption(option, { notMerge: true });
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
  padding: 12px;
  background: #fff;
  border-radius: 6px;
}

.chart-title {
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #333;
}

.chart-container {
  position: relative;
  width: 100%;
  background: #f8f9fa;
  border-radius: 4px;
}

.chart-values-overlay {
  position: absolute;
  top: 4px;
  right: 8px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 2px;
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
  gap: 4px;
  align-items: center;
  padding: 4px 8px;
  font-size: 11px;
  border-radius: 4px;
}

.tag-peak {
  color: #67c23a;
  background: rgb(103 194 126 / 15%);
  border: 1px solid rgb(103 194 126 / 40%);
}

.tag-mean {
  color: #f56c6c;
  background: rgb(245 108 108 / 15%);
  border: 1px solid rgb(245 108 108 / 40%);
}

.tag-name {
  font-weight: 600;
}

.tag-range {
  color: #666;
}

.tag-delete {
  padding: 0;
  font-size: 14px;
  line-height: 1;
  color: inherit;
  cursor: pointer;
  background: none;
  border: none;
}

.tag-delete:hover {
  opacity: 0.7;
}
</style>
