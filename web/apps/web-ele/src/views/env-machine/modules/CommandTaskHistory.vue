<script lang="ts" setup>
import type { CommandTask } from '#/api/core/env-machine-config';
import { getCommandTaskListApi, deleteCommandTaskApi } from '#/api/core/env-machine-config';
import { ref, onMounted } from 'vue';
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

// 格式化时间
function formatTime(time?: string): string {
  if (!time) return '-';
  return new Date(time).toLocaleString('zh-CN');
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
async function loadTasks() {
  loading.value = true;
  try {
    const data = await getCommandTaskListApi({
      page: currentPage.value,
      page_size: pageSize.value,
    });
    taskList.value = data.items || [];
    total.value = data.total;
  } catch (error) {
    ElMessage.error('加载任务历史失败');
  } finally {
    loading.value = false;
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

// 翻页
function handlePageChange(page: number) {
  currentPage.value = page;
  loadTasks();
}

// 初始化
onMounted(() => {
  loadTasks();
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
            <span class="task-name">{{ task.template_name }}</span>
            <span class="task-type-badge">{{ task.template_type === 'command' ? '运行命令' : task.template_type === 'script' ? '脚本' : '配置' }}</span>
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
          <div class="task-time">
            {{ formatTime(task.sys_create_datetime) }}
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
              <div v-if="result.stdout" class="result-output">
                <div class="output-label">stdout:</div>
                <pre>{{ result.stdout }}</pre>
              </div>
              <div v-if="result.stderr" class="result-output result-stderr">
                <div class="output-label">stderr:</div>
                <pre>{{ result.stderr }}</pre>
              </div>
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
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-name {
  font-weight: 500;
  color: #333;
}

.task-type-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: #e6f7ff;
  color: #1890ff;
  border-radius: 4px;
}

.task-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.stat-item .success {
  color: #52c41a;
}

.stat-item .failed {
  color: #ff4d4f;
}

.task-time {
  font-size: 12px;
  color: #999;
}

.task-actions {
  margin-left: auto;
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

.result-output {
  margin-top: 8px;
}

.output-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.result-output pre {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  font-family: Consolas, Monaco, monospace;
  background: #f5f5f5;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-stderr pre {
  color: #ff4d4f;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
