<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { Close } from '@element-plus/icons-vue';

interface Props {
  visible: boolean;
  metrics: { key: string; label: string }[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:visible': [value: boolean];
  select: [metric: string];
}>();

const RECENT_SEARCH_KEY = 'performance-monitor-recent-metrics';
const MAX_RECENT = 3;

const searchKeyword = ref('');
const recentSearches = ref<string[]>([]);

// 从 localStorage 加载最近搜索
function loadRecentSearches(): string[] {
  try {
    // SSR 兼容：检查 localStorage 是否存在
    const stored = typeof localStorage !== 'undefined'
      ? localStorage.getItem(RECENT_SEARCH_KEY)
      : null;
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

// 保存最近搜索到 localStorage
function saveRecentSearches(searches: string[]) {
  try {
    // SSR 兼容：检查 localStorage 是否存在
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(searches));
    }
  } catch (error) {
    console.warn('保存最近搜索失败:', error);
  }
}

// 初始化加载最近搜索
recentSearches.value = loadRecentSearches();

// 过滤后的结果
const filteredMetrics = computed(() => {
  if (!searchKeyword.value.trim()) return props.metrics;
  const keyword = searchKeyword.value.trim().toLowerCase();
  return props.metrics.filter(m =>
    m.key.toLowerCase().includes(keyword) ||
    m.label.toLowerCase().includes(keyword)
  );
});

function handleClose() {
  emit('update:visible', false);
}

function handleSelect(metric: string) {
  // 更新最近搜索列表
  const recent = recentSearches.value.filter(m => m !== metric);
  recentSearches.value = [metric, ...recent].slice(0, MAX_RECENT);
  saveRecentSearches(recentSearches.value);

  emit('select', metric);
  emit('update:visible', false);
}

function handleRecentClick(metric: string) {
  handleSelect(metric);
}

// 弹窗关闭时清空搜索关键词
watch(() => props.visible, (newVal) => {
  if (!newVal) {
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
  <div v-if="visible" class="metric-search-popup">
    <div class="popup-header">
      <span class="popup-title">选择指标</span>
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
          v-for="(metric, index) in recentSearches"
          :key="metric"
          class="recent-tag"
          :class="`recent-tag-${index + 1}`"
          @click="handleRecentClick(metric)"
        >
          {{ metrics.find(m => m.key === metric)?.label || metric }}
        </span>
      </div>
    </div>

    <div class="popup-results">
      <span class="results-label">搜索结果:</span>
      <div class="results-list">
        <div
          v-for="metric in filteredMetrics"
          :key="metric.key"
          class="result-item"
          @click="handleSelect(metric.key)"
        >
          <span class="result-label">{{ metric.label }}</span>
          <span class="result-key">{{ metric.key }}</span>
        </div>
        <div v-if="filteredMetrics.length === 0" class="no-results">
          暂无匹配结果
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-search-popup {
  position: absolute;
  top: 50px;
  right: 0;
  z-index: 100;
  width: 350px;
  padding: 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgb(0 0 0 / 15%);
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.popup-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.close-icon {
  font-size: 18px;
  color: #999;
  cursor: pointer;
  transition: color 0.3s;
}

.close-icon:hover {
  color: #666;
}

.popup-search {
  margin-bottom: 12px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  font-size: 13px;
  outline: none;
  border: 1px solid #ddd;
  border-radius: 6px;
  transition: border-color 0.3s;
}

.search-input:focus {
  border-color: #409eff;
}

.popup-recent {
  margin-bottom: 12px;
}

.recent-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: #999;
}

.recent-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.recent-tag {
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.3s;
}

.recent-tag-1 {
  color: #1890ff;
  background: #e6f7ff;
}

.recent-tag-2 {
  color: #52c41a;
  background: #f6ffed;
}

.recent-tag-3 {
  color: #fa8c16;
  background: #fff7e6;
}

.recent-tag:hover {
  opacity: 0.8;
  transform: translateY(-1px);
}

.popup-results {
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.results-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: #999;
}

.results-list {
  max-height: 180px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.result-item:hover {
  background: #f5f5f5;
}

.result-label {
  flex: 1;
  color: #333;
}

.result-key {
  margin-left: 12px;
  font-size: 11px;
  color: #999;
}

.no-results {
  padding: 16px;
  font-size: 13px;
  color: #999;
  text-align: center;
}
</style>