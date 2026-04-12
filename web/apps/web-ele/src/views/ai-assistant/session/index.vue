<script lang="ts" setup>
import type { AISession, AIGroup } from '#/api/core/ai-assistant';

import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElSelect,
  ElOption,
  ElEmpty,
  ElTag,
} from 'element-plus';

import {
  getAISessionListApi,
  getAIGroupListApi,
  deleteSessionApi,
  createSessionApi,
} from '#/api/core/ai-assistant';

defineOptions({ name: 'AISessionPage' });

const router = useRouter();

// 数据
const sessionList = ref<AISession[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 筛选条件
const searchForm = ref({
  group_id: '',
  status: undefined as number | undefined,
});

// 新建会话弹窗
const dialogVisible = ref(false);
const dialogLoading = ref(false);
const groupList = ref<AIGroup[]>([]);
const groupLoading = ref(false);
const newSessionForm = ref({
  group_id: '',
});

// 状态映射
const statusMap: Record<number, { label: string; type: 'success' | 'warning' | 'info' }> = {
  0: { label: '活跃', type: 'success' },
  1: { label: '已关闭', type: 'warning' },
  2: { label: '已清除', type: 'info' },
};

// 格式化相对时间
function formatTimeAgo(dateStr: string): string {
  if (!dateStr) return '-';

  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) {
    return '刚刚';
  } else if (minutes < 60) {
    return `${minutes}分钟前`;
  } else if (hours < 24) {
    return `${hours}小时前`;
  } else if (days < 7) {
    return `${days}天前`;
  } else {
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
    });
  }
}

// 获取群组首字母
function getGroupInitial(groupId: string): string {
  if (!groupId) return '?';
  return groupId.charAt(0).toUpperCase();
}

// 获取状态标签
function getStatusTag(status: number) {
  return statusMap[status] || { label: '未知', type: 'info' };
}

// 计算预览文本
function getPreviewText(session: AISession): string {
  const status = getStatusTag(session.status);
  return `${session.message_count}条消息 · ${status.label}`;
}

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getAISessionListApi({
      group_id: searchForm.value.group_id || undefined,
      status: searchForm.value.status,
      page: currentPage.value,
      page_size: pageSize.value,
    });
    sessionList.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error('加载数据失败:', error);
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
}

// 重置
function handleReset() {
  searchForm.value = {
    group_id: '',
    status: undefined,
  };
  currentPage.value = 1;
  loadData();
}

// 进入详情页
function goToDetail(session: AISession) {
  router.push(`/ai-assistant/session/${session.id}`);
}

// 加载群组列表
async function loadGroupList() {
  groupLoading.value = true;
  try {
    const res = await getAIGroupListApi({
      is_active: true,
      page: 1,
      page_size: 100,
    });
    groupList.value = res.items || [];
  } catch (error) {
    console.error('加载群组列表失败:', error);
  } finally {
    groupLoading.value = false;
  }
}

// 打开新建会话弹窗
function handleCreateSession() {
  newSessionForm.value = {
    group_id: '',
  };
  dialogVisible.value = true;
  loadGroupList();
}

// 获取群组显示名称
function getGroupDisplayName(group: AIGroup): string {
  return group.group_name || group.group_id;
}

// 提交新建会话
async function handleCreateSubmit() {
  if (!newSessionForm.value.group_id) {
    ElMessage.warning('请选择群组');
    return;
  }

  dialogLoading.value = true;
  try {
    await createSessionApi({
      group_id: newSessionForm.value.group_id,
    });
    ElMessage.success('会话创建成功');
    dialogVisible.value = false;
    loadData();
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '创建失败';
    ElMessage.error(msg);
  } finally {
    dialogLoading.value = false;
  }
}

// 删除会话
function handleDelete(session: AISession, event: MouseEvent) {
  event.stopPropagation(); // 阻止触发点击进入详情

  ElMessageBox.confirm(
    `确定要删除会话 "${session.chat_id}" 吗？删除后该会话的所有消息记录将一并删除。`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await deleteSessionApi(session.id);
      ElMessage.success('删除成功');
      loadData();
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '删除失败';
      ElMessage.error(msg);
    }
  });
}

// 初始加载
onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="session-container">
      <!-- 头部区域 -->
      <div class="session-header">
        <div class="header-row">
          <h2 class="session-title">会话管理</h2>
          <ElButton type="primary" @click="handleCreateSession">
            + 新建会话
          </ElButton>
        </div>

        <!-- 搜索框 -->
        <div class="session-search">
          <ElInput
            v-model="searchForm.group_id"
            placeholder="搜索群组ID..."
            clearable
            class="search-input"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <span class="search-icon">🔍</span>
            </template>
          </ElInput>
          <ElSelect
            v-model="searchForm.status"
            placeholder="状态筛选"
            clearable
            class="status-select"
            @change="handleSearch"
          >
            <ElOption label="活跃" :value="0" />
            <ElOption label="已关闭" :value="1" />
            <ElOption label="已清除" :value="2" />
          </ElSelect>
          <ElButton @click="handleReset">重置</ElButton>
        </div>
      </div>

      <!-- 会话列表 -->
      <div class="session-list" v-loading="loading">
        <template v-if="sessionList.length > 0">
          <div
            v-for="session in sessionList"
            :key="session.id"
            class="session-card"
          >
            <!-- 左侧头像 -->
            <div class="session-avatar" @click="goToDetail(session)">
              {{ getGroupInitial(session.group_id) }}
            </div>

            <!-- 右侧内容 -->
            <div class="session-content" @click="goToDetail(session)">
              <!-- 上：群组ID + 时间 -->
              <div class="session-top">
                <span class="session-name">{{ session.group_name || session.group_id }}</span>
                <span class="session-time">{{ formatTimeAgo(session.last_message_time) }}</span>
              </div>

              <!-- 下：预览信息 -->
              <div class="session-bottom">
                <span class="session-preview">{{ getPreviewText(session) }}</span>
                <ElTag
                  :type="getStatusTag(session.status).type"
                  size="small"
                  effect="plain"
                >
                  {{ getStatusTag(session.status).label }}
                </ElTag>
              </div>
            </div>

            <!-- 删除按钮 -->
            <div class="session-actions">
              <ElButton
                type="danger"
                size="small"
                text
                @click="(e: MouseEvent) => handleDelete(session, e)"
              >
                删除
              </ElButton>
            </div>
          </div>
        </template>

        <template v-else>
          <ElEmpty description="暂无会话数据" />
        </template>
      </div>

      <!-- 加载更多 -->
      <div v-if="sessionList.length > 0 && sessionList.length < total" class="load-more">
        <span @click="() => { currentPage++; loadData(); }">加载更多</span>
      </div>
    </div>

    <!-- 新建会话弹窗 -->
    <ElDialog v-model="dialogVisible" title="新建会话" width="400px">
      <ElForm label-width="80px">
        <ElFormItem label="选择群组" required>
          <ElSelect
            v-model="newSessionForm.group_id"
            placeholder="请选择群组"
            filterable
            :loading="groupLoading"
            style="width: 100%"
          >
            <ElOption
              v-for="group in groupList"
              :key="group.id"
              :label="getGroupDisplayName(group)"
              :value="group.group_id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="handleCreateSubmit">
          确定
        </ElButton>
      </template>
    </ElDialog>
  </Page>
</template>

<style scoped>
.session-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f5f5;
}

/* 头部区域 */
.session-header {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.session-search {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  flex: 1;
  max-width: 300px;
}

.search-icon {
  font-size: 14px;
}

.status-select {
  width: 120px;
}

/* 会话列表 */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

/* 会话卡片 - 微信风格 */
.session-card {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 14px 20px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}

.session-card:hover {
  background: #f5f5f5;
}

/* 头像 - 微信绿色渐变 */
.session-avatar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #07c160 0%, #06ae56 100%);
  border-radius: 8px;
  cursor: pointer;
}

/* 右侧内容 */
.session-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  cursor: pointer;
}

/* 上：群组名称 + 时间 */
.session-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-name {
  overflow: hidden;
  font-size: 15px;
  font-weight: 500;
  color: #333;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  flex-shrink: 0;
  margin-left: 12px;
  font-size: 12px;
  color: #999;
}

/* 下：预览信息 */
.session-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.session-preview {
  overflow: hidden;
  font-size: 13px;
  color: #999;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 操作按钮 */
.session-actions {
  flex-shrink: 0;
}

/* 加载更多 */
.load-more {
  padding: 16px;
  text-align: center;

  span {
    color: #07c160;
    cursor: pointer;
  }

  span:hover {
    text-decoration: underline;
  }
}

/* Element Plus 样式覆盖 */
:deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px #e8e8e8 inset;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #07c160 inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #07c160 inset;
}

:deep(.el-select .el-input__wrapper) {
  border-radius: 8px;
}

:deep(.el-empty) {
  padding: 60px 0;
}
</style>