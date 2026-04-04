<script lang="ts" setup>
import type {
  DashboardStatsResponse,
  TopTagItem,
  TopDurationItem,
  OfflineMachineItem,
} from '#/api/core/device-monitor';

import { onMounted, onUnmounted, ref, computed } from 'vue';

import { Page } from '@vben/common-ui';

import { ElSelect, ElOption, ElButton, ElScrollbar } from 'element-plus';

import { getDashboardStatsApi } from '#/api/core/device-monitor';

defineOptions({ name: 'DeviceMonitorPage' });

// 数据
const loading = ref(false);
const stats = ref<DashboardStatsResponse | null>(null);
const namespace = ref<string>('');
const namespaceOptions = ref<string[]>([]);

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
    const res = await getDashboardStatsApi(namespace.value || undefined);
    stats.value = res;
  } catch (error) {
    console.error('加载统计数据失败:', error);
  } finally {
    loading.value = false;
  }
}

// 刷新
function handleRefresh() {
  loadStats();
}

// 计算柱状图宽度百分比
function getBarWidth(value: number, max: number): string {
  const percent = Math.min((value / max) * 100, 100);
  return `${Math.max(percent, 2)}%`;
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
      <!-- 顶部筛选栏 -->
      <div class="filter-bar">
        <div class="filter-left">
          <span class="filter-label">机器分类：</span>
          <ElSelect
            v-model="namespace"
            placeholder="全部"
            clearable
            style="width: 200px"
            @change="loadStats"
          >
            <ElOption
              v-for="opt in namespaceOptions"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </ElSelect>
        </div>
        <ElButton type="primary" :loading="loading" @click="handleRefresh">
          刷新数据
        </ElButton>
      </div>

      <!-- 主内容区域 -->
      <div v-loading="loading" class="main-content">
        <!-- 左侧面板 -->
        <div class="left-panel">
          <!-- 模块1：设备台数统计 -->
          <div class="stats-card device-stats-card">
            <div class="card-title">📊 设备台数统计</div>

            <!-- 汇总行 -->
            <div class="summary-row">
              <div class="summary-item purple">
                <div class="summary-value">{{ stats?.device_stats?.total || 0 }}</div>
                <div class="summary-label">总数</div>
              </div>
              <div class="summary-item green">
                <div class="summary-value">{{ stats?.device_stats?.online || 0 }}</div>
                <div class="summary-label">在线</div>
              </div>
              <div class="summary-item red">
                <div class="summary-value">{{ stats?.device_stats?.offline || 0 }}</div>
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
              <div class="enabled-item green">
                启用 {{ stats?.device_stats?.by_type?.reduce((sum, t) => sum + t.enabled, 0) || 0 }}
              </div>
              <div class="enabled-item red">
                未启用 {{ stats?.device_stats?.by_type?.reduce((sum, t) => sum + t.disabled, 0) || 0 }}
              </div>
            </div>
          </div>

          <!-- 模块6：异步机器排查 -->
          <div class="stats-card offline-card">
            <div class="card-title warning">⚠️ 异步机器排查（启用但离线）</div>
            <ElScrollbar class="offline-list" v-if="stats?.offline_machines?.length">
              <div
                v-for="item in stats?.offline_machines || []"
                :key="item.id"
                class="offline-item"
              >
                <span class="offline-dot">●</span>
                <span class="offline-info">
                  {{ item.ip || item.device_sn }}
                  <span class="offline-type">({{ deviceTypeNames[item.device_type] || item.device_type }})</span>
                </span>
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
                <div class="detail-item fail">
                  <div class="detail-value">{{ stats?.apply_24h?.failed || 0 }}</div>
                  <div class="detail-label">资源不足</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 模块3 & 5：TOP10 标签 -->
          <div class="top-cards-row">
            <!-- 申请次数 TOP10 -->
            <div class="stats-card top-card">
              <div class="card-title">📈 申请次数 TOP10 标签</div>
              <div class="top-list">
                <div
                  v-for="(item, index) in stats?.top10_tags || []"
                  :key="index"
                  class="top-item"
                >
                  <div class="top-tag">{{ item.tag }}</div>
                  <div
                    class="top-bar"
                    :style="{ width: getBarWidth(item.count, maxTagCount) }"
                  ></div>
                  <span class="top-count">{{ item.count }}</span>
                </div>
                <div v-if="!stats?.top10_tags?.length" class="no-data">暂无数据</div>
              </div>
            </div>

            <!-- 资源不足 TOP10 -->
            <div class="stats-card top-card">
              <div class="card-title warning">⚠️ 资源不足 TOP10 标签</div>
              <div class="top-list">
                <div
                  v-for="(item, index) in stats?.top10_insufficient || []"
                  :key="index"
                  class="top-item"
                >
                  <div class="top-tag">{{ item.tag }}</div>
                  <div
                    class="top-bar red"
                    :style="{ width: getBarWidth(item.count, maxInsufficientCount) }"
                  ></div>
                  <span class="top-count">{{ item.count }}</span>
                </div>
                <div v-if="!stats?.top10_insufficient?.length" class="no-data">暂无数据</div>
              </div>
            </div>
          </div>

          <!-- 模块4：占用时长 TOP20 -->
          <div class="stats-card duration-card">
            <div class="card-title">⏱️ 机器占用时长 TOP20</div>
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
                  :style="{ width: getBarWidth(item.duration_minutes, maxDuration) }"
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
  background: #f5f7fa;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
}

.filter-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: #666;
}

/* 主内容区域 */
.main-content {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

/* 左侧面板 */
.left-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 右侧面板 */
.right-panel {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 卡片基础样式 */
.stats-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: bold;
  color: #333;
  margin-bottom: 12px;
}

.card-title.warning {
  color: #fa8c16;
}

/* 设备统计卡片 */
.device-stats-card {
  background: #f9f0ff;
}

.summary-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #d9d9d9;
}

.summary-item {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 6px;
  color: #fff;
}

.summary-item.purple {
  background: #722ed1;
}

.summary-item.green {
  background: #52c41a;
}

.summary-item.red {
  background: #ff4d4f;
}

.summary-value {
  font-size: 20px;
  font-weight: bold;
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

.type-value {
  font-size: 18px;
  font-weight: bold;
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
  text-align: center;
  padding: 4px;
  border-radius: 4px;
  font-size: 12px;
  color: #fff;
}

.enabled-item.green {
  background: #52c41a;
}

.enabled-item.red {
  background: #ff4d4f;
}

/* 离线机器卡片 */
.offline-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff7e6;
  border: 1px solid #ffd591;
  min-height: 0;
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
  padding: 6px 8px;
  background: #fff;
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 12px;
}

.offline-dot {
  color: #fa8c16;
  margin-right: 8px;
}

.offline-info {
  flex: 1;
}

.offline-type {
  color: #999;
  font-size: 11px;
}

.offline-duration {
  color: #fa8c16;
}

/* 申请统计卡片 */
.apply-card {
  border: 2px solid #1890ff;
}

.apply-main {
  display: flex;
  align-items: center;
  gap: 16px;
}

.apply-total {
  text-align: center;
}

.apply-value {
  font-size: 32px;
  font-weight: bold;
  color: #1890ff;
}

.apply-label {
  font-size: 13px;
  color: #666;
}

.apply-detail {
  flex: 1;
  display: flex;
  gap: 12px;
}

.detail-item {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 6px;
}

.detail-item.success {
  background: #f6ffed;
}

.detail-item.fail {
  background: #fff2f0;
}

.detail-value {
  font-size: 18px;
  font-weight: bold;
}

.detail-item.success .detail-value {
  color: #52c41a;
}

.detail-item.fail .detail-value {
  color: #ff4d4f;
}

.detail-label {
  font-size: 11px;
  color: #666;
}

/* TOP 卡片行 */
.top-cards-row {
  display: flex;
  gap: 16px;
}

.top-card {
  flex: 1;
}

.top-list {
  height: 200px;
}

.top-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.top-tag {
  width: 80px;
  font-size: 11px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-bar {
  height: 14px;
  background: #1890ff;
  border-radius: 3px;
  min-width: 4px;
  max-width: 150px;
}

.top-bar.red {
  background: #ff4d4f;
}

.top-count {
  font-size: 11px;
  color: #666;
  margin-left: 6px;
}

/* 占用时长卡片 */
.duration-card {
  flex: 1;
  display: flex;
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
  font-size: 12px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.duration-type {
  font-size: 10px;
}

.duration-bar {
  height: 14px;
  background: #52c41a;
  border-radius: 3px;
  min-width: 4px;
  max-width: 200px;
}

.duration-value {
  font-size: 11px;
  color: #52c41a;
  margin-left: 6px;
  font-weight: 500;
}

/* 无数据 */
.no-data {
  color: #999;
  font-size: 12px;
  text-align: center;
  padding: 20px;
}
</style>