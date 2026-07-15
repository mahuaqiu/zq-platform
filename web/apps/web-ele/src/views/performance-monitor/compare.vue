<script setup lang="ts">
import type { ChartSeries, CompareTag, SummaryRow } from './types';

import type {
  CompareDataResponse,
  ExportTaskCreate,
  PerformanceData,
  PerformanceVersion,
} from '#/api/core/performance-monitor';

import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import * as echarts from 'echarts';
import { ElButton, ElEmpty, ElMessage, ElTag } from 'element-plus';

import {
  createCompareTag,
  createExportTask,
  deleteCompareTag,
  getCompareData,
  getCompareTags,
  getVersions,
  queryAdvancedMetrics,
} from '#/api/core/performance-monitor';
import { getMetricLabel } from './hwinfo-metrics-config';

import AddTagDialog from './components/AddTagDialog.vue';
import CompareChartPanel from './components/CompareChartPanel.vue';
import CompareSummaryTable from './components/CompareSummaryTable.vue';
import ExportProgressDialog from './components/ExportProgressDialog.vue';
import MetricSelector from './components/MetricSelector.vue';
import MetricSearchPopup from './components/MetricSearchPopup.vue';
import VersionSelector from './components/VersionSelector.vue';
import { VERSION_COLORS } from './types';

const route = useRoute();

// 版本列表
const versions = ref<PerformanceVersion[]>([]);
const selectedVersionIds = ref<string[]>([]);
const loadingVersions = ref(false);

// 对比数据
const compareData = ref<CompareDataResponse>({ versions: [] });
const loadingCompare = ref(false);

// dataZoom slider 独立容器（用于 CPU/GPU 双图表）
const dataZoomSliderRef = ref<HTMLDivElement | null>(null);
let dataZoomSliderChart: echarts.ECharts | null = null;

// dataZoom slider 独立容器（用于其他指标单图表）
const singleMetricSliderRef = ref<HTMLDivElement | null>(null);
let singleMetricSliderChart: echarts.ECharts | null = null;

// 共享的 dataZoom 范围状态（切换指标时保持）
const sharedDataZoomRange = ref({ start: 0, end: 100 });

// 当前指标
const currentMetric = ref('cpu_usage');
const metricOptions = [
  { key: 'cpu_usage', label: 'CPU' },
  { key: 'gpu_usage', label: 'GPU' },
  { key: 'memory_usage', label: '内存' },
  { key: 'commit_memory', label: '提交内存' },
];

// 更多指标弹窗
const showMorePopup = ref(false);

// HWiNFO 指标状态
const hwinfoMetricKey = ref<string>('');
const hwinfoMetricInfo = ref<{ displayName: string; unit: string }>({ displayName: '', unit: '' });
const hwinfoChartData = ref<ChartSeries[]>([]);
const loadingHwinfoMetric = ref(false);

// 对比标签
const compareTags = ref<CompareTag[]>([]);
const loadingTags = ref(false);
const showAddTagDialog = ref(false);

// 版本颜色映射
function getVersionColor(index: number): string {
  return VERSION_COLORS[index % VERSION_COLORS.length] || '#67c23a';
}

// 判断是否是 CPU/GPU 指标（需要显示两个图表）
const isCpuOrGpuMetric = computed(() => {
  return currentMetric.value === 'cpu_usage' || currentMetric.value === 'gpu_usage';
});

function sampleTimeSeconds(data: PerformanceData): number {
  return (data.elapsed_ms ?? data.relative_time * 1000) / 1000;
}

function systemMetricValue(data: PerformanceData, metric: 'cpu_usage' | 'gpu_usage'): number | null {
  if (metric === 'cpu_usage') {
    return data.system_metrics?.cpu_percent ?? data.cpu_usage ?? null;
  }
  return data.system_metrics?.gpu_percent ?? data.gpu_usage ?? null;
}

// 系统数据图表（归一化：每条线从0开始）
const systemChartSeries = computed<ChartSeries[]>(() => {
  const result: ChartSeries[] = [];
  const metricField = currentMetric.value as keyof PerformanceData;

  compareData.value.versions.forEach((v, i) => {
    const systemData: Array<{ time: number; value: number | null }> = [];

    v.collects.forEach((c) => {
      c.data.forEach((d) => {
        systemData.push({
          time: sampleTimeSeconds(d),
          value: isCpuOrGpuMetric.value
            ? systemMetricValue(d, currentMetric.value as 'cpu_usage' | 'gpu_usage')
            : (d[metricField] as number) || 0,
        });
      });
    });

    systemData.sort((a, b) => a.time - b.time);
    const startTime = systemData.at(0)?.time ?? 0;

    const normalizedData = systemData.map(d => ({
      time: d.time - startTime,
      value: d.value,
    }));

    result.push({
      name: v.version.name,
      data: normalizedData,
      color: getVersionColor(i),
    });
  });

  return result;
});

// 进程数据图表（仅 CPU/GPU）
const processChartSeries = computed<ChartSeries[]>(() => {
  if (!isCpuOrGpuMetric.value) return [];

  const result: ChartSeries[] = [];

  compareData.value.versions.forEach((v, i) => {
    const processData: Array<{ time: number; value: number }> = [];

    v.collects.forEach((c) => {
      c.data.forEach((d) => {
        const values = d.target_processes?.map((p) =>
          currentMetric.value === 'cpu_usage' ? (p.total_cpu || 0) : (p.total_gpu || 0),
        ) || [];
        // CPU 多进程可加总；GPU 接近任务管理器，用 max，避免高于系统
        const processValue = values.length
          ? (currentMetric.value === 'cpu_usage' ? values.reduce((s, v) => s + v, 0) : Math.max(...values, 0))
          : 0;
        processData.push({
          time: sampleTimeSeconds(d),
          value: processValue,
        });
      });
    });

    processData.sort((a, b) => a.time - b.time);
    const startTime = processData.at(0)?.time ?? 0;

    const normalizedData = processData.map(d => ({
      time: d.time - startTime,
      value: d.value,
    }));

    result.push({
      name: v.version.name,
      data: normalizedData,
      color: getVersionColor(i),
    });
  });

  return result;
});

// 图表标题
const systemChartTitle = computed(() => {
  // HWiNFO 指标
  if (currentMetric.value === 'hwinfo') {
    const englishName = hwinfoMetricInfo.value.displayName || hwinfoMetricKey.value;
    const chineseName = getMetricLabel(hwinfoMetricKey.value);
    const unit = hwinfoMetricInfo.value.unit;
    let name = chineseName !== hwinfoMetricKey.value
      ? `${chineseName}（${englishName}）`
      : englishName;
    if (unit) {
      name = `${name} (${unit})`;
    }
    return name;
  }

  const metric = metricOptions.find(m => m.key === currentMetric.value);
  const label = metric?.label || currentMetric.value;
  if (isCpuOrGpuMetric.value) {
    return `${label} - 系统使用率 (%)`;
  }
  if (currentMetric.value.includes('memory')) {
    return `${label} (GB)`;
  }
  return `${label} (%)`;
});

const processChartTitle = computed(() => {
  const metric = metricOptions.find(m => m.key === currentMetric.value);
  const label = metric?.label || currentMetric.value;
  return `${label} - 进程使用率 (%)`;
});

// 判断是否使用 HWiNFO 数据
const isHwinfoMetric = computed(() => currentMetric.value === 'hwinfo');

// 最终图表数据（HWiNFO 或系统数据）
const finalSystemChartSeries = computed(() => {
  if (isHwinfoMetric.value) return hwinfoChartData.value;
  return systemChartSeries.value;
});

// 处理选择 HWiNFO 指标
async function handleHwinfoMetricSelect(metricKey: string) {
  if (compareData.value.versions.length === 0) {
    ElMessage.warning('请先进行版本对比');
    return;
  }

  loadingHwinfoMetric.value = true;
  hwinfoMetricKey.value = metricKey;
  hwinfoMetricInfo.value = { displayName: '', unit: '' };

  try {
    // 为每个版本获取 HWiNFO 指标数据
    const seriesList: ChartSeries[] = [];

    for (const [index, v] of compareData.value.versions.entries()) {
      // 获取该版本的时间范围（从 compareData 中获取，用于筛选 HWiNFO 数据）
      const versionDataPoints = v.collects.flatMap(c => c.data);
      versionDataPoints.sort((a, b) => sampleTimeSeconds(a) - sampleTimeSeconds(b));

      if (versionDataPoints.length === 0) continue;

      // 该版本的时间范围
      const firstDataPoint = versionDataPoints.at(0);
      const lastDataPoint = versionDataPoints.at(-1);
      if (!firstDataPoint || !lastDataPoint) continue;
      const versionStartTime = sampleTimeSeconds(firstDataPoint);
      const versionEndTime = sampleTimeSeconds(lastDataPoint);

      // 遍历每个采集获取 HWiNFO 数据
      const allData: Array<{ time: number; value: number }> = [];

      for (const c of v.collects) {
        const collectId = c.collect.id;
        if (!collectId) continue;

        const result = await queryAdvancedMetrics({
          collect_id: collectId,
          metric_keys: [metricKey],
        });

        const metricData = result.metrics[metricKey];
        if (metricData?.data) {
          // 保存指标信息（使用第一个版本的信息）
          if (index === 0 && !hwinfoMetricInfo.value.displayName) {
            hwinfoMetricInfo.value = {
              displayName: metricData.display_name || metricKey,
              unit: metricData.unit || '',
            };
          }

          // 根据该版本的时间范围筛选 HWiNFO 数据
          metricData.data.forEach(d => {
            if (d.relative_time >= versionStartTime && d.relative_time <= versionEndTime) {
              allData.push({ time: d.relative_time, value: d.value });
            }
          });
        }
      }

      // 按时间排序并归一化（从该版本的起始时间开始）
      allData.sort((a, b) => a.time - b.time);
      const normalizedData = allData.map(d => ({
        time: d.time - versionStartTime,
        value: d.value,
      }));

      // 只有有数据才添加到 seriesList
      if (normalizedData.length > 0) {
        seriesList.push({
          name: v.version.name,
          data: normalizedData,
          color: getVersionColor(index),
        });
      }
    }

    hwinfoChartData.value = seriesList;
    currentMetric.value = 'hwinfo';

    if (seriesList.length === 0) {
      ElMessage.warning('未获取到指标数据');
    } else {
      ElMessage.success(`已加载指标: ${hwinfoMetricInfo.value.displayName || metricKey}`);
    }
  } catch (error) {
    console.error('获取 HWiNFO 指标数据失败:', error);
    ElMessage.error('获取指标数据失败');
  } finally {
    loadingHwinfoMetric.value = false;
  }
}

// 获取第一个采集ID（用于 MetricSearchPopup 加载指标列表）
const firstCollectId = computed(() => {
  if (compareData.value.versions.length === 0) return '';
  return compareData.value.versions[0]?.collects[0]?.collect.id || '';
});

// 数据摘要（根据标签区间计算）
const summaryData = computed<SummaryRow[]>(() => {
  // 获取冲高和稳态标签
  const peakTag = compareTags.value.find(t => t.type === 'peak');
  const stableTag = compareTags.value.find(t => t.type === 'stable');

  // HWiNFO 指标特殊处理
  if (currentMetric.value === 'hwinfo' && hwinfoChartData.value.length > 0) {
    return hwinfoChartData.value.map((series) => {
      // HWiNFO 数据已经是归一化的，可以直接用标签时间过滤
      const peakData = peakTag
        ? series.data.filter(d => d.time >= peakTag.start_time && d.time <= peakTag.end_time)
        : [];
      const stableData = stableTag
        ? series.data.filter(d => d.time >= stableTag.start_time && d.time <= stableTag.end_time)
        : [];

      const peakValues = peakData.map(d => d.value).filter((value): value is number => value !== null);
      const meanValues = stableData.map(d => d.value).filter((value): value is number => value !== null);
      const peakValue = peakValues.length > 0 ? Math.max(...peakValues) : undefined;
      const meanValue = meanValues.length > 0
        ? meanValues.reduce((sum, value) => sum + value, 0) / meanValues.length
        : undefined;

      return {
        version_name: series.name,
        color: series.color,
        peak_hwinfo: peakTag ? peakValue : undefined,
        mean_hwinfo: stableTag ? meanValue : undefined,
      };
    });
  }

  // 系统指标处理
  return compareData.value.versions.map((v, i) => {
    // 获取所有数据并按时间排序
    const allData = v.collects.flatMap((c) => c.data);
    allData.sort((a, b) => a.relative_time - b.relative_time);

    // 找到该版本的起始时间（用于将归一化的标签时间转换为原始时间）
    const versionStartTime = allData.at(0)?.relative_time ?? 0;

    // 辅助函数：获取区间内的数据（标签时间是归一化的，需要转换为原始时间）
    const getIntervalData = (normalizedStart: number, normalizedEnd: number) => {
      // 将归一化时间转换为原始时间
      const originalStart = normalizedStart + versionStartTime;
      const originalEnd = normalizedEnd + versionStartTime;
      return allData.filter(d => d.relative_time >= originalStart && d.relative_time <= originalEnd);
    };

    // 辅助函数：计算区间内系统指标的最大值
    const getIntervalPeak = (data: PerformanceData[], field: keyof PerformanceData) => {
      if (data.length === 0) return 0;
      return Math.max(...data.map(d => (d[field] as number) || 0));
    };

    // 辅助函数：计算区间内进程指标的最大值
    const getIntervalProcessPeak = (data: PerformanceData[], field: 'total_cpu' | 'total_gpu') => {
      if (data.length === 0) return 0;
      return Math.max(...data.map((d) => {
        const values = d.target_processes?.map((p) => p[field] || 0) || [];
        if (!values.length) return 0;
        // GPU 用 max；CPU 仍可加总后取区间峰值
        return field === 'total_gpu' ? Math.max(...values, 0) : values.reduce((s, v) => s + v, 0);
      }));
    };

    // 辅助函数：计算区间内系统指标的平均值
    const getIntervalMean = (data: PerformanceData[], field: keyof PerformanceData) => {
      if (data.length === 0) return 0;
      const values = data.map(d => (d[field] as number) || 0);
      return values.reduce((a, b) => a + b, 0) / values.length;
    };

    // 辅助函数：计算区间内进程指标的平均值
    const getIntervalProcessMean = (data: PerformanceData[], field: 'total_cpu' | 'total_gpu') => {
      if (data.length === 0) return 0;
      const values = data.map((d) => {
        const list = d.target_processes?.map((p) => p[field] || 0) || [];
        if (!list.length) return 0;
        return field === 'total_gpu' ? Math.max(...list, 0) : list.reduce((s, v) => s + v, 0);
      });
      return values.reduce((a, b) => a + b, 0) / values.length;
    };

    // 冲高区间数据（标签时间是归一化的）
    const peakData = peakTag ? getIntervalData(peakTag.start_time, peakTag.end_time) : [];
    // 稳态区间数据
    const stableData = stableTag ? getIntervalData(stableTag.start_time, stableTag.end_time) : [];

    return {
      version_name: v.version.name,
      color: getVersionColor(i),
      // 冲高区间最高值
      peak_cpu: peakTag ? getIntervalPeak(peakData, 'cpu_usage') : undefined,
      peak_process_cpu: peakTag ? getIntervalProcessPeak(peakData, 'total_cpu') : undefined,
      peak_gpu: peakTag ? getIntervalPeak(peakData, 'gpu_usage') : undefined,
      peak_process_gpu: peakTag ? getIntervalProcessPeak(peakData, 'total_gpu') : undefined,
      peak_memory_usage: peakTag ? getIntervalPeak(peakData, 'memory_usage') : undefined,
      peak_commit_memory: peakTag ? getIntervalPeak(peakData, 'commit_memory') : undefined,
      // 稳态区间平均值
      mean_cpu: stableTag ? getIntervalMean(stableData, 'cpu_usage') : undefined,
      mean_process_cpu: stableTag ? getIntervalProcessMean(stableData, 'total_cpu') : undefined,
      mean_gpu: stableTag ? getIntervalMean(stableData, 'gpu_usage') : undefined,
      mean_process_gpu: stableTag ? getIntervalProcessMean(stableData, 'total_gpu') : undefined,
      mean_memory_usage: stableTag ? getIntervalMean(stableData, 'memory_usage') : undefined,
      mean_commit_memory: stableTag ? getIntervalMean(stableData, 'commit_memory') : undefined,
    };
  });
});

// 初始化独立的 dataZoom slider（用于 CPU/GPU 双图表联动）
function initDataZoomSlider() {
  if (!dataZoomSliderRef.value || !isCpuOrGpuMetric.value) return;

  // 销毁旧图表
  if (dataZoomSliderChart) {
    dataZoomSliderChart.dispose();
  }

  dataZoomSliderChart = echarts.init(dataZoomSliderRef.value);

  // 获取时间范围
  const allTimes = systemChartSeries.value.flatMap(s => s.data.map(d => d.time));
  const minTime = allTimes.length > 0 ? Math.min(...allTimes) : 0;
  const maxTime = allTimes.length > 0 ? Math.max(...allTimes) : 100;

  const option: echarts.EChartsOption = {
    grid: {
      left: 60,
      right: 40,
      top: 5,
      bottom: 5,
    },
    xAxis: {
      type: 'value',
      min: minTime,
      max: maxTime,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        formatter: (value: number) => `${Math.round(value)}秒`,
        color: '#666',
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      show: false,
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        xAxisIndex: 0,
        start: sharedDataZoomRange.value.start,
        end: sharedDataZoomRange.value.end,
        height: 20,
        bottom: 5,
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
    ],
    series: [],
  };

  dataZoomSliderChart.setOption(option);

  // 监听 dataZoom 变化，保存范围状态
  dataZoomSliderChart.on('datazoom', (params: any) => {
    sharedDataZoomRange.value = {
      start: params.start || 0,
      end: params.end || 100,
    };
  });

  // 加入图表组实现联动
  dataZoomSliderChart.group = 'cpu-gpu-compare';
  echarts.connect('cpu-gpu-compare');
}

// 初始化独立的时间范围选择 slider（用于其他指标单图表）
function initSingleMetricSlider() {
  if (!singleMetricSliderRef.value) return;

  // 销毁旧图表
  if (singleMetricSliderChart) {
    singleMetricSliderChart.dispose();
  }

  singleMetricSliderChart = echarts.init(singleMetricSliderRef.value);

  // 获取时间范围
  const allTimes = finalSystemChartSeries.value.flatMap(s => s.data.map(d => d.time));
  const minTime = allTimes.length > 0 ? Math.min(...allTimes) : 0;
  const maxTime = allTimes.length > 0 ? Math.max(...allTimes) : 100;

  const option: echarts.EChartsOption = {
    grid: {
      left: 60,
      right: 40,
      top: 5,
      bottom: 5,
    },
    xAxis: {
      type: 'value',
      min: minTime,
      max: maxTime,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        formatter: (value: number) => `${Math.round(value)}秒`,
        color: '#666',
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      show: false,
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        xAxisIndex: 0,
        start: sharedDataZoomRange.value.start,
        end: sharedDataZoomRange.value.end,
        height: 20,
        bottom: 5,
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
    ],
    series: [],
  };

  singleMetricSliderChart.setOption(option);

  // 监听 dataZoom 变化，保存范围状态
  singleMetricSliderChart.on('datazoom', (params: any) => {
    sharedDataZoomRange.value = {
      start: params.start || 0,
      end: params.end || 100,
    };
  });

  // 加入图表组实现联动
  singleMetricSliderChart.group = 'single-metric-compare';
  echarts.connect('single-metric-compare');
}

// 监听数据变化，重新初始化 slider
watch([systemChartSeries, isCpuOrGpuMetric, finalSystemChartSeries], () => {
  if (compareData.value.versions.length > 0) {
    // 延迟初始化，确保 DOM 已渲染
    setTimeout(() => {
      if (isCpuOrGpuMetric.value) {
        initDataZoomSlider();
      } else {
        initSingleMetricSlider();
      }
    }, 100);
  }
}, { immediate: true });

onMounted(async () => {
  await fetchVersions();

  // 优先从 sessionStorage 读取（页面切换恢复），其次从 URL 参数读取
  const storedVersionIds = sessionStorage.getItem('compare_version_ids');
  const urlVersionIds = route.query.version_ids as string;

  const versionIds = storedVersionIds || urlVersionIds;
  if (versionIds) {
    selectedVersionIds.value = versionIds.split(',');
    await handleCompare();
  }
});

onUnmounted(() => {
  if (dataZoomSliderChart) {
    dataZoomSliderChart.dispose();
  }
  if (singleMetricSliderChart) {
    singleMetricSliderChart.dispose();
  }
});

// 获取版本列表（不需要 device_id）
async function fetchVersions() {
  loadingVersions.value = true;
  try {
    const result = await getVersions();
    versions.value = result.items;
  } catch {
    ElMessage.error('获取版本列表失败');
  } finally {
    loadingVersions.value = false;
  }
}

// 开始对比
async function handleCompare() {
  if (selectedVersionIds.value.length < 2) {
    ElMessage.warning('请至少选择2个版本进行对比');
    return;
  }

  loadingCompare.value = true;
  try {
    const result = await getCompareData(selectedVersionIds.value);
    compareData.value = result;

    // 保存对比状态到 sessionStorage，用于页面切换恢复
    sessionStorage.setItem('compare_version_ids', selectedVersionIds.value.join(','));

    // 加载对比标签
    await fetchCompareTags();
  } catch {
    ElMessage.error('获取对比数据失败');
  } finally {
    loadingCompare.value = false;
  }
}

// 获取对比标签
async function fetchCompareTags() {
  loadingTags.value = true;
  try {
    const result = await getCompareTags();
    compareTags.value = result.items;
  } catch (error) {
    console.error('获取对比标签失败', error);
    compareTags.value = [];
  } finally {
    loadingTags.value = false;
  }
}

// 删除对比标签
async function handleRemoveTag(tagId: string) {
  try {
    await deleteCompareTag(tagId);
    ElMessage.success('标签删除成功');
    await fetchCompareTags();
  } catch {
    ElMessage.error('删除标签失败');
  }
}

// 添加对比标签
function handleAddTag(data: {
  end_time: number;
  name: string;
  note?: string;
  start_time: number;
  type: 'peak' | 'stable';
}) {
  createCompareTag(data)
    .then(() => {
      ElMessage.success('标签添加成功');
      fetchCompareTags();
    })
    .catch(() => {
      ElMessage.error('添加标签失败');
    });
  showAddTagDialog.value = false;
}

// 计算图表数据的最大时间（用于限制标签输入范围）
const maxChartTime = computed(() => {
  const allTimes = systemChartSeries.value.flatMap(s => s.data.map(d => d.time));
  return allTimes.length > 0 ? Math.max(...allTimes) : 0;
});

// 导出相关状态
const showExportDialog = ref(false);
const exportTaskId = ref('');
const isExporting = ref(false);

// 导出报告
async function handleExport() {
  if (selectedVersionIds.value.length < 2) {
    ElMessage.warning('请至少选择2个版本');
    return;
  }

  if (compareData.value.versions.length === 0) {
    ElMessage.warning('请先进行版本对比');
    return;
  }

  isExporting.value = true;

  try {
    const params: ExportTaskCreate = {
      version_ids: selectedVersionIds.value.join(','),
      metric: currentMetric.value as 'cpu_usage' | 'gpu_usage' | 'memory_usage' | 'commit_memory' | 'hwinfo',
      hwinfo_key: currentMetric.value === 'hwinfo' ? hwinfoMetricKey.value : undefined,
    };

    const result = await createExportTask(params);

    if ('task_id' in result) {
      exportTaskId.value = result.task_id;
      showExportDialog.value = true;
    }
  } catch (error: any) {
    ElMessage.error(error.message || '创建导出任务失败');
  } finally {
    isExporting.value = false;
  }
}

// 注意：用户需要手动点击"开始对比"按钮，不自动触发
</script>

<template>
  <div class="version-compare">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <h3>版本对比</h3>
      <VersionSelector
        :versions="versions"
        :selected-ids="selectedVersionIds"
        @update:selected-ids="selectedVersionIds = $event"
      />
      <div class="action-buttons">
        <ElButton
          type="success"
          :disabled="selectedVersionIds.length < 2"
          @click="handleCompare"
        >
          开始对比
        </ElButton>
        <ElButton type="warning" :loading="isExporting" @click="handleExport">
          导出报告
        </ElButton>
      </div>
    </div>

    <!-- 导出进度弹窗 -->
    <ExportProgressDialog
      :visible="showExportDialog"
      :task-id="exportTaskId"
      @update:visible="showExportDialog = $event"
    />

    <!-- 指标选择器和标签区域 -->
    <div class="metric-bar" v-if="compareData.versions.length > 0">
      <MetricSelector
        :current-metric="currentMetric"
        @change="currentMetric = $event"
        @more="showMorePopup = true"
      />
      <MetricSearchPopup
        :visible="showMorePopup"
        :collect-id="firstCollectId"
        @update:visible="showMorePopup = $event"
        @select="handleHwinfoMetricSelect"
      />
      <!-- 标签列表 -->
      <div class="tag-area">
        <ElTag
          v-for="tag in compareTags"
          :key="tag.id"
          :type="tag.type === 'peak' ? 'danger' : 'success'"
          effect="plain"
          closable
          @close="handleRemoveTag(tag.id)"
        >
          {{ tag.name }}（{{ tag.type === 'peak' ? '冲高' : '稳态' }}: {{ tag.start_time }}s-{{ tag.end_time }}s）
        </ElTag>
        <ElButton size="small" type="primary" plain @click="showAddTagDialog = true">
          +标签
        </ElButton>
      </div>
    </div>

    <!-- 添加标签弹窗 -->
    <AddTagDialog
      :visible="showAddTagDialog"
      :max-time="maxChartTime"
      @update:visible="showAddTagDialog = $event"
      @submit="handleAddTag"
    />

    <!-- 图表区 - CPU/GPU 显示两个图表，其他指标显示一个 -->
    <div v-if="compareData.versions.length > 0" class="charts-area">
      <!-- CPU/GPU: 双图表布局 -->
      <div v-if="isCpuOrGpuMetric" class="dual-charts">
        <CompareChartPanel
          :title="systemChartTitle"
          :series="systemChartSeries"
          :tags="compareTags"
          :loading="loadingCompare"
          :current-metric="currentMetric"
          data-zoom-type="inside"
          chart-group="cpu-gpu-compare"
          :data-zoom-start="sharedDataZoomRange.start"
          :data-zoom-end="sharedDataZoomRange.end"
        />
        <!-- dataZoom slider 放在两个图表中间 -->
        <div class="datazoom-slider-container">
          <div class="slider-label">时间范围选择</div>
          <div ref="dataZoomSliderRef" class="slider-chart"></div>
        </div>
        <CompareChartPanel
          :title="processChartTitle"
          :series="processChartSeries"
          :tags="compareTags"
          :loading="loadingCompare"
          :current-metric="currentMetric"
          data-zoom-type="inside"
          chart-group="cpu-gpu-compare"
          :data-zoom-start="sharedDataZoomRange.start"
          :data-zoom-end="sharedDataZoomRange.end"
        />
      </div>
      <!-- 其他指标/HWiNFO: 单图表 + 独立时间范围选择 -->
      <div v-else class="single-chart-with-slider">
        <CompareChartPanel
          :title="systemChartTitle"
          :series="finalSystemChartSeries"
          :tags="compareTags"
          :loading="loadingCompare || loadingHwinfoMetric"
          :current-metric="currentMetric"
          :hwinfo-unit="hwinfoMetricInfo.unit"
          data-zoom-type="inside"
          chart-group="single-metric-compare"
          :data-zoom-start="sharedDataZoomRange.start"
          :data-zoom-end="sharedDataZoomRange.end"
        />
        <!-- 独立的时间范围选择卡片 -->
        <div class="datazoom-slider-container">
          <div class="slider-label">时间范围选择</div>
          <div ref="singleMetricSliderRef" class="slider-chart"></div>
        </div>
      </div>
    </div>

    <!-- 底部面板 -->
    <div class="bottom-panel" v-if="compareData.versions.length > 0">
      <CompareSummaryTable :summary-data="summaryData" :current-metric="currentMetric" :hwinfo-unit="hwinfoMetricInfo.unit" />
    </div>

    <!-- 无数据提示 -->
    <ElEmpty
      v-if="selectedVersionIds.length < 2"
      description="请选择至少2个版本进行对比"
    />
  </div>
</template>

<style scoped>
.version-compare {
  padding: 16px;
  background: #f5f5f5;
  min-height: 100vh;
}

.control-bar {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.control-bar h3 {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.action-buttons {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.metric-bar {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.tag-area {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
}

.charts-area {
  margin-bottom: 12px;
}

.dual-charts {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dual-charts .compare-chart-panel {
  width: 100%;
}

.single-chart-with-slider {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.datazoom-slider-container {
  background: #fff;
  border-radius: 8px;
  padding: 12px 16px;
}

.slider-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.slider-chart {
  height: 30px;
}

.bottom-panel {
  display: flex;
  gap: 16px;
  margin-top: 12px;
}

.bottom-panel > :first-child {
  flex: 1;
}
</style>
