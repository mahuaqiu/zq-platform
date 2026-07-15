<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { ElIcon } from 'element-plus';
import { Close } from '@element-plus/icons-vue';
import { getAvailableMetrics, type AvailableMetric } from '#/api/core/performance-monitor';
import { getMetricLabel } from '../hwinfo-metrics-config';

interface Props {
  visible: boolean;
  collectId?: string;
  isLinuxDevice?: boolean;  // 是否为 Linux 设备，用于过滤重复指标和隔离搜索记录
}

const props = withDefaults(defineProps<Props>(), {
  collectId: '',
  isLinuxDevice: false,
});

const emit = defineEmits<{
  'update:visible': [value: boolean];
  select: [metric: string];
}>();

// 按设备类型隔离最近搜索记录
const getRecentSearchKey = () => {
  const deviceType = props.isLinuxDevice ? 'linux' : 'windows';
  return `performance-monitor-recent-metrics-${deviceType}`;
};
const MAX_RECENT = 5;

const searchKeyword = ref('');
const recentSearches = ref<string[]>([]);
const metrics = ref<AvailableMetric[]>([]);
const loading = ref(false);

// 从 localStorage 加载最近搜索（按设备类型）
function loadRecentSearches(): string[] {
  try {
    const key = getRecentSearchKey();
    const stored = typeof localStorage !== 'undefined'
      ? localStorage.getItem(key)
      : null;
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

// 保存最近搜索到 localStorage（按设备类型）
function saveRecentSearches(searches: string[]) {
  try {
    const key = getRecentSearchKey();
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(searches));
    }
  } catch (error) {
    console.warn('保存最近搜索失败:', error);
  }
}

// 初始化加载最近搜索
recentSearches.value = loadRecentSearches();

// 监听设备类型变化，重新加载对应的最近搜索记录
watch(() => props.isLinuxDevice, () => {
  recentSearches.value = loadRecentSearches();
});

// 加载指标列表
async function loadMetrics() {
  if (!props.collectId) return;
  loading.value = true;
  try {
    const result = await getAvailableMetrics(props.collectId);
    metrics.value = result.items;
  } catch (error) {
    console.error('加载指标列表失败:', error);
  } finally {
    loading.value = false;
  }
}

// 获取显示名称（优先使用中文翻译）
function getDisplayLabel(metric: AvailableMetric): string {
  if (metric.source === 'system') {
    return metric.label; // 进程指标已有中文
  }
  // HWiNFO 指标尝试从配置文件获取中文翻译
  const translated = getMetricLabel(metric.key);
  return translated !== metric.key ? translated : metric.label;
}

// 过滤后的结果
const filteredMetrics = computed(() => {
  if (!searchKeyword.value.trim()) return metrics.value;
  const keyword = searchKeyword.value.trim().toLowerCase();
  return metrics.value.filter(m =>
    m.key.toLowerCase().includes(keyword) ||
    m.label.toLowerCase().includes(keyword) ||
    getDisplayLabel(m).toLowerCase().includes(keyword)
  );
});

// Linux 设备下，过滤掉与快捷按钮重复的核心指标
// Linux CPU Usage -> 对应 CPU 快捷按钮
// Linux Memory Usage -> 对应 内存 快捷按钮
const linuxMetricsFiltered = computed<AvailableMetric[]>(() => []);

// 分组显示：进程指标、Linux 系统指标、HWiNFO 指标
const systemMetrics = computed(() =>
  filteredMetrics.value.filter(m => m.source === 'system')
);
const linuxMetrics = computed(() => linuxMetricsFiltered.value);
const hwinfoMetrics = computed(() =>
  filteredMetrics.value.filter(m => m.source === 'hwinfo')
);

function handleClose() {
  emit('update:visible', false);
}

function handleSelect(metricKey: string) {
  const recent = recentSearches.value.filter(m => m !== metricKey);
  recentSearches.value = [metricKey, ...recent].slice(0, MAX_RECENT);
  saveRecentSearches(recentSearches.value);

  emit('select', metricKey);
  emit('update:visible', false);
}

function handleRecentClick(metricKey: string) {
  handleSelect(metricKey);
}

// 弹窗打开时加载指标列表
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadMetrics();
  } else {
    searchKeyword.value = '';
  }
});

// 键盘交互支持
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    emit('update:visible', false);
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
  <!-- 遮罩层 -->
  <div v-if="visible" class="popup-overlay" @click="handleClose"></div>
  <!-- 弹窗主体 -->
  <div v-if="visible" class="metric-search-popup">
    <div class="popup-header">
      <span class="popup-title">性能指标搜索</span>
      <el-icon class="close-icon" @click="handleClose">
        <Close />
      </el-icon>
    </div>

    <div class="popup-search">
      <input
        v-model="searchKeyword"
        class="search-input"
        placeholder="搜索指标名称..."
      />
    </div>

    <div v-if="recentSearches.length > 0" class="popup-recent">
      <span class="recent-label">最近搜索:</span>
      <div class="recent-tags">
        <span
          v-for="(metricKey, index) in recentSearches"
          :key="metricKey"
          class="recent-tag"
          :class="`recent-tag-${index + 1}`"
          @click="handleRecentClick(metricKey)"
        >
          {{ metrics.find(m => m.key === metricKey)?.label || metricKey }}
        </span>
      </div>
    </div>

    <div class="popup-results">
      <div v-if="loading" class="loading-state">
        <span class="loading-text">加载中...</span>
      </div>

      <template v-else>
        <!-- 进程指标 -->
        <div v-if="systemMetrics.length > 0" class="metric-group">
          <span class="group-label">进程指标</span>
          <div class="results-list">
            <div
              v-for="metric in systemMetrics"
              :key="metric.key"
              class="result-item system-item"
              @click="handleSelect(metric.key)"
            >
              <span class="result-label">{{ metric.label }}</span>
              <span class="result-source">进程</span>
            </div>
          </div>
        </div>

        <!-- Linux 系统指标 -->
        <div v-if="linuxMetrics.length > 0" class="metric-group">
          <span class="group-label">Linux 系统指标 ({{ linuxMetrics.length }})</span>
          <div class="results-list">
            <div
              v-for="metric in linuxMetrics"
              :key="metric.key"
              class="result-item linux-item"
              @click="handleSelect(metric.key)"
            >
              <span class="result-label">{{ getDisplayLabel(metric) }}</span>
              <span class="result-source linux-source">Linux</span>
            </div>
          </div>
        </div>

        <!-- HWiNFO 指标 -->
        <div v-if="hwinfoMetrics.length > 0" class="metric-group">
          <span class="group-label">HWiNFO 传感器 ({{ hwinfoMetrics.length }})</span>
          <div class="results-list hwinfo-list">
            <div
              v-for="metric in hwinfoMetrics"
              :key="metric.key"
              class="result-item"
              @click="handleSelect(metric.key)"
            >
              <span class="result-label">{{ getDisplayLabel(metric) }}</span>
              <span class="result-key">{{ metric.key }}</span>
            </div>
          </div>
        </div>

        <div v-if="filteredMetrics.length === 0 && searchKeyword.trim() && !loading" class="no-results">
          暂无匹配结果
        </div>

        <div v-if="metrics.length === 0 && !loading" class="no-data-tip">
          请先选择采集记录
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.popup-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99;
  background: rgb(0 0 0 / 40%);
  backdrop-filter: blur(2px);
}

.metric-search-popup {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 100;
  width: 420px;
  max-height: 80vh;
  padding: 20px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgb(0 0 0 / 20%);
  border: 1px solid #e8e8e8;
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.popup-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}

.close-icon {
  font-size: 20px;
  color: #999;
  cursor: pointer;
  transition: all 0.3s;
  padding: 4px;
  border-radius: 4px;
}

.close-icon:hover {
  color: #ff4d4f;
  background: #fff1f0;
}

.popup-search {
  margin-bottom: 16px;
}

.search-input {
  width: 100%;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  transition: all 0.3s;
  background: #fafafa;
}

.search-input:focus {
  border-color: #409eff;
  background: white;
  box-shadow: 0 0 0 2px rgb(64 158 255 / 20%);
}

.search-input::placeholder {
  color: #bfbfbf;
}

.popup-recent {
  margin-bottom: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.recent-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: #8c8c8c;
  font-weight: 500;
}

.recent-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.recent-tag {
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.3s;
  font-weight: 500;
}

.recent-tag-1 {
  color: #1890ff;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

.recent-tag-2 {
  color: #52c41a;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.recent-tag-3 {
  color: #fa8c16;
  background: #fff7e6;
  border: 1px solid #ffd591;
}

.recent-tag-4 {
  color: #722ed1;
  background: #f9f0ff;
  border: 1px solid #d3adf7;
}

.recent-tag-5 {
  color: #13c2c2;
  background: #e6fffb;
  border: 1px solid #87e8de;
}

.recent-tag:hover {
  opacity: 0.85;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgb(0 0 0 / 10%);
}

.popup-results {
  padding-top: 16px;
}

.metric-group {
  margin-bottom: 16px;
}

.group-label {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
  color: #8c8c8c;
  font-weight: 500;
}

.results-list {
  max-height: 200px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #d9d9d9 transparent;
}

.results-list::-webkit-scrollbar {
  width: 6px;
}

.results-list::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 3px;
}

.results-list::-webkit-scrollbar-track {
  background: transparent;
}

.hwinfo-list {
  max-height: 280px;
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  font-size: 14px;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.3s;
  margin-bottom: 4px;
}

.result-item:hover {
  background: #f5f7fa;
  transform: translateX(2px);
}

.system-item {
  background: #f0f5ff;
}

.system-item:hover {
  background: #e6f0ff;
}

.linux-item {
  background: #f0f9eb;
}

.linux-item:hover {
  background: #e6f7dc;
}

.linux-source {
  color: #67c23a;
  background: #f0f9eb;
}

.result-label {
  flex: 1;
  color: #1a1a1a;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-source {
  margin-left: 12px;
  font-size: 11px;
  color: #1890ff;
  background: #e6f7ff;
  padding: 2px 8px;
  border-radius: 4px;
}

.result-key {
  margin-left: 12px;
  font-size: 11px;
  color: #bfbfbf;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loading-state {
  padding: 24px 16px;
  text-align: center;
}

.loading-text {
  color: #409eff;
  font-size: 14px;
}

.no-results {
  padding: 24px 16px;
  font-size: 14px;
  color: #bfbfbf;
  text-align: center;
  background: #fafafa;
  border-radius: 8px;
}

.no-data-tip {
  padding: 24px 16px;
  font-size: 13px;
  color: #8c8c8c;
  text-align: center;
  background: #fafafa;
  border-radius: 8px;
}
</style>