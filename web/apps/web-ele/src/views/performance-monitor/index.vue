<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import ChartPanel from './components/ChartPanel.vue';
import MetricCard from './components/MetricCard.vue';
import Top10List from './components/Top10List.vue';
import CollectDialog from './components/CollectDialog.vue';
import {
  getCollectStatus,
  stopCollect,
  getLatestData,
  getCollectList,
} from '#/api/core/performance-monitor';
import type {
  PerformanceData,
  CollectStatus,
  PerformanceCollect,
} from '#/api/core/performance-monitor';
import type { ChartSeries, MetricCardData, Top10Item } from './types';
import { VERSION_COLORS } from './types';

// 设备选择
const deviceId = ref('');
const devices = ref<Array<{ id: string; name: string; ip: string }>>([]);
const deviceOptions = computed(() =>
  devices.value.map((d) => ({ label: `${d.name} (${d.ip})`, value: d.id })),
);

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

// 定时轮询
let pollingTimer: number | null = null;

// 当前数值显示
const currentMetrics = computed(() => {
  const latest = performanceData.value[performanceData.value.length - 1];
  if (!latest) return null;
  return latest;
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
    { name: '系统', data: systemData, color: '#409eff' },
    { name: '进程', data: processData, color: '#67c23a' },
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
    },
  ];
});

const commitMemoryChartSeries = computed<ChartSeries[]>(() => {
  if (!performanceData.value.length) return [];
  return [
    {
      name: '系统',
      data: performanceData.value.map((d) => ({
        time: d.relative_time,
        value: d.commit_memory || 0,
      })),
      color: '#f56c6c',
    },
    {
      name: '进程',
      data: performanceData.value.map((d) => {
        const totalMem =
          d.target_processes?.reduce((sum, p) => sum + p.total_memory, 0) || 0;
        return { time: d.relative_time, value: totalMem / 1024 }; // MB to GB
      }),
      color: '#909399',
    },
  ];
});

const memoryChartSeries = computed<ChartSeries[]>(() => {
  if (!performanceData.value.length) return [];
  return [
    {
      name: '系统',
      data: performanceData.value.map((d) => ({
        time: d.relative_time,
        value: d.memory_usage || 0,
      })),
      color: '#909399',
    },
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
    color: VERSION_COLORS[i % 3],
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
    color: VERSION_COLORS[i % 3],
  }));
});

// 时间窗口选择
const timeWindow = ref(60); // 默认60分钟
const timeWindowOptions = [30, 60, 120, -1]; // -1 表示全部

// 初始化
onMounted(async () => {
  // 获取设备列表（模拟数据）
  devices.value = [
    { id: 'device-001', name: 'Windows-001', ip: '192.168.1.100' },
    { id: 'device-002', name: 'Windows-002', ip: '192.168.1.101' },
  ];
  deviceId.value = devices.value[0]?.id || '';

  await refreshStatus();
  await fetchCollectHistory();
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
    collectHistory.value = result.items;
  } catch (error) {
    console.error('获取采集历史失败', error);
  }
}

function startPolling(collectId: string) {
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = window.setInterval(async () => {
    try {
      const result = await getLatestData(collectId, 10);
      performanceData.value = result.items;
      historyData.value = [...historyData.value, ...result.items].slice(-100);
    } catch (error) {
      console.error('获取最新数据失败', error);
    }
  }, collectStatus.value.interval * 1000 || 5000);
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
}
</script>

<template>
  <div class="performance-monitor">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <div class="left-controls">
        <el-select
          v-model="deviceId"
          placeholder="选择设备"
          style="width: 180px"
          @change="handleDeviceChange"
        >
          <el-option
            v-for="opt in deviceOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button
          v-if="!collectStatus.is_collecting"
          type="success"
          @click="handleStartClick"
        >
          开始采集
        </el-button>
        <el-button
          v-else
          type="danger"
          @click="handleStopClick"
        >
          停止采集
        </el-button>
        <div v-if="collectStatus.is_collecting" class="status-badge">
          <span class="status-dot"></span>
          采集中 {{ collectStatus.interval }}秒/
          {{ collectStatus.target_processes?.length || 0 }}进程
        </div>
      </div>
      <div class="right-controls">
        <el-button type="primary" size="small">标记版本</el-button>
        <el-button size="small">历史采集</el-button>
      </div>
    </div>

    <!-- 时间轴选择器 -->
    <div class="time-selector">
      <el-button-group>
        <el-button
          v-for="opt in timeWindowOptions"
          :key="opt"
          :type="timeWindow === opt ? 'primary' : 'default'"
          size="small"
          @click="timeWindow = opt"
        >
          {{ opt === -1 ? '全部' : `${opt}分钟` }}
        </el-button>
      </el-button-group>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧曲线图 -->
      <div class="charts-area">
        <ChartPanel title="CPU 使用率" :series="cpuChartSeries" :height="160" />
        <ChartPanel title="GPU 使用率" :series="gpuChartSeries" :height="120" />
        <ChartPanel
          title="提交内存"
          :series="commitMemoryChartSeries"
          :height="120"
        />
        <ChartPanel title="内存使用" :series="memoryChartSeries" :height="120" />
      </div>

      <!-- 右侧栏 -->
      <div class="sidebar">
        <!-- 次要指标卡片 -->
        <div class="metrics-grid">
          <MetricCard v-for="(card, i) in metricCards" :key="i" :data="card" />
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
      @started="handleCollectStarted"
    />
  </div>
</template>

<style scoped>
.performance-monitor {
  padding: 16px;
  background: #f5f5f5;
  min-height: 100vh;
}
.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.left-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}
.right-controls {
  display: flex;
  gap: 8px;
}
.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: #f0f9eb;
  border-radius: 4px;
  font-size: 12px;
  color: #67c23a;
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
.time-selector {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}
</style>