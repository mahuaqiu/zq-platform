<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { ChartSeries } from '../types';
import type { CompareTag } from '../types';

const props = defineProps<{
  title?: string; // 图表标题
  series: ChartSeries[];
  tags: CompareTag[];
  loading?: boolean;
  currentMetric?: string; // 当前指标类型
  hwinfoUnit?: string; // HWiNFO 指标单位
  dataZoomType?: 'slider' | 'inside' | 'none'; // dataZoom 类型
  chartGroup?: string; // 图表分组（用于联动）
  dataZoomStart?: number; // dataZoom 起始位置
  dataZoomEnd?: number; // dataZoom 结束位置
}>();

// 判断是否是内存类指标
const isMemoryMetric = computed(() => {
  return props.currentMetric?.includes('memory') || false;
});

// 判断是否是 HWiNFO 指标
const isHwinfoMetric = computed(() => {
  return props.currentMetric === 'hwinfo';
});

// 单位
const unit = computed(() => {
  if (isHwinfoMetric.value) return props.hwinfoUnit || '';
  if (isMemoryMetric.value) return 'GB';
  return '%';
});

const emit = defineEmits<{
  (e: 'hover-change', data: { time: number; values: Record<string, number> }): void;
  (e: 'datazoom-change', data: { start: number; end: number }): void;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

// 均值线显示状态（默认关闭）
const showMeanLine = ref(false);

// 切换均值线显示
function toggleMeanLine() {
  showMeanLine.value = !showMeanLine.value;
  initChart();
}

// 获取 dataZoom 配置
const getDataZoomConfig = () => {
  const type = props.dataZoomType || 'none';

  if (type === 'none') return undefined;

  if (type === 'slider') {
    // 滑块类型，显示在图表底部（和 CPU/GPU 一致）
    return [
      {
        type: 'slider',
        show: true,
        xAxisIndex: 0,
        start: 0,
        end: 100,
        height: 20,
        bottom: 5,
        left: 60,
        right: 40,
        borderColor: '#ddd',
        fillerColor: 'rgba(64, 158, 255, 0.2)',
        handleStyle: { color: '#409eff' },
        textStyle: { color: '#666' },
        labelFormatter: (value: number) => `${Math.round(value)}秒`,
      },
      {
        type: 'inside',
        xAxisIndex: 0,
      },
    ];
  }

  if (type === 'inside') {
    // 内置类型，不显示滑块（用于系统图表）
    return [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: props.dataZoomStart ?? 0,
        end: props.dataZoomEnd ?? 100,
      },
    ];
  }

  return undefined;
};

const initChart = () => {
  if (!chartRef.value) return;
  chart = echarts.init(chartRef.value);

  // Build markArea data from tags (using relative seconds directly)
  const peakAreas = props.tags
    .filter(t => t.type === 'peak')
    .map(t => {
      return [{ xAxis: t.start_time }, { xAxis: t.end_time }] as Array<{ xAxis: number }>;
    });

  const stableAreas = props.tags
    .filter(t => t.type === 'stable')
    .map(t => {
      return [{ xAxis: t.start_time }, { xAxis: t.end_time }] as Array<{ xAxis: number }>;
    });

  const seriesData = props.series.map((s, index) => {
    return {
      name: s.name,
      type: 'line',
      data: s.data.map(d => [d.time, d.value]),
      lineStyle: {
        color: s.color,
        width: 2,
      },
      itemStyle: { color: s.color },
      smooth: false,
      symbol: 'none',
      // 大数据模式优化（超过2000个点时自动启用）
      large: true,
      largeThreshold: 2000,
      // 渐进式渲染（超过3000个点时启用）
      progressive: 400,
      progressiveThreshold: 3000,
      progressiveChunkMode: 'mod',
      // 只给第一条线添加 markArea（标签区域）
      markArea: index === 0 ? {
        silent: true,
        itemStyle: {
          color: 'rgba(230, 162, 60, 0.1)', // 冲高区域橙色
        },
        data: peakAreas,
      } : undefined,
      // 均值线（当开启时显示）
      markLine: showMeanLine.value ? {
        silent: true,
        symbol: 'none',
        label: { show: false }, // 不显示均值数值
        lineStyle: {
          color: s.color,
          type: 'dashed',
          width: 2,
          opacity: 0.8,
        },
        data: [{ type: 'average' }],
      } : undefined,
    };
  }) as echarts.SeriesOption[];

  // Add stable areas as separate series if needed
  if (stableAreas.length > 0) {
    seriesData.push({
      type: 'line',
      markArea: {
        silent: true,
        itemStyle: {
          color: 'rgba(103, 194, 58, 0.1)', // 稳态区域绿色
        },
        data: stableAreas,
      },
      data: [],
    } as echarts.SeriesOption);
  }

  const option: echarts.EChartsOption = {
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
          name: props.title || '性能对比图表',
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
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#fff',
      borderColor: '#eee',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: {
        color: '#333',
        fontSize: 12,
      },
      formatter: (params: any) => {
        if (!Array.isArray(params)) params = [params];
        const time = params[0]?.data?.[0] ?? params[0]?.value?.[0];
        let result = `<div style="font-weight:600;margin-bottom:6px;color:#666;">时间: ${time}秒</div>`;
        params.forEach((p: any) => {
          if (p.seriesName) {
            const value = p.data?.[1] ?? p.value?.[1] ?? 0;
            const color = p.color || '#409eff';
            const formattedValue = isMemoryMetric.value
              ? value.toFixed(2)
              : value.toFixed(1);
            result += `<div style="display:flex;align-items:center;margin:2px 0;">
              <span style="display:inline-block;width:10px;height:10px;background:${color};border-radius:50%;margin-right:6px;"></span>
              <span style="color:#333;">${p.seriesName}: </span>
              <span style="font-weight:500;color:${color};">${formattedValue}${unit.value}</span>
            </div>`;
          }
        });
        return result;
      },
    },
    grid: {
      left: 60,
      right: 15,
      bottom: 40,
      top: 30,
    },
    xAxis: {
      type: 'value',
      name: '相对时间(秒)',
      nameLocation: 'middle',
      nameGap: 30,
    },
    yAxis: {
      type: 'value',
    },
    dataZoom: getDataZoomConfig(),
    series: seriesData,
  };

  chart.setOption(option);

  // 设置图表分组（用于联动）
  if (props.chartGroup) {
    chart.group = props.chartGroup;
    echarts.connect(props.chartGroup);
  }

  // DataZoom 事件
  chart.on('datazoom', (params: any) => {
    emit('datazoom-change', {
      start: params.start || 0,
      end: params.end || 100,
    });
  });

  // Hover event
  chart.on('axisSelect', (params: unknown) => {
    const p = params as { dataTime?: number };
    if (p.dataTime) {
      const values: Record<string, number> = {};
      props.series.forEach(s => {
        const point = s.data.find(d => d.time === p.dataTime);
        if (point?.value != null) values[s.name] = point.value;
      });
      emit('hover-change', { time: p.dataTime, values });
    }
  });
};

watch([() => props.series, () => props.tags], () => {
  if (chart) initChart();
}, { deep: true });

onMounted(() => {
  initChart();
  window.addEventListener('resize', () => chart?.resize());
});

onUnmounted(() => {
  chart?.dispose();
  window.removeEventListener('resize', () => chart?.resize());
});
</script>

<template>
  <div class="compare-chart-panel" v-loading="loading">
    <!-- 所有类型：标题统一放在左上角 -->
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container" :class="{ 'has-datazoom': dataZoomType === 'slider' }"></div>
  </div>
</template>

<style scoped>
.compare-chart-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.chart-container {
  height: 300px;
}

.chart-container.has-datazoom {
  height: 320px;
}
</style>