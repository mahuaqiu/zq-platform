<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue';
import { ElInput, ElSelect, ElButton, ElOption } from 'element-plus';
import * as echarts from 'echarts';
import { getMetricMappings, queryAdvancedMetrics } from '#/api/core/performance-monitor';
import type { MetricMappingResponse, AdvancedMetricsResponse, MetricTimeSeries } from '#/api/core/performance-monitor';

interface Props {
  collectId: string;
}

const props = defineProps<Props>();

// 默认折叠
const isExpanded = ref(false);
const keyword = ref('');
const category = ref('all');
const displayMode = ref('card');
const results = ref<MetricMappingResponse[]>([]);
const selectedMetrics = ref<string[]>([]);
const metricsData = ref<AdvancedMetricsResponse | null>(null);
const loading = ref(false);
const chartRefs = ref<Map<string, HTMLDivElement>>(new Map());
const chartInstances = ref<Map<string, echarts.ECharts>>(new Map());

// 展开/折叠
function toggleExpand() {
  isExpanded.value = !isExpanded.value;
}

async function handleSearch() {
  loading.value = true;
  const cat = category.value === 'all' ? undefined : category.value;
  const res = await getMetricMappings(keyword.value, cat);
  results.value = res;
  loading.value = false;
}

async function handleShowMetric(hwinfoKey: string) {
  if (selectedMetrics.value.includes(hwinfoKey)) {
    selectedMetrics.value = selectedMetrics.value.filter(k => k !== hwinfoKey);
  } else {
    selectedMetrics.value.push(hwinfoKey);
  }

  if (selectedMetrics.value.length > 0) {
    loading.value = true;
    metricsData.value = await queryAdvancedMetrics({
      collect_id: props.collectId,
      metric_keys: selectedMetrics.value,
    });
    loading.value = false;

    // 渲染图表
    await nextTick();
    renderCharts();
  } else {
    metricsData.value = null;
    // 清理图表实例
    chartInstances.value.forEach(chart => chart.dispose());
    chartInstances.value.clear();
    chartRefs.value.clear();
  }
}

function isSelected(hwinfoKey: string): boolean {
  return selectedMetrics.value.includes(hwinfoKey);
}

function renderCharts() {
  if (!metricsData.value?.metrics) return;

  Object.entries(metricsData.value.metrics).forEach(([key, ts]) => {
    const chartDiv = chartRefs.value.get(key);
    if (!chartDiv) return;

    // 清理已有实例
    const existingChart = chartInstances.value.get(key);
    if (existingChart) {
      existingChart.dispose();
    }

    // 创建新图表
    const chart = echarts.init(chartDiv);
    const timeData = ts.data.map(d => d.relative_time);
    const valueData = ts.data.map(d => d.value);

    chart.setOption({
      grid: { left: 40, right: 20, top: 10, bottom: 25 },
      xAxis: {
        type: 'category',
        data: timeData,
        axisLabel: { fontSize: 10, color: '#999' },
        axisLine: { lineStyle: { color: '#ddd' } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { fontSize: 10, color: '#999' },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#eee', type: 'dashed' } },
      },
      series: [{
        type: 'line',
        data: valueData,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
        smooth: true,
        symbol: 'none',
      }],
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const time = params[0]?.axisValue;
          const value = params[0]?.value;
          return `时间: ${time}秒<br/>值: ${value?.toFixed(2)} ${ts.unit || ''}`;
        },
      },
    });

    chartInstances.value.set(key, chart);
  });
}

// 监听窗口大小变化，调整图表尺寸
onMounted(() => {
  window.addEventListener('resize', () => {
    chartInstances.value.forEach(chart => chart.resize());
  });
});
</script>

<template>
  <div class="advanced-metrics">
    <div class="metrics-header">
      <h3 class="metrics-title" @click="toggleExpand">
        <span class="expand-icon">{{ isExpanded ? '▼' : '▶' }}</span>
        高级指标 (hwinfo_raw 200+传感器)
      </h3>
      <div v-if="isExpanded" class="metrics-controls">
        <ElInput v-model="keyword" placeholder="搜索指标（如：CPU核心温度）" style="width: 220px" clearable />
        <ElSelect v-model="category" style="width: 100px">
          <ElOption label="全部分类" value="all" />
          <ElOption label="系统" value="system" />
          <ElOption label="硬件" value="hardware" />
          <ElOption label="网络" value="network" />
        </ElSelect>
        <ElSelect v-model="displayMode" style="width: 100px">
          <ElOption label="卡片模式" value="card" />
          <ElOption label="图表模式" value="chart" />
        </ElSelect>
        <ElButton type="primary" @click="handleSearch" :loading="loading">搜索</ElButton>
      </div>
    </div>

    <!-- 折叠提示 -->
    <div v-if="!isExpanded" class="metrics-hint">
      点击展开或输入搜索内容后显示对应的hwinfo指标（共200+传感器数据，默认不显示）
    </div>

    <!-- 搜索结果 -->
    <div v-if="isExpanded && results.length" class="metrics-results">
      <div
        v-for="m in results"
        :key="m.id"
        class="metric-item"
        :class="{ selected: isSelected(m.hwinfo_key) }"
        @click="handleShowMetric(m.hwinfo_key)"
      >
        <span class="metric-name">{{ m.display_name }}</span>
        <span class="metric-key">{{ m.hwinfo_key }}</span>
        <span class="metric-unit" v-if="m.unit">{{ m.unit }}</span>
      </div>
    </div>

    <!-- 已选指标图表 -->
    <div v-if="isExpanded && metricsData && metricsData.metrics" class="metrics-charts">
      <div v-for="[key, ts] in Object.entries(metricsData.metrics)" :key="key" class="metric-chart">
        <div class="chart-header">
          <span class="chart-title">{{ ts.display_name || key }}</span>
          <span class="chart-info">
            最新值: {{ ts.data.length ? ts.data[ts.data.length-1]?.value?.toFixed(2) : '-' }} {{ ts.unit }}
          </span>
        </div>
        <div class="chart-container" :ref="(el) => { if (el) chartRefs.set(key, el as HTMLDivElement) }"></div>
      </div>
    </div>

    <!-- 无结果提示 -->
    <div v-if="isExpanded && !results.length && keyword" class="no-results">
      未找到匹配的指标
    </div>
  </div>
</template>

<style scoped>
.advanced-metrics {
  background: linear-gradient(135deg, #f0f9ff 0%, #e8f4ff 100%);
  border: 1px solid #409eff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
.metrics-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.metrics-title {
  margin: 0;
  color: #409eff;
  font-size: 14px;
  cursor: pointer;
}
.expand-icon {
  margin-right: 5px;
}
.metrics-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}
.metrics-hint {
  margin-top: 8px;
  color: #666;
  font-size: 11px;
  padding: 8px;
  background: white;
  border-radius: 4px;
}
.metrics-results {
  margin-top: 15px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-height: 200px;
  overflow-y: auto;
}
.metric-item {
  background: white;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  gap: 5px;
  align-items: center;
  border: 1px solid #eee;
}
.metric-item.selected {
  border-color: #409eff;
  background: #e8f4ff;
}
.metric-name {
  font-size: 13px;
  color: #333;
}
.metric-key {
  font-size: 11px;
  color: #999;
}
.metric-unit {
  font-size: 11px;
  color: #666;
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 3px;
}
.metrics-charts {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ddd;
}
.metric-chart {
  background: white;
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 10px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.chart-title {
  font-size: 13px;
  color: #333;
  font-weight: bold;
}
.chart-info {
  font-size: 12px;
  color: #666;
}
.chart-container {
  width: 100%;
  height: 120px;
}
.no-results {
  text-align: center;
  color: #999;
  padding: 20px;
}
</style>