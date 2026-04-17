<script lang="ts" setup>
import type { DashboardStatsResponse } from '#/api/core/device-monitor';

import { onMounted, onUnmounted, ref, computed } from 'vue';

import { Page } from '@vben/common-ui';

import { ElScrollbar, ElSelect, ElOption, ElTag } from 'element-plus';

import { getDashboardStatsApi } from '#/api/core/device-monitor';
import { NAMESPACE_OPTIONS } from '#/views/env-machine/types';

defineOptions({ name: 'DeviceMonitorPage' });

// namespace 选项（排除"全部"选项）
const namespaceOptions = computed(() => {
  return NAMESPACE_OPTIONS.filter(opt => opt.value !== '');
});

// 判断是否选中了所有 namespace
const isAllSelected = computed(() => {
  return selectedNamespaces.value.length === namespaceOptions.value.length;
});

// 自定义显示文本
const selectDisplayText = computed(() => {
  if (isAllSelected.value) {
    return '全部';
  }
  return '';
});

// 数据
const loading = ref(false);
const stats = ref<DashboardStatsResponse | null>(null);
// 默认选中所有配置的 namespace
const selectedNamespaces = ref<string[]>(namespaceOptions.value.map(opt => opt.value));

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

// 加载数据
async function loadStats() {
  loading.value = true;
  try {
    // 传递选中的 namespace 列表（逗号分隔）
    // 如果没有选中任何 namespace，传递空字符串让后端返回空数据
    const namespaceParam = selectedNamespaces.value.length > 0
      ? selectedNamespaces.value.join(',')
      : '';
    const res = await getDashboardStatsApi(namespaceParam);
    stats.value = res;
  } catch (error) {
    console.error('加载统计数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// namespace 变化时重新加载数据（防止清空所有选项）
function handleNamespaceChange(val: string[]) {
  // 如果清空了所有选项，恢复到选中所有
  if (val.length === 0) {
    selectedNamespaces.value = namespaceOptions.value.map(opt => opt.value);
  }
  loadStats();
}

// 初始化
onMounted(() => {
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
      <!-- 页面顶部标题栏 -->
      <div class="page-header">
        <h1 class="page-title">设备监控</h1>
        <ElSelect
          v-model="selectedNamespaces"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="请选择 Namespace"
          style="width: 250px"
          @change="handleNamespaceChange"
        >
          <template #tag>
            <ElTag v-if="isAllSelected" type="info">全部</ElTag>
            <template v-else>
              <ElTag
                v-for="ns in selectedNamespaces.slice(0, 1)"
                :key="ns"
                type="info"
              >
                {{ namespaceOptions.find(opt => opt.value === ns)?.label || ns }}
              </ElTag>
              <ElTag v-if="selectedNamespaces.length > 1" type="info">
                +{{ selectedNamespaces.length - 1 }}
              </ElTag>
            </template>
          </template>
          <ElOption
            v-for="opt in namespaceOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </ElSelect>
      </div>

      <!-- 主内容区域 -->
      <div v-loading="loading" class="main-content">
        <!-- 左侧面板 -->
        <div class="left-panel">
          <!-- 设备台数统计 -->
          <div class="stats-card device-stats-card">
            <div class="card-title">设备台数统计</div>

            <!-- 汇总行 -->
            <div class="summary-row">
              <div class="summary-item">
                <span class="summary-value stat-blue">{{ stats?.device_stats?.total || 0 }}</span>
                <span class="summary-label">总数</span>
              </div>
              <div class="summary-item">
                <span class="summary-value stat-green">{{ stats?.device_stats?.online || 0 }}</span>
                <span class="summary-label">在线</span>
              </div>
              <div class="summary-item">
                <span class="summary-value stat-red">{{ stats?.device_stats?.offline || 0 }}</span>
                <span class="summary-label">离线</span>
              </div>
            </div>

            <!-- 按类型统计 -->
            <div class="type-row">
              <div
                v-for="item in stats?.device_stats?.by_type || []"
                :key="item.type"
                class="type-item"
              >
                <div class="type-value stat-blue">{{ item.total }}</div>
                <div class="type-label">{{ deviceTypeNames[item.type] || item.type }}</div>
              </div>
            </div>

            <!-- 启用/未启用 -->
            <div class="enabled-row">
              <div class="enabled-item enabled-green">启用 {{ stats?.device_stats?.by_type?.reduce((sum, t) => sum + t.enabled, 0) || 0 }}</div>
              <div class="enabled-item enabled-red">未启用 {{ stats?.device_stats?.by_type?.reduce((sum, t) => sum + t.disabled, 0) || 0 }}</div>
            </div>
          </div>

          <!-- 异步机器排查 -->
          <div class="stats-card offline-card">
            <div class="card-title">
              异步机器排查
            </div>
            <div class="card-subtitle">（启用但离线）</div>
            <ElScrollbar class="offline-list" v-if="stats?.offline_machines?.length">
              <div
                v-for="item in stats?.offline_machines || []"
                :key="item.id"
                class="offline-item"
              >
                <span class="offline-dot"></span>
                <span class="offline-name">{{ item.name || item.ip || item.device_sn }}</span>
                <span class="offline-ip">{{ item.ip || item.device_sn }}</span>
                <span class="offline-duration">离线 {{ item.offline_duration }}</span>
              </div>
            </ElScrollbar>
            <div v-else class="no-data">暂无更多离线设备</div>
          </div>
        </div>

        <!-- 右侧面板 -->
        <div class="right-panel">
          <!-- 24小时申请统计 -->
          <div class="stats-card apply-card">
            <div class="card-title">24小时申请统计</div>
            <div class="apply-main">
              <div class="apply-total">
                <div class="apply-value stat-blue">{{ stats?.apply_24h?.total || 0 }}</div>
                <div class="apply-label">申请总次数</div>
              </div>
              <div class="apply-detail">
                <div class="detail-item success">
                  <div class="detail-value stat-green">{{ stats?.apply_24h?.success || 0 }}</div>
                  <div class="detail-label">成功</div>
                </div>
                <div class="detail-item insufficient">
                  <div class="detail-value stat-orange">{{ stats?.apply_24h?.failed || 0 }}</div>
                  <div class="detail-label">资源不足</div>
                </div>
                <div class="detail-item failed">
                  <div class="detail-value stat-red">{{ otherFailedCount }}</div>
                  <div class="detail-label">失败</div>
                </div>
              </div>
            </div>
          </div>

          <!-- TOP10 标签 -->
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
                  <span class="top-tag">{{ item.tag }}</span>
                  <div class="top-bar-bg">
                    <div
                      class="top-bar"
                      :style="{ width: getTagBarWidth(item.count) }"
                    ></div>
                  </div>
                  <span class="top-count stat-blue">{{ item.count }}</span>
                </div>
                <div v-if="!stats?.top10_tags?.length" class="no-data">暂无数据</div>
              </div>
            </div>

            <!-- 资源不足 TOP10 -->
            <div class="stats-card top-card">
              <div class="card-title">
                资源不足 TOP10 标签
              </div>
              <div v-if="stats?.top10_insufficient?.length" class="card-subtitle">设备资源紧张，需关注</div>
              <div class="top-list">
                <div
                  v-for="(item, index) in stats?.top10_insufficient || []"
                  :key="index"
                  class="top-item"
                >
                  <span class="top-tag">{{ item.tag }}</span>
                  <div class="top-bar-bg">
                    <div
                      class="top-bar red"
                      :style="{ width: getInsufficientBarWidth(item.count) }"
                    ></div>
                  </div>
                  <span class="top-count stat-red">{{ item.count }}</span>
                </div>
                <div v-if="!stats?.top10_insufficient?.length" class="no-data">暂无数据</div>
              </div>
            </div>
          </div>

          <!-- 占用时长 TOP20 -->
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
                  <div class="duration-type">{{ deviceTypeNames[item.device_type] || item.device_type }}</div>
                </div>
                <div class="duration-bar-bg">
                  <div
                    class="duration-bar"
                    :style="{ width: getDurationBarWidth(item.duration_minutes) }"
                  ></div>
                </div>
                <span class="duration-value stat-green">{{ item.duration_display }}</span>
              </div>
              <div v-if="!stats?.top20_duration?.length" class="no-data">更多数据请向下滚动查看</div>
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
  background: #f0f2f5;
}

/* 页面顶部标题栏 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #111;
}

/* 主内容区域 */
.main-content {
  display: flex;
  flex: 1;
  gap: 20px;
  padding: 24px;
  min-height: 0;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex: 2;
  flex-direction: column;
  gap: 20px;
}

/* 卡片基础样式 */
.stats-card {
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.card-title {
  margin-bottom: 16px;
  font-size: 15px;
  font-weight: 600;
  color: #111;
}

.card-subtitle {
  margin-bottom: 12px;
  font-size: 12px;
  color: #999;
}

/* 设备统计卡片 */
.device-stats-card {
  /* 继承基础样式 */
}

.summary-row {
  display: flex;
  gap: 32px;
  padding-bottom: 20px;
  margin-bottom: 20px;
  border-bottom: 1px solid #e8e8e8;
}

.summary-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.summary-value {
  font-size: 32px;
  font-weight: 600;
}

.summary-label {
  font-size: 13px;
  color: #666;
}

/* 数字颜色 */
.stat-blue {
  color: #3b82f6;
}

.stat-green {
  color: #22c55e;
}

.stat-red {
  color: #ef4444;
}

.stat-orange {
  color: #f59e0b;
}

.type-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.type-item {
  flex: 1;
  padding: 12px;
  text-align: center;
  background: #f5f5f5;
  border-radius: 8px;
}

.type-value {
  font-size: 24px;
  font-weight: 600;
}

.type-label {
  font-size: 12px;
  color: #666;
}

.enabled-row {
  display: flex;
  gap: 16px;
}

.enabled-item {
  flex: 1;
  padding: 10px;
  font-size: 14px;
  text-align: center;
  border-radius: 6px;
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
}

.offline-card .card-title {
  margin-bottom: 4px;
}

.offline-card .card-subtitle {
  margin-bottom: 12px;
}

.offline-list {
  flex: 1;
  min-height: 0;
}

.offline-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  background: #fff5f5;
  border: 1px solid #fecaca;
  border-radius: 8px;
}

.offline-dot {
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
}

.offline-name {
  flex: 1;
  font-size: 13px;
  color: #111;
}

.offline-ip {
  font-size: 12px;
  color: #666;
}

.offline-duration {
  font-size: 12px;
  color: #ef4444;
}

/* 申请统计卡片 */
.apply-card {
  /* 继承基础样式 */
}

.apply-main {
  display: flex;
  gap: 24px;
  align-items: center;
}

.apply-total {
  flex: 1;
  padding: 16px;
  text-align: center;
  background: #f5f5f5;
  border-radius: 8px;
}

.apply-value {
  font-size: 32px;
  font-weight: 600;
}

.apply-label {
  font-size: 13px;
  color: #666;
}

.apply-detail {
  display: flex;
  flex: 2;
  gap: 16px;
}

.detail-item {
  flex: 1;
  padding: 16px;
  text-align: center;
  border-radius: 8px;
}

.detail-item.success {
  background: #dcfce7;
  border: 1px solid #86efac;
}

.detail-item.insufficient {
  background: #fef3c7;
  border: 1px solid #fcd34d;
}

.detail-item.failed {
  background: #fee2e2;
  border: 1px solid #fecaca;
}

.detail-value {
  font-size: 24px;
  font-weight: 600;
}

.detail-label {
  font-size: 12px;
  color: #666;
}

/* TOP 卡片行 */
.top-cards-row {
  display: flex;
  gap: 20px;
}

.top-card {
  flex: 1;
}

.top-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.top-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.top-tag {
  width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

/* 进度条背景轨道 */
.top-bar-bg {
  flex: 1;
  height: 12px;
  background: #e5e5e5;
  border-radius: 3px;
  position: relative;
}

.top-bar {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: #3b82f6;
  border-radius: 3px;
}

.top-bar.red {
  background: #ef4444;
}

.top-count {
  width: 40px;
  font-size: 12px;
}

/* 占用时长卡片 */
.duration-card {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.duration-card .card-title {
  margin-bottom: 16px;
}

.duration-list {
  flex: 1;
  min-height: 0;
}

.duration-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.duration-info {
  width: 100px;
}

.duration-ip {
  font-size: 12px;
  color: #111;
}

.duration-type {
  font-size: 11px;
  color: #666;
}

/* 进度条背景轨道 */
.duration-bar-bg {
  flex: 1;
  height: 14px;
  background: #e5e5e5;
  border-radius: 3px;
  position: relative;
}

.duration-bar {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: #22c55e;
  border-radius: 3px;
}

.duration-value {
  width: 60px;
  font-size: 12px;
}

/* 无数据 */
.no-data {
  padding: 16px 20px;
  font-size: 13px;
  color: #999;
  text-align: center;
}
</style>