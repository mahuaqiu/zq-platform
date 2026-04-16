<script lang="ts" setup>
import type {
  DashboardStatsResponse,
  TopTagItem,
  TopDurationItem,
  OfflineMachineItem,
} from '#/api/core/device-monitor';

import { onMounted, onUnmounted, ref, computed } from 'vue';

import { Page } from '@vben/common-ui';

import { ElScrollbar, ElSelect, ElOption } from 'element-plus';

import {
  getDashboardStatsApi,
  getNamespacesApi,
} from '#/api/core/device-monitor';

defineOptions({ name: 'DeviceMonitorPage' });

// 数据
const loading = ref(false);
const stats = ref<DashboardStatsResponse | null>(null);
const namespaces = ref<string[]>([]);
const selectedNamespace = ref<string>('');

// 自动刷新定时器
let refreshTimer: ReturnType<typeof setInterval> | null = null;

// 计算最大申请次数（用于柱状图比例）
const maxTagCount = computed(() => {
  if (!stats.value?.top10_tags?.length) return 1;
  return Math.max(...stats.value.top10_tags.map((t) => t.count), 1);
});

// 计算最大资源不足次数
const maxInsufficientCount = computed(() => {
  if (!stats.value?.top10_insufficient?.length) return 1;
  return Math.max(...stats.value.top10_insufficient.map((t) => t.count), 1);
});

// 计算最大占用时长
const maxDuration = computed(() => {
  if (!stats.value?.top20_duration?.length) return 1;
  return Math.max(...stats.value.top20_duration.map((t) => t.duration_minutes), 1);
});

// 计算其他失败次数（除资源不足外的非成功次数）
const otherFailedCount = computed(() => {
  if (!stats.value?.apply_24h) return 0;
  const { total, success, failed } = stats.value.apply_24h;
  return total - success - failed;
});

// 计算柱状图宽度（固定像素值）
const TOP_TAG_BAR_MAX = 140; // 申请次数TOP10最大宽度
const TOP_INSUFFICIENT_BAR_MAX = 60; // 资源不足TOP10最大宽度
const DURATION_BAR_MAX = 280; // 占用时长TOP20最大宽度

function getTagBarWidth(value: number): string {
  const percent = Math.min((value / maxTagCount.value) * 100, 100);
  return `${Math.max(percent * TOP_TAG_BAR_MAX / 100, 10)}px`;
}

function getInsufficientBarWidth(value: number): string {
  const percent = Math.min((value / maxInsufficientCount.value) * 100, 100);
  return `${Math.max(percent * TOP_INSUFFICIENT_BAR_MAX / 100, 10)}px`;
}

function getDurationBarWidth(value: number): string {
  const percent = Math.min((value / maxDuration.value) * 100, 100);
  return `${Math.max(percent * DURATION_BAR_MAX / 100, 10)}px`;
}

// 设备类型显示名称
const deviceTypeNames: Record<string, string> = {
  windows: 'Windows',
  mac: 'Mac',
  android: 'Android',
  ios: 'iOS',
};

// 设备类型颜色
const deviceTypeColors: Record<string, string> = {
  windows: '#1890ff',
  mac: '#52c41a',
  android: '#faad14',
  ios: '#eb2f96',
};

// 加载数据
async function loadStats() {
  loading.value = true;
  try {
    const res = await getDashboardStatsApi(selectedNamespace.value || undefined);
    stats.value = res;
  } catch (error) {
    console.error('加载统计数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 加载 namespace 列表
async function loadNamespaces() {
  try {
    const res = await getNamespacesApi();
    namespaces.value = res;
  } catch (error) {
    console.error('加载 namespace 列表失败:', error);
  }
}

// namespace 变化时重新加载数据
function handleNamespaceChange() {
  loadStats();
}

// 初始化
onMounted(() => {
  loadNamespaces();
  loadStats();
  // 30分钟自动刷新
  refreshTimer = setInterval(loadStats, 30 * 60 * 1000);
});

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }
});
</script>

<template>
  <Page auto-content-height>
    <div class="device-monitor-page">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <ElSelect
          v-model="selectedNamespace"
          placeholder="全部 Namespace"
          clearable
          style="width: 200px"
          @change="handleNamespaceChange"
        >
          <ElOption
            v-for="ns in namespaces"
            :key="ns"
            :label="ns"
            :value="ns"
          />
        </ElSelect>
      </div>

      <!-- 主内容区域 -->
      <div v-loading="loading" class="main-content">
        <!-- 左侧面板 -->
        <div class="left-panel">
          <!-- 左侧标题栏 -->
          <div class="left-panel-header">
            实时状态
          </div>

          <!-- 模块1：设备台数统计 -->
          <div class="stats-card device-stats-card">
            <div class="card-title">设备台数统计</div>

            <!-- 汇总行 -->
            <div class="summary-row">
              <div class="summary-item">
                <div class="summary-value stat-blue">{{ stats?.device_stats?.total || 0 }}</div>
                <div class="summary-label">总数</div>
              </div>
              <div class="summary-item">
                <div class="summary-value stat-green">{{ stats?.device_stats?.online || 0 }}</div>
                <div class="summary-label">在线</div>
              </div>
              <div class="summary-item">
                <div class="summary-value stat-red">{{ stats?.device_stats?.offline || 0 }}</div>
                <div class="summary-label">离线</div>
              </div>
            </div>

            <!-- 按类型统计 -->
            <div class="type-row">
              <div
                v-for="item in stats?.device_stats?.by_type || []"
                :key="item.type"
                class="type-item"
              >
                <div
                  class="type-value"
                  :style="{ color: deviceTypeColors[item.type] }"
                >
                  {{ item.total }}
                </div>
                <div class="type-label">{{ deviceTypeNames[item.type] || item.type }}</div>
              </div>
            </div>

            <!-- 启用/未启用 -->
            <div class="enabled-row">
              <div class="enabled-item enabled-green">启用 {{ stats?.device_stats?.by_type?.reduce((sum, t) => sum + t.enabled, 0) || 0 }}</div>
              <div class="enabled-item enabled-red">未启用 {{ stats?.device_stats?.by_type?.reduce((sum, t) => sum + t.disabled, 0) || 0 }}</div>
            </div>
          </div>

          <!-- 模块6：异步机器排查 -->
          <div class="stats-card offline-card">
            <div class="card-title warning">异步机器排查（启用但离线）</div>
            <ElScrollbar class="offline-list" v-if="stats?.offline_machines?.length">
              <div
                v-for="item in stats?.offline_machines || []"
                :key="item.id"
                class="offline-item"
              >
                <span class="offline-dot">●</span>
                <span class="offline-name">{{ item.name || item.ip || item.device_sn }}</span>
                <span class="offline-ip">({{ item.ip || item.device_sn }})</span>
                <span class="offline-duration">离线 {{ item.offline_duration }}</span>
              </div>
            </ElScrollbar>
            <div v-else class="no-data">暂无离线设备</div>
          </div>
        </div>

        <!-- 右侧面板 -->
        <div class="right-panel">
          <!-- 模块2：24h申请总次数 -->
          <div class="stats-card apply-card">
            <div class="apply-main">
              <div class="apply-total">
                <div class="apply-value">{{ stats?.apply_24h?.total || 0 }}</div>
                <div class="apply-label">24h申请总次数</div>
              </div>
              <div class="apply-detail">
                <div class="detail-item success">
                  <div class="detail-value">{{ stats?.apply_24h?.success || 0 }}</div>
                  <div class="detail-label">成功</div>
                </div>
                <div class="detail-item insufficient">
                  <div class="detail-value">{{ stats?.apply_24h?.failed || 0 }}</div>
                  <div class="detail-label">资源不足</div>
                </div>
                <div class="detail-item failed">
                  <div class="detail-value">{{ otherFailedCount }}</div>
                  <div class="detail-label">失败</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 模块3 & 5：TOP10 标签 -->
          <div class="top-cards-row">
            <!-- 申请次数 TOP10 -->
            <div class="stats-card top-card">
              <div class="card-title">申请次数 TOP10 标签</div>
              <div class="top-list">
                <div
                  v-for="(item, index) in stats?.top10_tags || []"
                  :key="index"
                  class="top-item"
                >
                  <div class="top-tag">{{ item.tag }}</div>
                  <div
                    class="top-bar"
                    :style="{ width: getTagBarWidth(item.count) }"
                  ></div>
                  <span class="top-count">{{ item.count }}</span>
                </div>
                <div v-if="!stats?.top10_tags?.length" class="no-data">暂无数据</div>
              </div>
            </div>

            <!-- 资源不足 TOP10 -->
            <div class="stats-card top-card">
              <div class="card-title warning">资源不足 TOP10 标签</div>
              <div class="top-list">
                <div
                  v-for="(item, index) in stats?.top10_insufficient || []"
                  :key="index"
                  class="top-item"
                >
                  <div class="top-tag">{{ item.tag }}</div>
                  <div
                    class="top-bar red"
                    :style="{ width: getInsufficientBarWidth(item.count) }"
                  ></div>
                  <span class="top-count">{{ item.count }}</span>
                </div>
                <div v-if="!stats?.top10_insufficient?.length" class="no-data">暂无数据</div>
              </div>
            </div>
          </div>

          <!-- 模块4：占用时长 TOP20 -->
          <div class="stats-card duration-card">
            <div class="card-title">机器占用时长 TOP20</div>
            <ElScrollbar class="duration-list">
              <div
                v-for="(item, index) in stats?.top20_duration || []"
                :key="index"
                class="duration-item"
              >
                <div class="duration-info">
                  <div class="duration-ip">{{ item.ip || item.device_sn }}</div>
                  <div
                    class="duration-type"
                    :style="{ color: deviceTypeColors[item.device_type] }"
                  >
                    {{ deviceTypeNames[item.device_type] || item.device_type }}
                  </div>
                </div>
                <div
                  class="duration-bar"
                  :style="{ width: getDurationBarWidth(item.duration_minutes) }"
                ></div>
                <span class="duration-value">{{ item.duration_display }}</span>
              </div>
              <div v-if="!stats?.top20_duration?.length" class="no-data">暂无数据</div>
            </ElScrollbar>
          </div>
        </div>
      </div>
    </div>
  </Page>
</template>

<style scoped>
.device-monitor-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  background: #f0f2f5; /* 改为浅灰 */
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: #fff;
  border-radius: 8px;
}

/* 主内容区域 */
.main-content {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 0;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: white;
  border-radius: 8px;
}

/* 左侧面板标题 */
.left-panel-header {
  padding-bottom: 8px;
  margin-bottom: 16px;
  font-size: 15px;
  font-weight: 600;
  color: #111;
  border-bottom: 2px solid #e8e8e8;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex: 2;
  flex-direction: column;
  gap: 12px;
}

/* 卡片基础样式 */
.stats-card {
  padding: 12px;
  background: #fff;
  border-radius: 8px;
}

.card-title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #111;
}

.card-title.warning {
  color: #111;
}

/* 设备统计卡片 - 白色背景 */
.device-stats-card {
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.summary-row {
  display: flex;
  gap: 8px;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px dashed #d9d9d9;
}

/* 汇总项 - 移除彩色背景 */
.summary-item {
  flex: 1;
  padding: 8px;
  text-align: center;
  background: #f5f5f5;
  border-radius: 6px;
}

.summary-value {
  font-size: 20px;
  font-weight: 600;
}

/* 数字颜色类 */
.stat-blue {
  color: #3b82f6;
}

.stat-green {
  color: #22c55e;
}

.stat-red {
  color: #ef4444;
}

.summary-label {
  font-size: 11px;
}

.type-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.type-item {
  flex: 1;
  text-align: center;
}

/* 类型数字改为蓝色 */
.type-value {
  font-size: 18px;
  font-weight: 600;
  color: #3b82f6;
}

.type-label {
  font-size: 11px;
  color: #666;
}

.enabled-row {
  display: flex;
  gap: 8px;
}

.enabled-item {
  flex: 1;
  padding: 4px;
  font-size: 12px;
  text-align: center;
  border-radius: 4px;
}

.enabled-green {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}

.enabled-red {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

/* 离线机器卡片 */
.offline-card {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.offline-card .card-title {
  flex-shrink: 0;
}

.offline-list {
  flex: 1;
  min-height: 0;
}

.offline-item {
  display: flex;
  align-items: center;
  padding: 6px;
  margin-bottom: 4px;
  font-size: 12px;
  line-height: 1.8;
  color: #333;
  background: #fff5f5;
  border: 1px solid #fecaca;
  border-radius: 4px;
}

.offline-dot {
  margin-right: 4px;
  color: #fa8c16;
}

.offline-name {
  color: #333;
}

.offline-ip {
  margin-left: 2px;
  font-size: 11px;
  color: #666;
}

.offline-duration {
  margin-left: auto;
  color: #fa8c16;
}

/* 申请统计卡片 */
.apply-card {
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.apply-main {
  display: flex;
  gap: 16px;
  align-items: center;
}

.apply-total {
  flex: 1;
  text-align: center;
}

.apply-value {
  font-size: 28px;
  font-weight: 600;
  color: #3b82f6; /* 蓝色 */
}

.apply-label {
  font-size: 13px;
  color: #666;
}

.apply-detail {
  display: flex;
  flex: 2;
  gap: 12px;
}

.detail-item {
  flex: 1;
  padding: 8px;
  text-align: center;
  border-radius: 6px;
}

.detail-item.success {
  background: #f6ffed;
}

.detail-item.insufficient {
  background: #fff7e6;
}

.detail-item.failed {
  background: #fff2f0;
}

.detail-value {
  font-size: 18px;
  font-weight: 600;
}

.detail-value.success {
  color: #22c55e;
}

.detail-value.insufficient {
  color: #f59e0b;
}

.detail-value.failed {
  color: #ef4444;
}

.detail-label {
  font-size: 11px;
  color: #666;
}

/* TOP 卡片行 */
.top-cards-row {
  display: flex;
  gap: 12px;
}

.top-card {
  flex: 1;
}

.top-list {
  padding: 4px 8px;
}

.top-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.top-tag {
  width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
  color: #333;
  white-space: nowrap;
}

/* 申请次数 TOP10 - 蓝色 */
.top-bar {
  height: 14px;
  background: #3b82f6;
  border-radius: 3px;
}

/* 资源不足 TOP10 - 红色 */
.top-bar.red {
  background: #ef4444;
}

.top-count {
  margin-left: 6px;
  font-size: 11px;
  color: #666;
}

/* 占用时长卡片 */
.duration-card {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.duration-card .card-title {
  flex-shrink: 0;
}

.duration-list {
  flex: 1;
  height: 270px;
  min-height: 0;
}

.duration-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.duration-info {
  width: 100px;
}

.duration-ip {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: #333;
  white-space: nowrap;
}

.duration-type {
  font-size: 10px;
}

.duration-bar {
  height: 14px;
  background: #52c41a;
  border-radius: 3px;
}

.duration-value {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #52c41a;
}

/* 无数据 */
.no-data {
  padding: 20px;
  font-size: 12px;
  color: #999;
  text-align: center;
}
</style>