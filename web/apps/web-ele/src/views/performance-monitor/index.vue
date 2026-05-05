<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import { ElSelect, ElOption, ElDialog, ElForm, ElFormItem, ElInput, ElButton } from 'element-plus';
import { useRouter } from 'vue-router';
import ChartPanel from './components/ChartPanel.vue';
import MetricCard from './components/MetricCard.vue';
import Top10List from './components/Top10List.vue';
import CollectDialog from './components/CollectDialog.vue';
import TimelineSelector from './components/TimelineSelector.vue';
import {
  getCollectStatus,
  stopCollect,
  getLatestData,
  getCollectData,
  getCollectList,
  getVersions,
  createVersion,
} from '#/api/core/performance-monitor';
import { getEnvMachineListApi } from '#/api/core/env-machine';
import type {
  PerformanceData,
  CollectStatus,
  PerformanceCollect,
  PerformanceVersion,
} from '#/api/core/performance-monitor';
import type { EnvMachine } from '#/api/core/env-machine';
import type { ChartSeries, MetricCardData, Top10Item } from './types';
import { VERSION_COLORS } from './types';

const router = useRouter();

// 设备选择
const deviceId = ref('');
const devices = ref<EnvMachine[]>([]);
const loadingDevices = ref(true);

// 在线设备列表
const onlineDevices = computed(() =>
  devices.value.filter((d) => d.status === 'online' || d.status === 'using'),
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

// 定时轮询
let pollingTimer: number | null = null;

// 时间窗口选择
const timeWindow = ref(30); // 默认30分钟

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

// 当前数值显示
const currentMetrics = computed(() => {
  const latest = performanceData.value[performanceData.value.length - 1];
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
  if (!performanceData.value.length) return [];
  const systemData = performanceData.value.map((d) => ({
    time: d.relative_time,
    value: d.cpu_usage || 0,
  }));
  const processData = performanceData.value.map((d) => {
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
  if (!performanceData.value.length) return [];
  return [
    {
      name: '系统',
      data: performanceData.value.map((d) => ({
        time: d.relative_time,
        value: d.gpu_usage || 0,
      })),
      color: '#e6a23c',
      unit: '%',
    },
  ];
});

// 提交内存图表 - 只显示进程内存总和
const commitMemoryChartSeries = computed<ChartSeries[]>(() => {
  if (!performanceData.value.length) return [];
  // 进程内存总和（MB）
  const processData = performanceData.value.map((d) => {
    const totalMemMB =
      d.target_processes?.reduce((sum, p) => sum + p.total_memory, 0) || 0;
    return { time: d.relative_time, value: totalMemMB };
  });
  return [
    { name: '进程内存', data: processData, color: '#f56c6c', unit: 'MB' },
  ];
});

const memoryChartSeries = computed<ChartSeries[]>(() => {
  if (!performanceData.value.length) return [];
  // 显示进程内存总和（MB单位）
  const processData = performanceData.value.map((d) => {
    const totalMemMB =
      d.target_processes?.reduce((sum, p) => sum + p.total_memory, 0) || 0;
    return { time: d.relative_time, value: totalMemMB };
  });
  return [
    { name: '进程内存', data: processData, color: '#909399', unit: 'MB' },
  ];
});

// 次要指标卡片数据
const metricCards = computed<MetricCardData[]>(() => {
  const latest = currentMetrics.value;
  if (!latest) return [];

  // 获取历史数据用于迷你趋势线
  const history = historyData.value.slice(-10);

  return [
    {
      name: '功耗',
      value: latest.power || 0,
      unit: 'W',
      color: '#409eff',
      historyData: history.map((d) => d.power || 0),
    },
    {
      name: 'CPU速度',
      value: latest.cpu_speed || 0,
      unit: 'GHz',
      color: '#67c23a',
      historyData: history.map((d) => d.cpu_speed || 0),
    },
    {
      name: 'CPU温度',
      value: latest.cpu_temp || 0,
      unit: '°C',
      color: '#e6a23c',
      historyData: history.map((d) => d.cpu_temp || 0),
    },
    {
      name: '进程句柄',
      value: latest.process_handles || 0,
      unit: '',
      color: '#909399',
      historyData: history.map((d) => d.process_handles || 0),
    },
    {
      name: '上传速度',
      value: latest.upload_speed || 0,
      unit: 'MB/s',
      color: '#67c23a',
      historyData: history.map((d) => d.upload_speed || 0),
    },
    {
      name: '下载速度',
      value: latest.download_speed || 0,
      unit: 'MB/s',
      color: '#409eff',
      historyData: history.map((d) => d.download_speed || 0),
    },
  ];
});

// TOP10 数据
const top10Cpu = computed<Top10Item[]>(() => {
  const latest = currentMetrics.value;
  if (!latest?.top10_cpu) return [];
  return latest.top10_cpu.map((p, i) => ({
    name: p.name,
    value: p.cpu || 0,
    trendData: historyData.value.slice(-10).map((d) => {
      const proc = d.top10_cpu?.find((t) => t.name === p.name);
      return proc?.cpu || 0;
    }),
    color: VERSION_COLORS[i % 3] || '#67c23a',
  }));
});

const top10Gpu = computed<Top10Item[]>(() => {
  const latest = currentMetrics.value;
  if (!latest?.top10_gpu) return [];
  return latest.top10_gpu.map((p, i) => ({
    name: p.name,
    value: p.gpu || 0,
    trendData: historyData.value.slice(-10).map((d) => {
      const proc = d.top10_gpu?.find((t) => t.name === p.name);
      return proc?.gpu || 0;
    }),
    color: VERSION_COLORS[i % 3] || '#67c23a',
  }));
});

// 获取在线设备列表
async function fetchOnlineDevices() {
  loadingDevices.value = true;
  try {
    const result = await getEnvMachineListApi({
      device_type: 'windows', // 性能监控目前只支持 Windows 设备
      page: 1,
      page_size: 100,
    });
    devices.value = result?.items || [];
    // 默认选择第一个在线设备
    const onlineDevs = devices.value.filter(
      (d) => d.status === 'online' || d.status === 'using',
    );
    const firstDevice = onlineDevs[0];
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
  await fetchOnlineDevices();

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
});

onUnmounted(() => {
  stopPolling();
});

async function refreshStatus() {
  if (!deviceId.value) return;
  try {
    const status = await getCollectStatus(deviceId.value);
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
    const result = await getCollectData(collectId, { page: 1, page_size: 500 });
    if (result?.items?.length) {
      performanceData.value = result.items;
      historyData.value = result.items.slice(-50);
    }
  } catch (error) {
    console.error('获取采集数据失败', error);
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
  try {
    const result = await getLatestData(collectId, 50);
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
  currentCollectId.value = collectId;
  refreshStatus();
}

async function handleStopClick() {
  if (!currentCollectId.value) return;
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

function handleTimelineWindowChange(range: [Date, Date]) {
  console.log('时间窗口变化', range);
}

function handleTimelineVersionClick(versionId: string) {
  handleVersionClick(versionId);
}

function handleTimelineCollectClick(collectId: string) {
  console.log('点击采集', collectId);
}
</script>

<template>
  <div class="performance-monitor">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <div class="left-controls">
        <!-- 设备选择框 -->
        <div class="device-selector">
          <span v-if="loadingDevices" style="color: #999; font-size: 12px;">加载中...</span>
          <el-select
            v-else
            v-model="deviceId"
            placeholder="选择设备"
            style="width: 200px"
            @change="handleDeviceChange"
          >
            <el-option
              v-for="device in onlineDevices"
              :key="device.id"
              :label="device.device_type + '-' + device.ip"
              :value="device.id"
            />
          </el-select>
        </div>
        <!-- 开始采集按钮 - 始终显示，采集中时隐藏 -->
        <button
          v-if="!collectStatus.is_collecting"
          class="start-btn"
          @click="handleStartClick"
        >
          开始采集
        </button>
        <!-- 停止采集按钮 - 始终显示，不采集中时disabled样式 -->
        <button
          class="stop-btn"
          :disabled="!collectStatus.is_collecting"
          @click="handleStopClick"
        >
          停止采集
        </button>
        <!-- 采集中状态显示进程名（带 Tooltip） -->
        <div
          v-if="collectStatus.is_collecting"
          class="status-badge"
          :title="processTooltipContent"
        >
          <span class="status-dot"></span>
          采集中 (频率{{ collectStatus.interval }}秒) |
          <span v-if="processNamesDisplay" class="process-names">
            {{ processNamesDisplay }}
          </span>
          <span v-else>{{ collectStatus.target_processes?.length || 0 }}进程</span>
        </div>
      </div>
      <div class="right-controls">
        <button class="mark-version-btn" @click="handleMarkVersionClick">
          标记版本
        </button>
        <button class="history-btn">历史采集</button>
      </div>
    </div>

    <!-- 时间轴选择器 -->
    <div class="time-selector-wrapper">
      <div class="time-selector">
        <div class="time-btn-group">
          <button
            v-for="opt in [30, 60, -1]"
            :key="opt"
            :class="timeWindow === opt ? 'time-btn active' : 'time-btn'"
            @click="timeWindow = opt"
          >
            {{ opt === -1 ? '全部' : `${opt}分钟` }}
          </button>
        </div>
        <TimelineSelector
          class="timeline-component"
          :collects="collectHistory"
          :versions="versions"
          :current-collect-id="currentCollectId"
          :total-duration="timeWindow === -1 ? 120 : timeWindow"
          :actual-start-time="actualTimeRange?.startTime"
          :actual-end-time="actualTimeRange?.endTime"
          @window-change="handleTimelineWindowChange"
          @version-click="handleTimelineVersionClick"
          @collect-click="handleTimelineCollectClick"
        />
      </div>
      <!-- 已标记版本显示 -->
      <div v-if="versions.length > 0" class="version-tags-row">
        <span class="version-label">已标记版本：</span>
        <span
          v-for="(v, i) in versions"
          :key="v.id"
          class="version-tag"
          :style="{ background: VERSION_COLORS[i % VERSION_COLORS.length] || '#67c23a' }"
          @click="handleVersionClick(v.id)"
        >
          {{ v.name }}
        </span>
        <span class="click-hint">点击跳转</span>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧曲线图 -->
      <div class="charts-area">
        <ChartPanel
          title="CPU（%）"
          :series="cpuChartSeries"
          :height="180"
          :raw-data="performanceData"
          chart-type="cpu"
        />
        <ChartPanel
          title="GPU（%）"
          :series="gpuChartSeries"
          :height="150"
          :raw-data="performanceData"
          chart-type="gpu"
        />
        <ChartPanel
          title="提交内存（MB）"
          :series="commitMemoryChartSeries"
          :height="150"
          :raw-data="performanceData"
          chart-type="commitMemory"
        />
        <ChartPanel
          title="内存（MB）"
          :series="memoryChartSeries"
          :height="150"
          :raw-data="performanceData"
          chart-type="memory"
        />
      </div>

      <!-- 右侧栏 -->
      <div class="sidebar">
        <!-- 其它指标卡片 -->
        <div class="metrics-grid">
          <div class="metrics-title">其它指标</div>
          <div class="metrics-cards">
            <MetricCard v-for="(card, i) in metricCards" :key="i" :data="card" />
          </div>
        </div>

        <!-- TOP10 概览 -->
        <Top10List title="CPU TOP10" :items="top10Cpu" />
        <Top10List title="GPU TOP10" :items="top10Gpu" />
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
              :label="c.name || `${c.start_time} (${c.interval}s)`"
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
  </div>
</template>

<style scoped>
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
  flex-shrink: 0;
}
.device-selector {
  display: inline-block;
  min-width: 200px;
}
.device-select {
  width: 180px;
  min-width: 180px;
}
/* 开始采集按钮 - 绿色 */
.start-btn {
  padding: 6px 16px;
  background: #67c23a;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.start-btn:hover {
  background: #5cb85c;
}
/* 停止采集按钮 - 灰色 */
.stop-btn {
  padding: 6px 16px;
  background: #f5f5f5;
  color: #999;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.stop-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.stop-btn:not(:disabled):hover {
  background: #eee;
  color: #666;
  border-color: #ccc;
}
.right-controls {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
/* 标记版本按钮 - 原生button蓝色 */
.mark-version-btn {
  padding: 6px 12px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}
.mark-version-btn:hover {
  background: #337ecc;
}
/* 历史采集按钮 - 原生button灰色 */
.history-btn {
  padding: 6px 12px;
  background: #f5f5f5;
  color: #666;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}
.history-btn:hover {
  background: #eee;
}
.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: #f0f9eb;
  border-radius: 4px;
  font-size: 11px;
  color: #67c23a;
  cursor: pointer;
}
.status-dot {
  width: 8px;
  height: 8px;
  background: #67c23a;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.process-names {
  color: #409eff;
}
.main-content {
  display: flex;
  gap: 12px;
}
.charts-area {
  flex: 65%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sidebar {
  flex: 35%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.metrics-grid {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
}
.metrics-title {
  font-size: 15px;
  font-weight: 700;
  color: #333;
  margin-bottom: 10px;
}
.metrics-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.time-selector-wrapper {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.time-selector {
  display: flex;
  gap: 8px;
  align-items: center;
}
.time-btn-group {
  display: flex;
  gap: 8px;
}
.time-btn {
  padding: 6px 12px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 11px;
  color: #666;
  cursor: pointer;
}
.time-btn.active {
  background: #409eff;
  border: none;
  color: #fff;
}
.time-btn:hover:not(.active) {
  background: #eee;
}
.timeline-component {
  flex: 1;
}
.version-tags-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 10px;
  color: #999;
}
.version-label {
  color: #999;
}
.version-tag {
  cursor: pointer;
  padding: 2px 6px;
  color: #fff;
  border-radius: 3px;
  font-size: 10px;
}
.click-hint {
  color: #999;
}
</style>