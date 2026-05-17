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
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

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
      // 只给第一条线添加 markArea（标签区域）
      markArea: index === 0 ? {
        silent: true,
        itemStyle: {
          color: 'rgba(245, 108, 108, 0.08)', // 冲高区域更淡的红色
        },
        data: peakAreas,
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
          color: 'rgba(103, 194, 58, 0.08)', // 稳态区域更淡的绿色
        },
        data: stableAreas,
      },
      data: [],
    } as echarts.SeriesOption);
  }

  const option: echarts.EChartsOption = {
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
      right: 40,
      bottom: 40,
      top: 40,
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
    series: seriesData,
  };

  chart.setOption(option);

  // Hover event
  chart.on('axisSelect', (params: unknown) => {
    const p = params as { dataTime?: number };
    if (p.dataTime) {
      const values: Record<string, number> = {};
      props.series.forEach(s => {
        const point = s.data.find(d => d.time === p.dataTime);
        if (point) values[s.name] = point.value;
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
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartRef" class="chart-container"></div>
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
</style>