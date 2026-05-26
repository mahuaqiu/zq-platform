<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ElSelect, ElOption, ElDialog, ElForm, ElFormItem, ElInput, ElButton, ElDatePicker } from 'element-plus';
import { useRouter } from 'vue-router';
import ChartPanel from './components/ChartPanel.vue';
import Top10Panel from './components/Top10Panel.vue';
import CollectDialog from './components/CollectDialog.vue';
import TimeNavigator from './components/TimeNavigator.vue';
import MetricSelector from './components/MetricSelector.vue';
import MetricSearchPopup from './components/MetricSearchPopup.vue';
import MiniTooltip from './components/MiniTooltip.vue';
import ProcessDetailPanel from './components/ProcessDetailPanel.vue';
import TargetProcessPanel from './components/TargetProcessPanel.vue';
import { getMetricLabel } from './hwinfo-metrics-config';
import {
  getCollectStatus,
  stopCollect,
  getLatestData,
  getCollectData,
  getCollectDataByRange,
  getCollectList,
  getVersions,
  createVersion,
  deleteCollect,
  setCollectProtected,
  getMarkers,
  queryAdvancedMetrics,
} from '#/api/core/performance-monitor';
import { getEnvMachineListApi } from '#/api/core/env-machine';
import type {
  PerformanceData,
  CollectStatus,
  PerformanceCollect,
  PerformanceVersion,
  MarkerResponse,
} from '#/api/core/performance-monitor';
import type { EnvMachine } from '#/api/core/env-machine';
import type { ChartSeries } from './types';

const router = useRouter();

// 设备选择
const deviceId = ref('');
const devices = ref<EnvMachine[]>([]);
const loadingDevices = ref(true);

// 在线设备列表（过滤虚拟设备，虚拟设备无法进行性能采集）
// Windows 和 Linux 设备都可以进行性能采集
const onlineDevices = computed(() =>
  devices.value.filter((d) =>
    (d.status === 'online' || d.status === 'using') && !d.is_virtual,
  ),
);

// 当前选中设备信息
const currentDeviceInfo = computed(() => {
  const device = devices.value.find((d) => d.id === deviceId.value);
  return device ? { ip: device.ip, status: device.status, device_type: device.device_type } : undefined;
});

// 采集状态
const collectStatus = ref<CollectStatus>({ is_collecting: false });
const currentCollectId = ref('');

// 采集弹窗
const showCollectDialog = ref(false);

// 性能数据
const performanceData = ref<PerformanceData[]>([]);
const historyData = ref<PerformanceData[]>([]); // 历史数据用于趋势线

// 标记数据
const markers = ref<MarkerResponse[]>([]);

// 点击图表选中的时刻（用于 TOP10 切换）
const clickedTime = ref<number>(0);

// 采集历史
const collectHistory = ref<PerformanceCollect[]>([]);

// 版本列表
const versions = ref<PerformanceVersion[]>([]);

// 版本标记弹窗
const showVersionDialog = ref(false);
const versionForm = ref({
  name: '',
  selectedCollects: [] as string[],
});

// 历史采集弹窗
const showHistoryDialog = ref(false);
const historySearchDate = ref<[Date, Date] | null>(null);
const historySearchProcess = ref('');
const historyLoading = ref(false);
const historyDeleting = ref<string | null>(null);
const selectedCollectIds = ref<Set<string>>(new Set()); // 多选状态
const batchDeleting = ref(false); // 批量删除loading

// 小 Tooltip 状态（hover 触发）
interface MiniTooltipState {
  position: { x: number; y: number };
  data: PerformanceData | undefined;
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
  containerRect: DOMRect;
  chartKey: string;  // 标识当前hover的图表
}
const miniTooltipState = ref<MiniTooltipState | null>(null);

// 大面板状态（click 触发）
interface DetailPanelState {
  data: PerformanceData;  // 点击的数据点完整数据
  seriesData: { name: string; value: number; color: string; unit: string }[];
  chartType: 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
  chartKey: string;  // 标识是哪个图表（cpu/gpu/memory/commitMemory/handles/hwinfo）
  position?: { x: number; y: number };  // 点击位置
  containerWidth?: number;  // 图表容器宽度
}
const detailPanelState = ref<DetailPanelState | null>(null);
const activeChartKey = ref<string | null>(null);  // 当前激活的图表

// 按钮操作 loading 状态（防止重复点击）
const isStarting = ref(false);
const isStopping = ref(false);

// 过滤后的历史采集列表
const filteredCollectHistory = computed(() => {
  const list = collectHistory.value;
  if (!list.length) return list;

  let filtered = list;

  // 按日期过滤
  if (historySearchDate.value && historySearchDate.value[0] && historySearchDate.value[1]) {
    const startDate = historySearchDate.value[0];
    const endDate = historySearchDate.value[1];
    filtered = filtered.filter((c) => {
      const collectDate = new Date(c.start_time);
      return collectDate >= startDate && collectDate <= endDate;
    });
  }

  // 按进程名模糊搜索
  if (historySearchProcess.value.trim()) {
    const keyword = historySearchProcess.value.trim().toLowerCase();
    filtered = filtered.filter((c) => {
      const processes = c.target_processes || [];
      return processes.some((p) => p.name.toLowerCase().includes(keyword));
    });
  }

  return filtered;
});

// 定时轮询
let pollingTimer: number | null = null;
let isMounted = false; // 组件挂载状态

// 用户选择的时间窗口范围（相对时间，秒）- 由 TimeNavigator 控制
const selectedRelativeTimeRange = ref<[number, number] | null>(null);

// 已加载的数据时间范围（用于判断是否需要动态加载更多数据）
const loadedTimeRange = ref<{ min: number; max: number } | null>(null);

// 总时长（采集记录的完整时长，不受加载范围限制）
const totalDuration = ref<number>(0);

// 正在加载更多数据的标记（避免重复请求）
const isLoadingMoreData = ref(false);

// 根据时间窗口过滤后的数据
const filteredPerformanceData = computed(() => {
  const data = performanceData.value;
  if (!data.length) return data;

  // 如果用户没有选择时间窗口，显示全部数据
  if (!selectedRelativeTimeRange.value) return data;

  const [startTime, endTime] = selectedRelativeTimeRange.value;
  return data.filter((d) => d.relative_time >= startTime && d.relative_time <= endTime);
});

// 迷你趋势线数据（基于时间窗口过滤后的数据，取最后10条）
const historyTrendData = computed(() => {
  return filteredPerformanceData.value.slice(-10);
});

// 进程名显示（采集中状态）
const processNamesDisplay = computed(() => {
  const processes = collectStatus.value.target_processes || [];
  if (processes.length === 0) return '';
  const names = processes.map((p) => p.name.replace('.exe', '').replace('.EXE', ''));
  if (names.length <= 3) return names.join(', ');
  return `${names.slice(0, 3).join(', ')}...+${names.length - 3}`;
});

// 进程 Tooltip 内容（采集中状态）- 使用进程名列表
const processTooltipContent = computed(() => {
  const processes = collectStatus.value.target_processes || [];
  if (processes.length === 0) return '';
  // 显示进程名和PID
  return processes
    .map((p) => {
      const pids = p.pids || [];
      if (pids.length > 0) {
        return `${p.name} PID:${pids.join(',')}`;
      }
      return p.name;
    })
    .join('\n');
});

// 当前选中的指标
type MetricKey = 'cpu' | 'gpu' | 'memory' | 'commitMemory' | 'handles' | 'hwinfo';
const currentMetric = ref<MetricKey>('cpu');
const showMorePopup = ref(false);

// HWiNFO 指标状态
const hwinfoMetricKey = ref<string>(''); // 具体的 HWiNFO 指标 key
const hwinfoMetricData = ref<{ time: number; value: number }[]>([]); // HWiNFO 指标数据
const hwinfoMetricInfo = ref<{ displayName: string; unit: string }>({ displayName: '', unit: '' });

// 处理选择指标（区分 HWiNFO 指标和进程指标）
async function handleHwinfoMetricSelect(metricKey: string) {
  if (!currentCollectId.value) {
    ElMessage.warning('请先选择采集记录');
    return;
  }

  // process_handles 是进程指标，直接切换到 handles 类型
  if (metricKey === 'process_handles') {
    currentMetric.value = 'handles';
    showMorePopup.value = false;
    return;
  }

  // HWiNFO 指标需要查询数据
  try {
    const result = await queryAdvancedMetrics({
      collect_id: currentCollectId.value,
      metric_keys: [metricKey],
      start_time: selectedRelativeTimeRange.value?.[0],
      end_time: selectedRelativeTimeRange.value?.[1],
    });

    const metricData = result.metrics[metricKey];
    if (metricData?.data) {
      // 存储 HWiNFO 指标数据
      hwinfoMetricKey.value = metricKey;
      hwinfoMetricData.value = metricData.data;
      hwinfoMetricInfo.value = {
        displayName: metricData.display_name || metricKey,
        unit: metricData.unit || '',
      };

      // 切换到 hwinfo 指标类型
      currentMetric.value = 'hwinfo';

      ElMessage.success(`已加载指标: ${hwinfoMetricInfo.value.displayName}`);
    } else {
      ElMessage.warning('该指标暂无数据');
    }
  } catch (error) {
    console.error('查询指标数据失败:', error);
    ElMessage.error('查询指标数据失败');
  }
}

// 当前选中设备是否为 Linux
const isLinuxDevice = computed(() => {
  const device = devices.value.find((d) => d.id === deviceId.value);
  return device?.device_type === 'linux';
});

// 所有指标列表（Linux 设备不显示 GPU 指标）
const allMetrics = computed(() => {
  const baseMetrics = [
    { key: 'cpu' as MetricKey, label: 'CPU使用率' },
    // Linux 设备没有 GPU 数据，不显示 GPU 指标
    ...(isLinuxDevice.value ? [] : [{ key: 'gpu' as MetricKey, label: 'GPU使用率' }]),
    { key: 'memory' as MetricKey, label: '进程内存' },
    { key: 'commitMemory' as MetricKey, label: '提交内存' },
    { key: 'handles' as MetricKey, label: '进程句柄' },
  ];

  // 如果选择了 HWiNFO 指标，添加到列表
  if (hwinfoMetricKey.value) {
    const englishName = hwinfoMetricInfo.value.displayName || hwinfoMetricKey.value;
    const chineseName = getMetricLabel(hwinfoMetricKey.value);

    // 如果有中文翻译，显示 "中文（英文）" 格式
    const label = chineseName !== hwinfoMetricKey.value
      ? `${chineseName}（${englishName}）`
      : englishName;

    baseMetrics.push({
      key: 'hwinfo' as MetricKey,
      label,
    });
  }

  return baseMetrics;
});

// 指标 key 映射（MetricSelector 使用 _usage/_memory 后缀，转换为内部 key）
const metricKeyMap: Record<string, MetricKey> = {
  cpu_usage: 'cpu',
  gpu_usage: 'gpu',
  memory_usage: 'memory',
  commit_memory: 'commitMemory',
};

// 指标切换处理
function handleMetricChange(metric: MetricKey | string) {
  // 转换 key（如果是从 MetricSelector 来的）
  const mappedKey = metricKeyMap[metric] || metric;
  currentMetric.value = mappedKey as MetricKey;
}

// 当前图表数据映射
const chartSeriesMap: Record<MetricKey, () => ChartSeries[]> = {
  cpu: () => cpuChartSeries.value,
  gpu: () => gpuChartSeries.value,
  memory: () => memoryChartSeries.value,
  commitMemory: () => commitMemoryChartSeries.value,
  handles: () => handlesChartSeries.value,
  hwinfo: () => hwinfoChartSeries.value,
};

// 当前图表数据
const currentChartSeries = computed<ChartSeries[]>(() => {
  return chartSeriesMap[currentMetric.value]?.() || [];
});

// 当前图表标题（HWiNFO 指标显示中文+单位）
const currentChartTitle = computed(() => {
  if (currentMetric.value === 'hwinfo') {
    const englishName = hwinfoMetricInfo.value.displayName || hwinfoMetricKey.value;
    const chineseName = getMetricLabel(hwinfoMetricKey.value);
    const unit = hwinfoMetricInfo.value.unit;

    // 有中文翻译时显示 "中文（英文）"，否则显示英文
    let name = chineseName !== hwinfoMetricKey.value
      ? `${chineseName}（${englishName}）`
      : englishName;

    // 有单位时添加单位
    if (unit) {
      name = `${name} (${unit})`;
    }
    return name;
  }

  // CPU/GPU/内存/提交内存/句柄加单位
  const metric = allMetrics.value.find(m => m.key === currentMetric.value);
  const baseLabel = metric?.label || currentMetric.value;

  // 添加单位
  if (currentMetric.value === 'cpu' || currentMetric.value === 'gpu') {
    return `${baseLabel} (%)`;
  } else if (currentMetric.value === 'memory') {
    return `${baseLabel} (MB)`;
  } else if (currentMetric.value === 'commitMemory') {
    return `${baseLabel} (MB)`;
  } else if (currentMetric.value === 'handles') {
    return `${baseLabel} (个)`;
  }

  return baseLabel;
});

// 当前图表类型
const currentChartType = computed(() => currentMetric.value);

// TOP10 面板显示条件（仅 CPU/GPU 显示）
const TOP10_METRICS: MetricKey[] = ['cpu', 'gpu'];
const showTop10Panel = computed(() => TOP10_METRICS.includes(currentMetric.value));

// 当前数值显示（基于过滤后的数据）
const currentMetrics = computed(() => {
  const data = filteredPerformanceData.value;
  const latest = data[data.length - 1];
  if (!latest) return null;
  return latest;
});

// 计算实际采集的时间范围
const actualTimeRange = computed(() => {
  if (performanceData.value.length === 0) {
    return undefined;
  }

  const firstData = performanceData.value[0];
  const lastData = performanceData.value[performanceData.value.length - 1];

  if (!firstData || !lastData) {
    return undefined;
  }

  return {
    startTime: new Date(firstData.timestamp),
    endTime: new Date(lastData.timestamp),
  };
});

// 曲线图数据
const cpuChartSeries = computed<ChartSeries[]>(() => {
  const data = filteredPerformanceData.value;
  if (!data.length) return [];
  const systemData = data.map((d) => ({
    time: d.relative_time,
    value: d.cpu_usage || 0,
  }));
  const processData = data.map((d) => {
    const totalCpu =
      d.target_processes?.reduce((sum, p) => sum + p.total_cpu, 0) || 0;
    return { time: d.relative_time, value: totalCpu };
  });
  return [
    { name: '系统', data: systemData, color: '#409eff', unit: '%' },
    { name: '进程', data: processData, color: '#67c23a', unit: '%' },
  ];
});

const gpuChartSeries = computed<ChartSeries[]>(() => {
  const data = filteredPerformanceData.value;
  if (!data.length) return [];
  const systemData = data.map((d) => ({
    time: d.relative_time,
    value: d.gpu_usage || 0,
  }));
  const processData = data.map((d) => {
    const totalGpu =
      d.target_processes?.reduce((sum, p) => sum + (p.total_gpu || 0), 0) || 0;
    return { time: d.relative_time, value: totalGpu };
  });
  return [
    { name: '系统', data: systemData, color: '#409eff', unit: '%' },
    { name: '进程', data: processData, color: '#67c23a', unit: '%' },
  ];
});

// 提交内存图表 - 显示进程提交内存总和（MB）
const commitMemoryChartSeries = computed<ChartSeries[]>(() => {
  const data = filteredPerformanceData.value;
  if (!data.length) return [];
  // 进程提交内存总和（MB）
  const processData = data.map((d) => {
    const totalCommittedMB =
      d.target_processes?.reduce((sum, p) => sum + (p.total_committed_memory || 0), 0) || 0;
    return { time: d.relative_time, value: totalCommittedMB };
  });
  return [
    { name: '提交内存', data: processData, color: '#409eff', unit: 'MB' },
  ];
});

const memoryChartSeries = computed<ChartSeries[]>(() => {
  const data = filteredPerformanceData.value;
  if (!data.length) return [];
  // 显示进程内存总和（MB单位）
  const processData = data.map((d) => {
    const totalMemMB =
      d.target_processes?.reduce((sum, p) => sum + p.total_memory, 0) || 0;
    return { time: d.relative_time, value: totalMemMB };
  });
  return [
    { name: '进程内存', data: processData, color: '#409eff', unit: 'MB' },
  ];
});

// 进程句柄图表 - 显示进程句柄总和
const handlesChartSeries = computed<ChartSeries[]>(() => {
  const data = filteredPerformanceData.value;
  if (!data.length) return [];
  // 显示进程句柄总和
  const processData = data.map((d) => {
    const totalHandles =
      d.target_processes?.reduce((sum, p) => sum + (p.total_handles || 0), 0) || 0;
    return { time: d.relative_time, value: totalHandles };
  });
  return [
    { name: '进程句柄', data: processData, color: '#409eff', unit: '个' },
  ];
});

// 当前采集记录的start_time（用于HWiNFO计算绝对时间）
const currentCollectStartTime = computed(() => {
  // 采集中时优先使用collectStatus的start_time
  if (collectStatus.value.is_collecting && collectStatus.value.start_time) {
    return collectStatus.value.start_time;
  }
  // 否则从collectHistory中查找
  if (!currentCollectId.value) return null;
  const collect = collectHistory.value.find(c => c.id === currentCollectId.value);
  return collect?.start_time || null;
});

// HWiNFO 指标的 rawData（构造符合 PerformanceData 结构的数据）
const hwinfoRawData = computed(() => {
  if (!hwinfoMetricData.value.length || !currentCollectStartTime.value) return [];

  const startTime = new Date(currentCollectStartTime.value).getTime();

  // 根据relative_time计算出绝对时间timestamp
  return hwinfoMetricData.value.map(d => ({
    relative_time: d.relative_time,
    timestamp: new Date(startTime + d.relative_time * 1000).toISOString(),
  })) as PerformanceData[];
});

// HWiNFO 指标图表数据
const hwinfoChartSeries = computed<ChartSeries[]>(() => {
  if (!hwinfoMetricData.value.length) return [];

  // 转换数据格式：relative_time -> time
  const data = hwinfoMetricData.value.map(d => ({
    time: d.relative_time,
    value: d.value,
  }));

  const unit = hwinfoMetricInfo.value.unit || '';
  const englishName = hwinfoMetricInfo.value.displayName || hwinfoMetricKey.value;
  const chineseName = getMetricLabel(hwinfoMetricKey.value);

  // Tooltip 显示简洁名称：优先中文，没有则英文
  const tooltipName = chineseName !== hwinfoMetricKey.value ? chineseName : englishName;

  // 根据 unit 决定 Y 轴单位显示
  let chartUnit = unit;
  if (unit === 'W' || unit === '°C' || unit === 'MHz' || unit === 'V' || unit === 'A') {
    chartUnit = unit; // 保持原单位
  } else if (unit === 'MB/s' || unit === 'GB/s') {
    chartUnit = unit;
  } else if (!unit) {
    chartUnit = ''; // 无单位
  }

  return [
    { name: tooltipName, data, color: '#409eff', unit: chartUnit },
  ];
});

// 获取在线设备列表
async function fetchOnlineDevices() {
  loadingDevices.value = true;
  try {
    // 获取 Windows 和 Linux 设备（虚拟设备会被前端过滤）
    const result = await getEnvMachineListApi({
      page: 1,
      page_size: 100,
    });
    devices.value = result?.items || [];

    // 获取所有设备的采集历史记录（不传 device_id，获取所有记录）
    const collectResult = await getCollectList({
      page: 1,
      page_size: 50,
    });
    const allCollects = collectResult?.items || [];

    // 统计每个设备的采集记录数量
    const deviceCollectCount = new Map<string, number>();
    for (const c of allCollects) {
      const count = deviceCollectCount.get(c.device_id) || 0;
      deviceCollectCount.set(c.device_id, count + 1);
    }

    // 过滤在线设备（排除虚拟设备）
    const onlineDevs = devices.value.filter(
      (d) => (d.status === 'online' || d.status === 'using') && !d.is_virtual,
    );

    // 按采集记录数量降序排序（有采集记录的设备优先）
    const sortedDevices = onlineDevs.sort((a, b) => {
      const countA = deviceCollectCount.get(a.id) || 0;
      const countB = deviceCollectCount.get(b.id) || 0;
      return countB - countA;  // 有记录的排在前面
    });

    // 默认选择第一个设备（优先选择有采集记录的）
    const firstDevice = sortedDevices[0];
    if (firstDevice) {
      deviceId.value = firstDevice.id;
    }
  } catch (error) {
    console.error('获取设备列表失败', error);
    ElMessage.warning('获取设备列表失败，请检查网络');
  } finally {
    loadingDevices.value = false;
  }
}

// 初始化
onMounted(async () => {
  isMounted = true;
  await fetchOnlineDevices();

  await refreshStatus();
  await fetchCollectHistory();

  // 添加全局点击事件监听（用于关闭大面板）
  document.addEventListener('click', handleGlobalClick);

  await fetchVersions();

  // 根据采集状态加载数据
  if (collectStatus.value.is_collecting && collectStatus.value.collect_id) {
    // 正在采集：加载已采集的数据并启动轮询
    currentCollectId.value = collectStatus.value.collect_id!;
    // 先加载已采集的历史数据
    await loadCollectData(collectStatus.value.collect_id!);
    // 然后启动轮询
    startPolling(collectStatus.value.collect_id!);
  } else if (collectHistory.value.length > 0) {
    // 未采集：加载最近的采集数据
    const latestCollect = collectHistory.value[0];
    if (latestCollect?.id) {
      currentCollectId.value = latestCollect.id;
      await loadCollectData(latestCollect.id);
    }
  }
});

onUnmounted(() => {
  isMounted = false;
  stopPolling();

  // 移除全局点击事件监听
  document.removeEventListener('click', handleGlobalClick);
});

async function refreshStatus() {
  if (!isMounted || !deviceId.value) return;
  try {
    const status = await getCollectStatus(deviceId.value);
    if (!isMounted) return; // 异步操作完成后再次检查
    collectStatus.value = status;
    if (status.is_collecting && status.collect_id) {
      currentCollectId.value = status.collect_id;
      startPolling(status.collect_id);
    }
  } catch (error) {
    console.error('获取采集状态失败', error);
  }
}

async function fetchCollectHistory() {
  try {
    const result = await getCollectList({
      device_id: deviceId.value,
      page: 1,
      page_size: 20,
    });
    collectHistory.value = result?.items || [];
  } catch (error) {
    console.error('获取采集历史失败', error);
  }
}

// 加载采集的全部数据（用于历史采集查看）
async function loadCollectData(collectId: string) {
  try {
    // 1. 先获取最新1条数据，确定总时长
    const latestResult = await getLatestData(collectId, 1);
    if (!latestResult?.items?.length) {
      console.warn('采集记录无数据');
      return;
    }

    const durationFromData = latestResult.items[0].relative_time;
    totalDuration.value = durationFromData; // 记录总时长

    // 2. 加载最近12小时的数据（最大显示范围，large模式可处理）
    const maxLoadDuration = 12 * 3600; // 12小时 = 43200秒
    let startTime = 0;
    let endTime = durationFromData;

    if (durationFromData > maxLoadDuration) {
      // 超过12小时：只加载最近12小时的数据
      startTime = durationFromData - maxLoadDuration;
      endTime = durationFromData;
    }

    // 3. 按时间范围请求详细数据
    const result = await getCollectDataByRange(collectId, {
      start_time: startTime,
      end_time: endTime,
    });

    if (result?.items?.length) {
      performanceData.value = result.items;
      historyData.value = result.items.slice(-50);

      // 记录已加载的时间范围
      const loadedStartTime = result.items[0]?.relative_time || startTime;
      const loadedEndTime = result.items[result.items.length - 1]?.relative_time || endTime;
      loadedTimeRange.value = { min: loadedStartTime, max: loadedEndTime };

      // 默认显示最近15分钟（前端过滤）
      const defaultDisplayDuration = 15 * 60;
      if (totalDuration.value > defaultDisplayDuration) {
        selectedRelativeTimeRange.value = [totalDuration.value - defaultDisplayDuration, totalDuration.value];
      } else {
        selectedRelativeTimeRange.value = null;
      }

      // 加载标记
      await loadMarkers();
    }
  } catch (error) {
    console.error('获取采集数据失败', error);
  }
}

// 加载标记数据
async function loadMarkers() {
  if (currentCollectId.value) {
    try {
      const res = await getMarkers(currentCollectId.value);
      markers.value = res.items || [];
    } catch (error) {
      console.error('获取标记失败', error);
    }
  }
}

async function fetchVersions() {
  try {
    const result = await getVersions(deviceId.value);
    versions.value = result.items;
  } catch (error) {
    console.error('获取版本列表失败', error);
  }
}

function startPolling(collectId: string) {
  if (pollingTimer) clearInterval(pollingTimer);

  // 立即获取最新数据显示
  loadLatestData(collectId);

  // 定时轮询获取最新数据
  pollingTimer = window.setInterval(async () => {
    await loadLatestData(collectId);
  }, (collectStatus.value.interval ?? 5) * 1000);
}

// 加载最新数据
async function loadLatestData(collectId: string) {
  if (!isMounted) return;
  try {
    const result = await getLatestData(collectId, 50);
    if (!isMounted) return; // 异步操作完成后再次检查
    if (result?.items?.length) {
      // 合并数据，避免重复
      const existingIds = new Set(performanceData.value.map(d => d.id));
      const newData = result.items.filter(d => !existingIds.has(d.id));

      if (performanceData.value.length === 0) {
        // 如果之前没有数据，直接设置返回的数据
        performanceData.value = result.items;
      } else if (newData.length > 0) {
        // 有新数据，追加到末尾
        performanceData.value = [...performanceData.value, ...newData];
      }

      // 更新历史数据用于迷你趋势线
      historyData.value = performanceData.value.slice(-50);
    }
  } catch (error) {
    console.error('获取最新数据失败', error);
  }
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

function handleStartClick() {
  if (!deviceId.value) {
    ElMessage.warning('请选择设备');
    return;
  }
  showCollectDialog.value = true;
}

function handleCollectStarted(collectId: string) {
  // 开始新采集前，先停止旧轮询并清空旧数据
  stopPolling();
  performanceData.value = [];
  historyData.value = [];
  // 重置时间范围选择和加载状态
  selectedRelativeTimeRange.value = null;
  loadedTimeRange.value = null;
  totalDuration.value = 0;
  selectedRelativeTimeRange.value = null;
  currentCollectId.value = collectId;
  refreshStatus();
}

async function handleStopClick() {
  if (!currentCollectId.value || isStopping.value) return;
  isStopping.value = true;
  try {
    await stopCollect({
      collect_id: currentCollectId.value,
      device_id: deviceId.value,
    });
    ElMessage.success('采集已停止');
    stopPolling();
    refreshStatus();
    fetchCollectHistory();
  } catch (error) {
    ElMessage.error('停止采集失败');
  } finally {
    isStopping.value = false;
  }
}

// 设备切换
async function handleDeviceChange() {
  stopPolling();
  performanceData.value = [];
  historyData.value = [];
  await refreshStatus();
  await fetchCollectHistory();
  await fetchVersions();

  // 如果没有正在采集，加载最近的采集数据
  if (!collectStatus.value.is_collecting && collectHistory.value.length > 0) {
    const latestCollect = collectHistory.value[0];
    if (latestCollect?.id) {
      currentCollectId.value = latestCollect.id;
      await loadCollectData(latestCollect.id);
    }
  }
}

// 版本操作
function handleMarkVersionClick() {
  if (collectHistory.value.length === 0) {
    ElMessage.warning('没有可用的采集记录');
    return;
  }
  versionForm.value = {
    name: '',
    selectedCollects: [],
  };
  showVersionDialog.value = true;
}

async function handleCreateVersion() {
  if (!versionForm.value.name) {
    ElMessage.warning('请输入版本名称');
    return;
  }
  if (versionForm.value.selectedCollects.length === 0) {
    ElMessage.warning('请选择采集记录');
    return;
  }

  // 计算所选采集记录的总时长
  let totalDurationSeconds = 0;
  for (const collectId of versionForm.value.selectedCollects) {
    const collect = collectHistory.value.find(c => c.id === collectId);
    if (collect?.start_time && collect?.end_time) {
      const startTime = new Date(collect.start_time).getTime();
      const endTime = new Date(collect.end_time).getTime();
      totalDurationSeconds += (endTime - startTime) / 1000;
    } else if (collect?.start_time) {
      // 如果没有结束时间（正在采集），使用当前时间
      const startTime = new Date(collect.start_time).getTime();
      totalDurationSeconds += (Date.now() - startTime) / 1000;
    }
  }

  // 限制最大时长12小时
  const maxDurationSeconds = 12 * 60 * 60; // 12小时
  if (totalDurationSeconds > maxDurationSeconds) {
    const hours = Math.floor(totalDurationSeconds / 3600);
    const minutes = Math.floor((totalDurationSeconds % 3600) / 60);
    ElMessage.warning(`所选采集记录总时长 ${hours}小时${minutes}分钟，超过最大限制12小时`);
    return;
  }

  try {
    await createVersion({
      device_id: deviceId.value,
      name: versionForm.value.name,
      collect_ids: versionForm.value.selectedCollects,
    });
    ElMessage.success('版本标记成功');
    showVersionDialog.value = false;
    await fetchVersions();
  } catch (error) {
    ElMessage.error('创建版本失败');
  }
}

function handleVersionClick(versionId: string) {
  router.push(`/performance-monitor/compare?version_ids=${versionId}`);
}

// 打开历史采集弹窗
function handleHistoryClick() {
  historySearchDate.value = null;
  historySearchProcess.value = '';
  selectedCollectIds.value = new Set(); // 清空选中状态
  fetchCollectHistory();
  showHistoryDialog.value = true;
}

// 选择历史采集记录并加载
async function handleSelectHistoryCollect(collectId: string) {
  currentCollectId.value = collectId;
  await loadCollectData(collectId);
  showHistoryDialog.value = false;
}

// 确认删除采集记录（使用正式对话框）
async function confirmDeleteCollect(collect: PerformanceCollect) {
  if (collect.status === 'running' || collect.is_protected) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      '删除后数据将无法恢复，是否确认删除该采集记录？',
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'delete-confirm-dialog',
      }
    );
    // 用户确认后执行删除
    await handleDeleteCollect(collect.id);
  } catch {
    // 用户取消，不做任何操作
  }
}

// 删除历史采集记录
async function handleDeleteCollect(collectId: string) {
  historyDeleting.value = collectId;
  try {
    await deleteCollect(collectId);
    ElMessage.success('删除成功');
    // 刷新历史列表
    await fetchCollectHistory();
    // 如果删除的是当前显示的采集，清空数据
    if (currentCollectId.value === collectId) {
      performanceData.value = [];
      historyData.value = [];
      currentCollectId.value = '';
    }
  } catch (error) {
    ElMessage.error('删除失败');
  } finally {
    historyDeleting.value = null;
  }
}

// 设置保护状态
async function handleToggleProtected(collect: PerformanceCollect) {
  try {
    const newStatus = !collect.is_protected;
    await setCollectProtected(collect.id, newStatus);
    // 更新本地状态
    collect.is_protected = newStatus;
    ElMessage.success(newStatus ? '已设置为永久保留' : '已取消永久保留');
  } catch (error) {
    ElMessage.error('操作失败');
  }
}

// 可删除的筛选记录（排除running和protected）
const deletableFilteredCollects = computed(() => {
  return filteredCollectHistory.value.filter(c => c.status !== 'running' && !c.is_protected);
});

// 全选可删除记录
function handleSelectAllDeletable() {
  const ids = deletableFilteredCollects.value.map(c => c.id);
  selectedCollectIds.value = new Set(ids);
}

// 取消全选
function handleClearSelection() {
  selectedCollectIds.value = new Set();
}

// 切换单条记录选中状态
function handleToggleSelect(collectId: string) {
  const newSet = new Set(selectedCollectIds.value);
  if (newSet.has(collectId)) {
    newSet.delete(collectId);
  } else {
    newSet.add(collectId);
  }
  selectedCollectIds.value = newSet;
}

// 批量删除选中记录
async function handleBatchDelete() {
  const ids = Array.from(selectedCollectIds.value);
  if (ids.length === 0) {
    ElMessage.warning('请先选择要删除的记录');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${ids.length} 条采集记录吗？删除后数据将无法恢复。`,
      '批量删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    batchDeleting.value = true;
    let successCount = 0;
    let failCount = 0;

    for (const id of ids) {
      try {
        await deleteCollect(id);
        successCount++;
      } catch {
        failCount++;
      }
    }

    batchDeleting.value = false;
    selectedCollectIds.value = new Set();

    if (failCount === 0) {
      ElMessage.success(`成功删除 ${successCount} 条记录`);
    } else {
      ElMessage.warning(`成功删除 ${successCount} 条，失败 ${failCount} 条`);
    }

    // 刷新历史列表
    await fetchCollectHistory();

    // 如果删除了当前显示的采集，清空数据
    if (ids.includes(currentCollectId.value)) {
      performanceData.value = [];
      historyData.value = [];
      currentCollectId.value = '';
    }
  } catch {
    // 用户取消
  }
}

// 计算采集时长（秒转换为可读格式）
function formatDuration(startTime: string, endTime?: string): string {
  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : new Date();
  const diffMs = end.getTime() - start.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}秒`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}分钟`;
  const hours = Math.floor(diffSec / 3600);
  const mins = Math.floor((diffSec % 3600) / 60);
  return `${hours}小时${mins}分钟`;
}

// 处理图表点击事件（更新 clickedTime 用于 TOP10 切换）
function handlePointClick(data: { time: number; collectId: string }) {
  clickedTime.value = data.time;
}

// 小 Tooltip 显示事件处理
function handleMiniTooltipShow(data: MiniTooltipState, chartKey: string) {
  miniTooltipState.value = {
    ...data,
    chartKey,
  };
}

// 小 Tooltip 隐藏事件处理
function handleMiniTooltipHide() {
  miniTooltipState.value = null;
}

// 大面板点击事件处理
function handleDetailClick(data: DetailPanelState, chartKey: string) {
  // 更新 clickedTime 用于底部面板联动
  if (data.data?.relative_time) {
    clickedTime.value = data.data.relative_time;
  }

  if (detailPanelState.value?.data?.relative_time === data.data?.relative_time
      && activeChartKey.value === chartKey) {
    detailPanelState.value = null;
    activeChartKey.value = null;
  } else {
    detailPanelState.value = data;
    activeChartKey.value = chartKey;
  }
}

// 大面板关闭事件处理
function handlePanelClose() {
  detailPanelState.value = null;
  activeChartKey.value = null;
}

// 全局点击事件处理（点击外部关闭大面板）
function handleGlobalClick(e: MouseEvent) {
  // 如果面板显示，且点击的不是图表区域或面板区域
  const target = e.target as HTMLElement;
  if (detailPanelState.value) {
    const isClickInChart = target.closest('.chart-area');
    const isClickInPanel = target.closest('.process-detail-panel');
    if (!isClickInChart && !isClickInPanel) {
      detailPanelState.value = null;
      activeChartKey.value = null;
    }
  }
}

// 处理时间导航条范围变化
function handleRangeChange(range: [number, number]) {
  selectedRelativeTimeRange.value = range;

  // 检查是否需要动态加载更早的数据
  if (loadedTimeRange.value && range[0] < loadedTimeRange.value.min) {
    loadMoreData(range[0], loadedTimeRange.value.min);
  }
}

// 动态加载更早的数据（用户拖动到早期时间时触发）
async function loadMoreData(start_time: number, end_time: number) {
  if (!currentCollectId.value || isLoadingMoreData.value) return;

  // 防止加载无效范围
  if (start_time < 0 || start_time >= end_time) return;

  isLoadingMoreData.value = true;

  try {
    const result = await getCollectDataByRange(currentCollectId.value, {
      start_time: Math.max(0, start_time),
      end_time: end_time,
    });

    if (result?.items?.length) {
      // 合并数据：新数据插入到开头，保持时间顺序
      const existingIds = new Set(performanceData.value.map(d => d.id));
      const newData = result.items.filter(d => !existingIds.has(d.id));

      if (newData.length > 0) {
        // 按时间顺序合并
        performanceData.value = [...newData, ...performanceData.value].sort(
          (a, b) => a.relative_time - b.relative_time
        );

        // 更新已加载的时间范围
        const newMinTime = Math.min(loadedTimeRange.value?.min || 0, newData[0].relative_time);
        loadedTimeRange.value = { min: newMinTime, max: loadedTimeRange.value?.max || 0 };
      }
    }
  } catch (error) {
    console.error('动态加载更多数据失败:', error);
  } finally {
    isLoadingMoreData.value = false;
  }
}
</script>

<template>
  <div class="performance-monitor">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <div class="left-controls">
        <!-- 设备选择标签 -->
        <span class="device-label-tag">设备选择</span>

        <!-- 设备下拉选择框（加大宽度，支持搜索） -->
        <el-select
          v-if="!loadingDevices"
          v-model="deviceId"
          placeholder="选择设备"
          class="device-select-large"
          filterable
          clearable
          @change="handleDeviceChange"
        >
          <el-option
            v-for="device in onlineDevices"
            :key="device.id"
            :label="device.device_type + ' - ' + device.ip"
            :value="device.id"
          >
            <span>{{ device.device_type }}</span>
            <span style="margin-left: 10px; color: #409eff">{{ device.ip }}</span>
          </el-option>
        </el-select>
        <span v-else class="loading-text">加载中...</span>

        <!-- 设备状态卡片（仅未采集时显示） -->
        <div v-if="!collectStatus.is_collecting && currentDeviceInfo" class="device-status-card">
          <span class="device-ip">{{ currentDeviceInfo.ip }}</span>
          <span class="online-badge" v-if="currentDeviceInfo.status === 'online' || currentDeviceInfo.status === 'using'">● 在线</span>
        </div>

        <!-- 采集状态卡片（采集时显示） -->
        <div v-if="collectStatus.is_collecting" class="collect-status-card">
          <span class="collect-label">采集状态：</span>
          <span class="collect-running">运行中</span>
          <span class="collect-duration">已采集: {{ performanceData.length > 0 ? performanceData[performanceData.length - 1]?.relative_time : 0 }}s</span>
        </div>

        <!-- 操作按钮（放到左边） -->
        <button class="start-btn" :disabled="collectStatus.is_collecting" @click="handleStartClick">开始采集</button>
        <button class="stop-btn" :disabled="!collectStatus.is_collecting || isStopping" @click="handleStopClick">
          {{ isStopping ? '停止中...' : '停止采集' }}
        </button>
        <button class="history-btn" @click="handleHistoryClick">查看历史</button>
      </div>
    </div>

        <!-- 指标选择器 -->
    <div v-if="performanceData.length > 0" class="metric-selector-area">
      <div class="metric-selector-wrapper">
        <MetricSelector
          :current-metric="currentMetric"
          :is-linux-device="isLinuxDevice"
          @change="handleMetricChange"
          @more="showMorePopup = true"
        />
        <MetricSearchPopup
          :visible="showMorePopup"
          :collect-id="currentCollectId || ''"
          @update:visible="showMorePopup = $event"
          @select="handleHwinfoMetricSelect"
        />
      </div>
    </div>

    <!-- 时间导航条 -->
    <TimeNavigator
      v-if="performanceData.length > 0 && currentCollectStartTime"
      :duration="totalDuration"
      :start-time="selectedRelativeTimeRange?.[0] || 0"
      :end-time="selectedRelativeTimeRange?.[1] || totalDuration"
      :collection-start-time="currentCollectStartTime"
      :collect-id="currentCollectId"
      :markers="markers"
      @range-change="handleRangeChange"
      @refresh-markers="loadMarkers"
    />

    <!-- 主内容区 - 单图表主导布局 -->
    <div class="charts-area">
      <!-- 当前指标图表 -->
      <div class="chart-wrapper" :class="{ 'has-panel': detailPanelState }">
        <div class="chart-container-wrapper">
          <ChartPanel
            :title="currentChartTitle"
            :series="currentChartSeries"
            :height="500"
            :raw-data="currentMetric === 'hwinfo' ? hwinfoRawData : filteredPerformanceData"
            :markers="markers"
            :chart-type="currentChartType"
            @point-click="handlePointClick"
            @mini-tooltip-show="(data) => handleMiniTooltipShow(data, currentMetric)"
            @mini-tooltip-hide="handleMiniTooltipHide"
            @detail-click="(data) => handleDetailClick(data, currentMetric)"
          />
          <MiniTooltip
            v-if="miniTooltipState && miniTooltipState.chartKey === currentMetric"
            :visible="miniTooltipState !== null"
            :position="miniTooltipState.position"
            :containerRect="miniTooltipState.containerRect"
            :data="miniTooltipState.data"
            :seriesData="miniTooltipState.seriesData"
            :chartType="miniTooltipState.chartType"
          />
        </div>
      </div>

      <!-- 底部面板区域 - 双面板布局（HWiNFO 指标和 Linux 设备不显示进程面板） -->
      <div v-if="currentMetric !== 'hwinfo' && !isLinuxDevice" class="bottom-panels">
        <!-- 目标进程明细面板 -->
        <div class="panel-wrapper target-process-wrapper">
          <TargetProcessPanel
            :data="filteredPerformanceData"
            :clicked-time="clickedTime"
            :chart-type="currentChartType"
          />
        </div>

        <!-- TOP10 进程面板（仅 CPU/GPU 显示） -->
        <div v-if="showTop10Panel" class="panel-wrapper top10-panel-wrapper">
          <Top10Panel
            :data="filteredPerformanceData"
            :clicked-time="clickedTime"
            :metric-type="currentMetric"
          />
        </div>
      </div>
    </div>

    <!-- 开始采集弹窗 -->
    <CollectDialog
      v-model:visible="showCollectDialog"
      :device-id="deviceId"
      :device-info="currentDeviceInfo"
      @started="handleCollectStarted"
    />

    <!-- 版本标记弹窗 -->
    <el-dialog v-model="showVersionDialog" title="标记版本" width="500px">
      <el-form label-width="80px">
        <el-form-item label="版本名称">
          <el-input
            v-model="versionForm.name"
            placeholder="如：v1.0.0、基准版本"
          />
        </el-form-item>
        <el-form-item label="采集记录">
          <el-select
            v-model="versionForm.selectedCollects"
            multiple
            placeholder="选择采集记录"
            style="width: 100%"
          >
            <el-option
              v-for="c in collectHistory"
              :key="c.id"
              :label="c.name || `${new Date(c.start_time).toLocaleString('zh-CN')} (${c.interval}s)`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showVersionDialog = false">取消</el-button>
        <el-button type="success" @click="handleCreateVersion">确认标记</el-button>
      </template>
    </el-dialog>

    <!-- 历史采集弹窗 -->
    <el-dialog v-model="showHistoryDialog" title="历史采集记录" width="700px" class="history-dialog">
      <!-- 搜索过滤区域 -->
      <div class="history-search-bar">
        <div class="search-row">
          <el-date-picker
            v-model="historySearchDate"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 280px"
            :shortcuts="[
              { text: '最近一周', value: () => { const end = new Date(); const start = new Date(); start.setTime(start.getTime() - 7 * 24 * 3600 * 1000); return [start, end]; } },
              { text: '最近一个月', value: () => { const end = new Date(); const start = new Date(); start.setTime(start.getTime() - 30 * 24 * 3600 * 1000); return [start, end]; } },
            ]"
          />
          <el-input
            v-model="historySearchProcess"
            placeholder="搜索进程名..."
            clearable
            style="width: 200px"
          >
            <template #prefix>
              <span style="color: #999">🔍</span>
            </template>
          </el-input>
          <el-button @click="historySearchDate = null; historySearchProcess = ''">清空筛选</el-button>
        </div>
        <div class="search-result-count">
          共 {{ filteredCollectHistory.length }} 条记录
          <span v-if="filteredCollectHistory.length !== collectHistory.length" style="color: #409eff">
            (筛选出 {{ filteredCollectHistory.length }} 条)
          </span>
        </div>

        <!-- 批量操作区域 -->
        <div class="batch-actions">
          <span class="selected-count">
            已选 {{ selectedCollectIds.size }} 条
            <span v-if="deletableFilteredCollects.length > 0" style="color: #999">
              (可删除 {{ deletableFilteredCollects.length }} 条)
            </span>
          </span>
          <el-button size="small" @click="handleSelectAllDeletable">全选可删除</el-button>
          <el-button size="small" @click="handleClearSelection">取消全选</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="selectedCollectIds.size === 0"
            :loading="batchDeleting"
            @click="handleBatchDelete"
          >
            批量删除 {{ selectedCollectIds.size > 0 ? `(${selectedCollectIds.size})` : '' }}
          </el-button>
        </div>
      </div>

      <!-- 历史采集列表 -->
      <div class="history-list" v-loading="historyLoading">
        <div
          v-for="c in filteredCollectHistory"
          :key="c.id"
          :class="['history-card', currentCollectId === c.id ? 'active' : '', c.is_protected ? 'protected' : '', c.status === 'running' ? 'running' : '', selectedCollectIds.has(c.id) ? 'selected' : '']"
        >
          <!-- 卡片头部 -->
          <div class="card-header">
            <div class="card-checkbox">
              <input
                type="checkbox"
                :checked="selectedCollectIds.has(c.id)"
                :disabled="c.status === 'running' || c.is_protected"
                @change="handleToggleSelect(c.id)"
                @click.stop
              />
            </div>
            <div class="card-status">
              <span v-if="c.status === 'running'" class="status-running">
                <span class="running-dot"></span> 采集中
              </span>
              <span v-else class="status-stopped">已完成</span>
              <span v-if="c.is_protected" class="protected-badge" title="永久保留">🔒</span>
            </div>
            <div class="card-actions">
              <button
                class="action-btn protect-btn"
                :class="{ 'is-protected': c.is_protected }"
                @click.stop="handleToggleProtected(c)"
                :title="c.is_protected ? '取消永久保留' : '设置永久保留'"
              >
                {{ c.is_protected ? '🔒 已保留' : '🔓 保留' }}
              </button>
              <button
                class="action-btn delete-btn"
                :disabled="c.status === 'running' || c.is_protected || historyDeleting === c.id"
                @click.stop="confirmDeleteCollect(c)"
              >
                <span v-if="historyDeleting === c.id">删除中...</span>
                <span v-else>🗑️ 删除</span>
              </button>
            </div>
          </div>

          <!-- 卡片内容 -->
          <div class="card-body" @click="handleSelectHistoryCollect(c.id)">
            <div class="card-info-row">
              <div class="info-item">
                <span class="info-label">采集时间</span>
                <span class="info-value">{{ new Date(c.start_time).toLocaleString('zh-CN') }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">采集时长</span>
                <span class="info-value">{{ formatDuration(c.start_time, c.end_time) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">采集频率</span>
                <span class="info-value">{{ c.interval }}秒/次</span>
              </div>
            </div>
            <div class="card-processes">
              <span class="processes-label">目标进程：</span>
              <div class="processes-tags">
                <span
                  v-for="p in c.target_processes?.slice(0, 4)"
                  :key="p.name"
                  class="process-tag"
                >
                  {{ p.name.replace('.exe', '').replace('.EXE', '') }}
                </span>
                <span v-if="c.target_processes?.length > 4" class="process-more">
                  +{{ c.target_processes.length - 4 }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="filteredCollectHistory.length === 0" class="history-empty">
          <div class="empty-icon">📋</div>
          <div class="empty-text">
            {{ collectHistory.length === 0 ? '暂无采集记录' : '没有匹配的记录' }}
          </div>
          <div v-if="collectHistory.length > 0" class="empty-hint">
            尝试调整筛选条件
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 图表容器 - 单独占据整行 */
.chart-wrapper {
  position: relative;
  margin-bottom: 16px;
}

/* 图表和 tooltip 的容器 */
.chart-container-wrapper {
  position: relative;
}

/* 面板激活时增加底部空间 */
.chart-wrapper.has-panel {
  margin-bottom: 200px;  /* 为面板留出空间 */
}

.performance-monitor {
  padding: 12px;
  background: #f5f5f5;
  min-height: 100vh;
}
.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
  min-width: 0;
}
.left-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: nowrap;
}
/* 设备选择标签 - 蓝色背景 */
.device-label-tag {
  display: inline-block;
  padding: 8px 20px;
  background: #409eff;
  color: white;
  border-radius: 4px;
  font-weight: bold;
  font-size: 13px;
}
/* 设备下拉选择框（加大宽度） */
.device-select-large {
  width: 260px;
}
.loading-text {
  color: #999;
  font-size: 12px;
}
/* 开始采集按钮 - 绿色 */
.start-btn {
  padding: 8px 20px;
  background: #67c23a;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.start-btn:hover:not(:disabled) {
  background: #5cb85c;
}
.start-btn:disabled {
  background: #c8e6c9;
  color: #fff;
  cursor: not-allowed;
  opacity: 0.6;
}
/* 停止采集按钮 - 红色 */
.stop-btn {
  padding: 8px 20px;
  background: #f56c6c;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.stop-btn:disabled {
  background: #f5f5f5;
  color: #999;
  border: 1px solid #ddd;
  cursor: not-allowed;
  opacity: 0.6;
}
.stop-btn:not(:disabled):hover {
  background: #f78989;
}
/* 查看历史按钮 - 橙色 */
.history-btn {
  padding: 8px 20px;
  background: #e6a23c;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.history-btn:hover {
  background: #ebb563;
}
/* 设备状态卡片 */
.device-status-card {
  padding: 8px 15px;
  background: white;
  border-radius: 4px;
  border: 1px solid #ddd;
}
.device-ip {
  font-weight: bold;
  font-size: 13px;
  color: #333;
}
.online-badge {
  margin-left: 10px;
  color: #67c23a;
  font-size: 12px;
}
/* 采集状态卡片 */
.collect-status-card {
  padding: 8px 15px;
  background: white;
  border-radius: 4px;
  border: 1px solid #ddd;
  font-size: 12px;
}
.collect-label {
  color: #666;
}
.collect-running {
  color: #67c23a;
  font-weight: bold;
}
.collect-duration {
  margin-left: 10px;
  color: #999;
}
/* 图表区 - 单列布局 */
.charts-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 指标选择器区域 */
.metric-selector-area {
  margin-bottom: 12px;
}

.metric-selector-wrapper {
  position: relative;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}

/* 底部面板区域 - 双面板布局 */
.bottom-panels {
  display: flex;
  gap: 16px;
}

.panel-wrapper {
  flex: 1;
  min-width: 300px;
  max-width: 400px;
}

.target-process-wrapper {
  flex: 0 0 320px;
  max-width: 320px;
}

.top10-panel-wrapper {
  flex: 1 1 400px;
  max-width: 400px;
}

.target-process-wrapper,
.top10-panel-wrapper {
  background: #fff;
  border-radius: 6px;
  overflow: hidden;
}

/* 历史采集弹窗样式 - 重新设计 */
.history-dialog .el-dialog__body {
  padding-top: 0;
}

.history-search-bar {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

.search-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.search-result-count {
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}

/* 批量操作区域 */
.batch-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #f0f5ff;
  border-radius: 6px;
  border: 1px solid #d6e4ff;
}

.selected-count {
  font-size: 13px;
  color: #1890ff;
  font-weight: 500;
}

.history-list {
  max-height: 450px;
  overflow-y: auto;
  padding-right: 4px;
}

.history-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 12px;
  transition: all 0.2s ease;
  overflow: hidden;
}

.history-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-color: #d0d0d0;
}

.history-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.history-card.protected {
  border-left: 3px solid #67c23a;
}

.history-card.running {
  border-left: 3px solid #e6a23c;
  background: #fdf6ec;
}

.history-card.selected {
  border-color: #409eff;
  background: #f0f5ff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
}

.card-checkbox {
  margin-right: 8px;
}

.card-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #409eff;
}

.card-checkbox input[type="checkbox"]:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.card-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-running {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #e6a23c;
  font-weight: 500;
}

.running-dot {
  width: 8px;
  height: 8px;
  background: #e6a23c;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}

.status-stopped {
  font-size: 12px;
  color: #67c23a;
}

.protected-badge {
  font-size: 12px;
  color: #67c23a;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  border: 1px solid #ddd;
  background: #f5f5f5;
  color: #666;
  transition: all 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  background: #eee;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.protect-btn.is-protected {
  background: #f0f9eb;
  border-color: #67c23a;
  color: #67c23a;
}

.protect-btn:not(.is-protected):hover {
  background: #f0f9eb;
  border-color: #c2e7b0;
}

.delete-btn:hover:not(:disabled) {
  background: #fef0f0;
  border-color: #fbc4c4;
  color: #f56c6c;
}

.card-body {
  padding: 16px;
  cursor: pointer;
}

.card-info-row {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 11px;
  color: #999;
}

.info-value {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.card-processes {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.processes-label {
  font-size: 11px;
  color: #999;
  white-space: nowrap;
}

.processes-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.process-tag {
  padding: 2px 8px;
  background: #e6f7ff;
  color: #409eff;
  border-radius: 3px;
  font-size: 11px;
  border: 1px solid #91d5ff;
}

.process-more {
  padding: 2px 6px;
  background: #f5f5f5;
  color: #999;
  border-radius: 3px;
  font-size: 10px;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.empty-icon {
  font-size: 48px;
  color: #ccc;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 14px;
  color: #999;
}

.empty-hint {
  font-size: 12px;
  color: #ccc;
  margin-top: 8px;
}
</style>