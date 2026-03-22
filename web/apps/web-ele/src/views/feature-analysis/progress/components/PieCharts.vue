<script setup lang="ts">
import type { EchartsUIType } from '@vben/plugins/echarts';

import { onMounted, ref, watch } from 'vue';

import { EchartsUI, useEcharts } from '@vben/plugins/echarts';

import type { PieChartDataItem } from '#/api/core/feature-analysis';

import {
  getTimelyTestChartApi,
  getTestStatusChartApi,
  getVerifyStatusChartApi,
} from '#/api/core/feature-analysis';

defineOptions({ name: 'PieCharts' });

const props = defineProps<{
  version?: string;
}>();

// 三个饼图的 ref
const chart1Ref = ref<EchartsUIType>();
const chart2Ref = ref<EchartsUIType>();
const chart3Ref = ref<EchartsUIType>();

const { renderEcharts: renderChart1 } = useEcharts(chart1Ref);
const { renderEcharts: renderChart2 } = useEcharts(chart2Ref);
const { renderEcharts: renderChart3 } = useEcharts(chart3Ref);

const loading = ref(false);

// 饼图配置
const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de'];

function renderPieChart(
  renderFn: (options: any) => void,
  title: string,
  data: PieChartDataItem[]
) {
  renderFn({
    color: colors,
    title: {
      text: title,
      left: 'center',
      top: 10,
      textStyle: {
        fontSize: 14,
        fontWeight: 'normal',
      },
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      bottom: 10,
      left: 'center',
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
        },
        data: data,
      },
    ],
  });
}

// 加载饼图数据
async function loadChartData() {
  loading.value = true;
  try {
    const [chart1Data, chart2Data, chart3Data] = await Promise.all([
      getTimelyTestChartApi(props.version),
      getTestStatusChartApi(props.version),
      getVerifyStatusChartApi(props.version),
    ]);

    renderPieChart(renderChart1, '及时转测情况', chart1Data.seriesData);
    renderPieChart(renderChart2, '需求转测情况', chart2Data.seriesData);
    renderPieChart(renderChart3, '已转测需求验证情况', chart3Data.seriesData);
  } catch (error) {
    console.error('加载饼图数据失败:', error);
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.version,
  () => {
    loadChartData();
  }
);

onMounted(() => {
  loadChartData();
});
</script>

<template>
  <div v-loading="loading" class="pie-charts grid grid-cols-3 gap-4">
    <div class="chart-card rounded-lg border bg-white p-4 shadow-sm">
      <EchartsUI ref="chart1Ref" class="h-64 w-full" />
    </div>
    <div class="chart-card rounded-lg border bg-white p-4 shadow-sm">
      <EchartsUI ref="chart2Ref" class="h-64 w-full" />
    </div>
    <div class="chart-card rounded-lg border bg-white p-4 shadow-sm">
      <EchartsUI ref="chart3Ref" class="h-64 w-full" />
    </div>
  </div>
</template>

<style scoped>
.pie-charts {
  margin-bottom: 16px;
}
</style>