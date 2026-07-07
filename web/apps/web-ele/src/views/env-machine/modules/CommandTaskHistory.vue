<script lang="ts" setup>
import type { CommandTask } from '#/api/core/env-machine-config';
import { getCommandTaskListApi, deleteCommandTaskApi } from '#/api/core/env-machine-config';
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';

defineOptions({ name: 'CommandTaskHistory' });

// 加载状态
const loading = ref(false);

// 数据
const taskList = ref<CommandTask[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);

// 展开的任务ID
const expandedTasks = ref<Set<string>>(new Set());

// 每台机器 stdout/stderr 折叠状态：key = `${task.id}::${machine_id}::${kind}`
// 默认折叠，避免机器多/输出长导致列表只剩一两条
const expandedOutputs = ref<Set<string>>(new Set());

function outputKey(taskId: string, machineId: string, kind: string): string {
  return `${taskId}::${machineId}::${kind}`;
}

function toggleOutput(taskId: string, machineId: string, kind: string): void {
  const k = outputKey(taskId, machineId, kind);
  if (expandedOutputs.value.has(k)) {
    expandedOutputs.value.delete(k);
  } else {
    expandedOutputs.value.add(k);
  }
}

// 是否存在未结束的任务（running/pending），用于驱动轮询
const hasRunning = computed(() =>
  taskList.value.some(
    (t) => t.status === 'running' || t.status === 'pending',
  ),
);

// 轮询定时器
let pollTimer: ReturnType<typeof setInterval> | null = null;
const POLL_INTERVAL = 3000;

// 格式化时间
// 优先用 sys_create_datetime，回退到 finished_datetime（兼容历史任务 create 为 null 的情况）
function formatTime(time?: string, fallback?: string): string {
  const val = time || fallback;
  if (!val) return '-';
  return new Date(val).toLocaleString('zh-CN');
}

// 获取状态显示
function getStatusDisplay(status: string): { text: string; type: string } {
  const map: Record<string, { text: string; type: string }> = {
    running: { text: '执行中', type: 'warning' },
    success: { text: '成功', type: 'success' },
    failed: { text: '失败', type: 'danger' },
    partial: { text: '部分成功', type: 'warning' },
  };
  return map[status] || { text: status, type: 'info' };
}

// 加载任务列表
// silent=true 时为轮询触发：不显示 loading、不弹错误 toast，避免界面闪烁和反复弹窗
async function loadTasks(silent: boolean = false) {
  if (!silent) {
    loading.value = true;
  }
  try {
    const data = await getCommandTaskListApi({
      page: currentPage.value,
      page_size: pageSize.value,
    });
    // 客户端按时间倒序再排一次，保证「最近执行」在最上面
    // 主排序键 sys_create_datetime，回退到 finished_datetime（兼容历史脏数据）
    // 历史任务 sys_create_datetime 可能为 null，回退到 finished_datetime 才能正确排序
    const items = (data.items || []).slice();
    items.sort((a, b) => {
      const parseTime = (val: any): number => {
        if (!val) return 0;
        const t = new Date(val).getTime();
        return isNaN(t) ? 0 : t;
      };
      const ta = parseTime(a.sys_create_datetime) || parseTime(a.finished_datetime);
      const tb = parseTime(b.sys_create_datetime) || parseTime(b.finished_datetime);
      return tb - ta;
    });
    taskList.value = items;
    total.value = data.total;
  } catch (error) {
    if (!silent) {
      ElMessage.error('加载任务历史失败');
    }
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
}

// 切换展开状态
function toggleExpand(taskId: string) {
  if (expandedTasks.value.has(taskId)) {
    expandedTasks.value.delete(taskId);
  } else {
    expandedTasks.value.add(taskId);
  }
}

// 删除任务
async function handleDelete(task: CommandTask) {
  try {
    await ElMessageBox.confirm(`确定要删除任务"${task.template_name}"吗？`, '提示', {
      type: 'warning',
    });
    await deleteCommandTaskApi(task.id);
    ElMessage.success('删除成功');
    await loadTasks();
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
}

// 启动轮询
function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    loadTasks(true);
  }, POLL_INTERVAL);
}

// 停止轮询
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

// 监听 running 状态：有 running 时启动轮询，全部完成后停止
watch(hasRunning, (running) => {
  if (running) {
    startPolling();
  } else {
    stopPolling();
  }
});

// 翻页时停止轮询，避免列表切换期间产生无意义请求
function handlePageChange(page: number) {
  stopPolling();
  currentPage.value = page;
  loadTasks();
}

// 初始化
onMounted(async () => {
  await loadTasks();
  // 首次加载如果已经有 running 任务，启动轮询等待后端写结果
  if (hasRunning.value) {
    startPolling();
  }
});

// 组件销毁时清理定时器
onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="task-history">
    <!-- 统计信息 -->
    <div class="stats-row">
      <span>共 {{ total }} 条任务记录</span>
    </div>

    <!-- 任务列表 -->
    <div class="task-list" v-loading="loading">
      <div v-if="taskList.length === 0 && !loading" class="empty-tip">
        暂无任务记录
      </div>

      <div
        v-for="task in taskList"
        :key="task.id"
        class="task-item"
        :class="{ 'task-expanded': expandedTasks.has(task.id) }"
      >
        <!-- 任务概览 -->
        <div class="task-header" @click="toggleExpand(task.id)">
          <div class="task-info">
            <div class="task-title-row">
              <span class="task-name">{{ task.template_name }}</span>
              <span class="task-type-badge">{{ task.template_type === 'command' ? '运行命令' : task.template_type === 'script' ? '脚本' : '配置' }}</span>
            </div>
            <div class="task-time" :title="`执行时间: ${formatTime(task.sys_create_datetime, task.finished_datetime)}`">
              🕒 {{ formatTime(task.sys_create_datetime, task.finished_datetime) }}
            </div>
          </div>
          <div class="task-stats">
            <el-tag :type="getStatusDisplay(task.status).type" size="small">
              {{ getStatusDisplay(task.status).text }}
            </el-tag>
            <span class="stat-item">
              成功: <strong class="success">{{ task.success_count }}</strong>
            </span>
            <span class="stat-item">
              失败: <strong class="failed">{{ task.failed_count }}</strong>
            </span>
            <span class="stat-item">/ {{ task.machine_count }} 台</span>
          </div>
          <div class="task-actions" @click.stop>
            <el-button type="danger" size="small" link @click="handleDelete(task)">
              删除
            </el-button>
          </div>
        </div>

        <!-- 展开的详情 -->
        <div v-if="expandedTasks.has(task.id)" class="task-detail">
          <div v-if="task.template_type === 'command'" class="command-content">
            <div class="detail-label">命令内容：</div>
            <pre class="command-code">{{ task.command }}</pre>
          </div>

          <div class="detail-label">执行结果：</div>
          <div class="result-list">
            <div
              v-for="result in task.result_detail"
              :key="result.machine_id"
              class="result-item"
              :class="{ 'result-success': result.success, 'result-failed': !result.success }"
            >
              <div class="result-header">
                <span class="result-icon">{{ result.success ? '✓' : '✗' }}</span>
                <span class="result-ip">{{ result.ip }}</span>
                <span class="result-device">({{ result.device_type }})</span>
                <span class="result-duration">{{ result.duration_seconds?.toFixed(1) }}s</span>
              </div>
              <template v-if="result.stdout">
                <div class="output-toggle">
                  <el-button
                    type="primary"
                    size="small"
                    @click.stop="toggleOutput(task.id, result.machine_id, 'stdout')"
                  >
                    <template v-if="expandedOutputs.has(outputKey(task.id, result.machine_id, 'stdout'))">
                      收起 stdout
                    </template>
                    <template v-else>
                      展开 stdout ({{ result.stdout.length }} 字)
                    </template>
                  </el-button>
                </div>
                <pre v-if="expandedOutputs.has(outputKey(task.id, result.machine_id, 'stdout'))" class="result-output-expanded">{{ result.stdout }}</pre>
              </template>
              <template v-if="result.stderr">
                <div class="output-toggle output-toggle-stderr">
                  <el-button
                    type="danger"
                    size="small"
                    @click.stop="toggleOutput(task.id, result.machine_id, 'stderr')"
                  >
                    <template v-if="expandedOutputs.has(outputKey(task.id, result.machine_id, 'stderr'))">
                      收起 stderr
                    </template>
                    <template v-else>
                      展开 stderr ({{ result.stderr.length }} 字)
                    </template>
                  </el-button>
                </div>
                <pre v-if="expandedOutputs.has(outputKey(task.id, result.machine_id, 'stderr'))" class="result-output-expanded result-stderr">{{ result.stderr }}</pre>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.task-history {
  padding: 16px;
}

.stats-row {
  margin-bottom: 16px;
  color: #666;
  font-size: 14px;
}

.empty-tip {
  text-align: center;
  padding: 40px;
  color: #999;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}

.task-item.task-expanded {
  border-color: #1890ff;
}

.task-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.task-header:hover {
  background: #f5f5f5;
}

.task-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.task-name {
  font-weight: 600;
  color: #1a1a1a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
}

.task-type-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: #e6f7ff;
  color: #1890ff;
  border-radius: 4px;
  flex-shrink: 0;
}

.task-time {
  font-size: 13px;
  color: #1890ff;
  font-weight: 500;
  white-space: nowrap;
}

.task-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  flex-shrink: 0;
}

.stat-item .success {
  color: #52c41a;
}

.stat-item .failed {
  color: #ff4d4f;
}

.task-actions {
  margin-left: auto;
  flex-shrink: 0;
}

.task-detail {
  padding: 16px;
  background: #fafafa;
  border-top: 1px solid #e8e8e8;
}

.command-content {
  margin-bottom: 16px;
}

.detail-label {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
}

.command-code {
  padding: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item {
  padding: 12px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.result-success {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.result-failed {
  background: #fff2f0;
  border-color: #ffccc7;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.result-icon {
  font-size: 14px;
}

.result-success .result-icon {
  color: #52c41a;
}

.result-failed .result-icon {
  color: #ff4d4f;
}

.result-ip {
  font-weight: 500;
}

.result-device {
  color: #666;
}

.result-duration {
  color: #999;
  margin-left: auto;
}

.output-toggle {
  margin-top: 8px;
}

.output-toggle-stderr {
  margin-top: 4px;
}

.result-output-expanded {
  margin: 4px 0 0 0;
  padding: 8px;
  font-size: 12px;
  font-family: Consolas, Monaco, monospace;
  background: #f5f5f5;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-output-expanded.result-stderr {
  color: #ff4d4f;
}

/* 全局样式穿透：确保 el-button 在 scoped 下也能正常渲染 */
.result-item :deep(.el-button) {
  font-size: 12px;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
