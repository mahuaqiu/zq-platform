<script lang="ts" setup>
import type { AISessionDetail, AIMessage } from '#/api/core/ai-assistant';

import { onMounted, onUnmounted, ref, nextTick, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElMessage,
  ElMessageBox,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElEmpty,
} from 'element-plus';

import { marked } from 'marked';

import {
  getAISessionDetailApi,
  getAIGroupListApi,
  sendMessageInSessionApi,
  clearSessionContextApi,
  closeSessionApi,
  createNewSessionApi,
} from '#/api/core/ai-assistant';

defineOptions({ name: 'AISessionDetailPage' });

// 配置 marked 选项
marked.setOptions({
  breaks: true, // 支持 GitHub 风格的换行
  gfm: true, // 支持 GitHub Flavored Markdown
});

const route = useRoute();
const router = useRouter();

// 数据
const sessionDetail = ref<AISessionDetail | null>(null);
const loading = ref(false);
const sending = ref(false);
const inputMessage = ref('');
const messagesContainer = ref<HTMLElement | null>(null);

// 触发词提示相关
const showTriggerSuggestion = ref(false);
const triggerSuggestionList = ref<string[]>([]);
const triggerSuggestionPosition = ref({ top: 0, left: 0 });
const inputRef = ref<HTMLInputElement | null>(null);
let groupTriggerWords: string[] = []; // 所有群组的触发词

// 轮询相关
let pollTimer: ReturnType<typeof setInterval> | null = null;
let pollTimeout: ReturnType<typeof setTimeout> | null = null;
const POLL_INTERVAL = 3000; // 轮询间隔 3秒
const POLL_TIMEOUT = 180000; // 轮询超时 3分钟
let lastMessageCount = 0; // 上次消息数量

// 从路由获取会话ID
const sessionId = computed(() => route.params.id as string);

// 状态映射
const statusMap: Record<number, { label: string; type: 'success' | 'warning' | 'info' }> = {
  0: { label: '活跃', type: 'success' },
  1: { label: '已关闭', type: 'warning' },
  2: { label: '已清除', type: 'info' },
};

// 获取状态标签
function getStatusTag(status: number) {
  return statusMap[status] || { label: '未知', type: 'info' };
}

// 格式化时间
function formatTime(dateStr: string): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// 格式化日期时间
function formatDateTime(dateStr: string): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// 从 chat_id 提取创建时间（格式: group_id_YYYYMMDD_HHMMSS）
function getCreateTime(chatId: string): string {
  if (!chatId) return '';
  const parts = chatId.split('_');
  if (parts.length >= 3) {
    // 返回 YYYYMMDD_HHMMSS
    return parts.slice(-2).join('_');
  }
  return chatId;
}

// 获取发送者显示名称
function getSenderName(message: AIMessage): string {
  if (message.message_type === 1) {
    // AI 助手：使用 trigger_word（去掉 @ 符号）
    const triggerWord = sessionDetail.value?.trigger_word || '@Andy';
    return triggerWord.replace('@', '');
  }
  return message.sender_name || message.sender_id || '用户';
}

// 渲染 Markdown 内容（仅对 AI 消息）
function renderContent(message: AIMessage): string {
  if (message.message_type === 1) {
    // AI 消息：渲染 Markdown
    try {
      return marked.parse(message.content) as string;
    } catch {
      return message.content;
    }
  }
  // 用户消息：普通文本，转义 HTML
  return message.content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 加载会话详情
async function loadSessionDetail() {
  if (!sessionId.value) return;

  loading.value = true;
  try {
    const res = await getAISessionDetailApi(sessionId.value);
    sessionDetail.value = res;
    // 滚动到底部
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('加载会话详情失败:', error);
    ElMessage.error('加载会话详情失败');
  } finally {
    loading.value = false;
  }
}

// 加载所有群组的触发词（用于自动补全）
async function loadTriggerWords() {
  try {
    const res = await getAIGroupListApi({
      is_active: true,
      page: 1,
      page_size: 100,
    });
    // 提取所有触发词（去重）
    const words = new Set<string>();
    res.items?.forEach((group) => {
      if (group.trigger_word) {
        words.add(group.trigger_word);
      }
    });
    groupTriggerWords = Array.from(words);
  } catch (error) {
    console.error('加载触发词失败:', error);
  }
}

// 处理输入变化（检测 @ 符号）
function handleInputChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const value = input.value;
  const cursorPos = input.selectionStart || 0;

  // 检查光标前是否有 @ 符号
  const textBeforeCursor = value.substring(0, cursorPos);
  const atIndex = textBeforeCursor.lastIndexOf('@');

  if (atIndex !== -1) {
    // 检查 @ 后面的文本（是否是触发词的一部分）
    const textAfterAt = textBeforeCursor.substring(atIndex + 1);

    // 如果 @ 后面没有空格且光标就在 @ 后面或紧接着
    if (!textAfterAt.includes(' ') && cursorPos >= atIndex) {
      // 过滤匹配的触发词
      const matched = groupTriggerWords.filter((word) =>
        word.toLowerCase().startsWith(textAfterAt.toLowerCase()),
      );

      if (matched.length > 0) {
        triggerSuggestionList.value = matched;
        showTriggerSuggestion.value = true;

        // 计算下拉框位置
        updateSuggestionPosition(atIndex);
      } else if (textAfterAt === '') {
        // 刚输入 @，显示所有触发词
        triggerSuggestionList.value = groupTriggerWords;
        showTriggerSuggestion.value = true;
        updateSuggestionPosition(atIndex);
      } else {
        showTriggerSuggestion.value = false;
      }
    } else {
      showTriggerSuggestion.value = false;
    }
  } else {
    showTriggerSuggestion.value = false;
  }
}

// 更新提示框位置
function updateSuggestionPosition(atIndex: number) {
  if (!inputRef.value) return;

  // 简化处理：固定在输入框上方
  const inputRect = inputRef.value.getBoundingClientRect();
  triggerSuggestionPosition.value = {
    top: inputRect.top - 40,
    left: inputRect.left + atIndex * 8, // 大约每个字符 8px
  };
}

// 选择触发词
function selectTriggerWord(word: string) {
  if (!inputRef.value) return;

  const value = inputMessage.value;
  const cursorPos = inputRef.value.selectionStart || 0;
  const textBeforeCursor = value.substring(0, cursorPos);
  const atIndex = textBeforeCursor.lastIndexOf('@');

  if (atIndex !== -1) {
    // 替换 @ 及后面的部分为完整触发词
    const before = value.substring(0, atIndex);
    const after = value.substring(cursorPos);
    inputMessage.value = before + word + ' ' + after;

    // 移动光标到触发词后面
    nextTick(() => {
      const newPos = atIndex + word.length + 1;
      inputRef.value?.setSelectionRange(newPos, newPos);
      inputRef.value?.focus();
    });
  }

  showTriggerSuggestion.value = false;
}

// 关闭提示框
function closeSuggestion() {
  showTriggerSuggestion.value = false;
}

// 滚动到底部
function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

// 开始轮询检查 AI 回复
function startPolling() {
  if (pollTimer) return; // 已在轮询中

  lastMessageCount = sessionDetail.value?.messages?.length || 0;

  // 设置超时，3分钟后停止轮询
  pollTimeout = setTimeout(() => {
    stopPolling();
    ElMessage.info('等待 AI 回复超时，请稍后刷新查看');
  }, POLL_TIMEOUT);

  // 开始轮询
  pollTimer = setInterval(async () => {
    try {
      const res = await getAISessionDetailApi(sessionId.value);
      const newCount = res?.messages?.length || 0;

      // 检查是否有新消息
      if (newCount > lastMessageCount) {
        sessionDetail.value = res;
        lastMessageCount = newCount;
        await nextTick();
        scrollToBottom();

        // 检查是否有 AI 回复（最后一条消息是 AI）
        const lastMsg = res?.messages?.[newCount - 1];
        if (lastMsg && lastMsg.message_type === 1) {
          stopPolling();
        }
      }
    } catch (error) {
      console.error('轮询失败:', error);
    }
  }, POLL_INTERVAL);
}

// 停止轮询
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (pollTimeout) {
    clearTimeout(pollTimeout);
    pollTimeout = null;
  }
}

// 发送消息
async function handleSend() {
  if (!inputMessage.value.trim()) {
    ElMessage.warning('请输入消息内容');
    return;
  }

  if (!sessionId.value) return;

  sending.value = true;
  try {
    await sendMessageInSessionApi(sessionId.value, inputMessage.value.trim());
    inputMessage.value = '';
    // 刷新会话详情
    await loadSessionDetail();
    // 开始轮询等待 AI 回复
    startPolling();
  } catch (error) {
    console.error('发送消息失败:', error);
    ElMessage.error('发送消息失败');
  } finally {
    sending.value = false;
  }
}

// 清除上下文
async function handleClearContext() {
  try {
    await ElMessageBox.confirm(
      '确定要清除当前会话的上下文吗？这将重置会话状态。',
      '确认清除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    if (!sessionId.value) return;

    await clearSessionContextApi(sessionId.value);
    ElMessage.success('上下文已清除');
    await loadSessionDetail();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清除上下文失败:', error);
      ElMessage.error('清除上下文失败');
    }
  }
}

// 关闭会话
async function handleCloseSession() {
  try {
    await ElMessageBox.confirm(
      '确定要关闭当前会话吗？关闭后将无法继续发送消息。',
      '确认关闭',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    if (!sessionId.value) return;

    await closeSessionApi(sessionId.value);
    ElMessage.success('会话已关闭');
    await loadSessionDetail();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('关闭会话失败:', error);
      ElMessage.error('关闭会话失败');
    }
  }
}

// 创建新会话
async function handleCreateNewSession() {
  try {
    await ElMessageBox.confirm(
      '确定要为此群组创建新会话吗？',
      '创建新会话',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      }
    );

    if (!sessionId.value) return;

    const res = await createNewSessionApi(sessionId.value);
    ElMessage.success('新会话已创建');
    // 跳转到新会话
    if (res && res.id) {
      router.replace(`/ai-assistant/session/${res.id}`);
    } else {
      // 返回列表页
      router.push('/ai-assistant/session');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('创建新会话失败:', error);
      ElMessage.error('创建新会话失败');
    }
  }
}

// 返回列表
function goBack() {
  router.push('/ai-assistant/session');
}

// 处理下拉菜单命令
function handleCommand(command: string) {
  switch (command) {
    case 'clear':
      handleClearContext();
      break;
    case 'close':
      handleCloseSession();
      break;
    case 'new':
      handleCreateNewSession();
      break;
  }
}

// 初始加载
onMounted(() => {
  loadSessionDetail();
  loadTriggerWords(); // 加载触发词列表
});

// 离开页面时停止轮询
onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <Page auto-content-height>
    <div class="chat-container">
      <!-- 聊天头部 -->
      <div class="chat-header">
        <div class="header-left" @click="goBack">
          <span class="back-icon">‹</span>
          <span class="back-text">返回</span>
        </div>
        <div class="header-center">
          <div class="group-name">{{ sessionDetail?.group_name || sessionDetail?.session?.group_id || '会话' }}</div>
        </div>
        <div class="header-right">
          <ElDropdown trigger="click" @command="handleCommand">
            <span class="menu-icon">⋮</span>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem command="clear">清除上下文</ElDropdownItem>
                <ElDropdownItem command="close">关闭会话</ElDropdownItem>
                <ElDropdownItem command="new">创建新会话</ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </div>
      </div>

      <!-- 会话信息栏 -->
      <div class="session-info" v-if="sessionDetail?.session">
        <div class="info-item">
          <span class="info-label">消息数:</span>
          <span class="info-value">{{ sessionDetail.session.message_count }} / 50</span>
        </div>
        <div class="info-divider">|</div>
        <div class="info-item">
          <span class="info-label">状态:</span>
          <span
            class="info-value status-tag"
            :class="`status-${sessionDetail.session.status}`"
          >
            {{ getStatusTag(sessionDetail.session.status).label }}
          </span>
        </div>
        <div class="info-divider">|</div>
        <div class="info-item">
          <span class="info-label">开始时间:</span>
          <span class="info-value">{{ formatDateTime(sessionDetail.session.start_time) }}</span>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="messages-container" ref="messagesContainer" v-loading="loading">
        <template v-if="sessionDetail?.messages && sessionDetail.messages.length > 0">
          <div
            v-for="message in sessionDetail.messages"
            :key="message.id"
            class="message-item"
            :class="message.message_type === 0 ? 'user-message' : 'ai-message'"
          >
            <!-- AI消息 - 左侧 -->
            <template v-if="message.message_type === 1">
              <div class="avatar ai-avatar">{{ getSenderName(message).charAt(0).toUpperCase() }}</div>
              <div class="message-content">
                <div class="sender-name">{{ getSenderName(message) }}</div>
                <div class="bubble ai-bubble">
                  <div class="bubble-content markdown-body" v-html="renderContent(message)"></div>
                  <div class="bubble-time">{{ formatTime(message.send_time) }}</div>
                </div>
              </div>
            </template>

            <!-- 用户消息 - 右侧 -->
            <template v-else>
              <div class="message-content">
                <div class="sender-name">{{ getSenderName(message) }}</div>
                <div class="bubble user-bubble">
                  <div class="bubble-content" v-html="renderContent(message)"></div>
                  <div class="bubble-time">{{ formatTime(message.send_time) }}</div>
                </div>
              </div>
              <div class="avatar user-avatar">{{ (message.sender_name || message.sender_id || 'U').charAt(0).toUpperCase() }}</div>
            </template>
          </div>
        </template>

        <template v-else-if="!loading">
          <ElEmpty description="暂无消息记录" />
        </template>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <!-- 触发词提示下拉框 -->
        <div
          v-if="showTriggerSuggestion && triggerSuggestionList.length > 0"
          class="trigger-suggestion"
          :style="{ top: triggerSuggestionPosition.top + 'px', left: triggerSuggestionPosition.left + 'px' }"
        >
          <div
            v-for="word in triggerSuggestionList"
            :key="word"
            class="suggestion-item"
            @click="selectTriggerWord(word)"
          >
            {{ word }}
          </div>
        </div>

        <input
          ref="inputRef"
          v-model="inputMessage"
          type="text"
          class="message-input"
          placeholder="输入 @ 可选择触发词"
          :disabled="sessionDetail?.session?.status !== 0 || sending"
          @input="handleInputChange"
          @keyup.enter="handleSend"
          @blur="closeSuggestion"
        />
        <button
          class="send-button"
          :disabled="!inputMessage.trim() || sessionDetail?.session?.status !== 0 || sending"
          @click="handleSend"
        >
          发送
        </button>
      </div>
    </div>
  </Page>
</template>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ededed;
}

/* 头部区域 */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #ededed;
  border-bottom: 1px solid #d9d9d9;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.back-icon {
  font-size: 24px;
  font-weight: 300;
  color: #333;
}

.back-text {
  font-size: 14px;
  color: #333;
}

.header-center {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.group-name {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.chat-id {
  font-size: 12px;
  color: #999;
}

.header-right {
  width: 32px;
  display: flex;
  justify-content: flex-end;
}

.menu-icon {
  font-size: 20px;
  font-weight: bold;
  color: #333;
  cursor: pointer;
  padding: 4px 8px;
}

/* 会话信息栏 */
.session-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f5f5f5;
  border-bottom: 1px solid #e8e8e8;
  font-size: 12px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.info-label {
  color: #999;
}

.info-value {
  color: #333;
}

.info-divider {
  color: #ddd;
}

.status-tag {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.status-0 {
  background: #e6f7e6;
  color: #52c41a;
}

.status-1 {
  background: #fff7e6;
  color: #fa8c16;
}

.status-2 {
  background: #f0f0f0;
  color: #999;
}

/* 消息列表区域 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #ededed;
}

/* 消息项 */
.message-item {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

/* AI消息 - 左对齐 */
.ai-message {
  justify-content: flex-start;
}

/* 用户消息 - 右对齐 */
.user-message {
  justify-content: flex-end;
}

/* 头像 */
.avatar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  border-radius: 4px;
}

.ai-avatar {
  background: #1890ff;
}

.user-avatar {
  background: #07c160;
}

/* 消息内容区 */
.message-content {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}

.sender-name {
  margin-bottom: 4px;
  font-size: 12px;
  color: #999;
}

.user-message .sender-name {
  text-align: right;
}

/* 气泡 */
.bubble {
  padding: 10px 14px;
  border-radius: 8px;
  position: relative;
}

/* AI气泡 - 白色 */
.ai-bubble {
  background: #fff;
  color: #333;
}

/* 用户气泡 - 绿色 */
.user-bubble {
  background: #95ec69;
  color: #333;
}

.bubble-content {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

/* Markdown 样式 */
.markdown-body {
  white-space: normal;
}

.markdown-body p {
  margin: 0 0 8px 0;
}

.markdown-body p:last-child {
  margin-bottom: 0;
}

.markdown-body code {
  padding: 2px 6px;
  background: #f5f5f5;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.markdown-body pre {
  margin: 8px 0;
  padding: 12px;
  background: #282c34;
  border-radius: 6px;
  overflow-x: auto;
}

.markdown-body pre code {
  padding: 0;
  background: transparent;
  color: #abb2bf;
  font-size: 13px;
  line-height: 1.6;
}

.markdown-body ul,
.markdown-body ol {
  margin: 8px 0;
  padding-left: 20px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body blockquote {
  margin: 8px 0;
  padding: 8px 12px;
  background: #f9f9f9;
  border-left: 4px solid #ddd;
  color: #666;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin: 12px 0 8px 0;
  font-weight: 600;
}

.markdown-body h1 { font-size: 18px; }
.markdown-body h2 { font-size: 16px; }
.markdown-body h3 { font-size: 15px; }
.markdown-body h4 { font-size: 14px; }

.markdown-body a {
  color: #1890ff;
  text-decoration: none;
}

.markdown-body a:hover {
  text-decoration: underline;
}

.markdown-body table {
  margin: 8px 0;
  border-collapse: collapse;
}

.markdown-body th,
.markdown-body td {
  padding: 6px 12px;
  border: 1px solid #e8e8e8;
}

.markdown-body th {
  background: #f5f5f5;
  font-weight: 600;
}

.bubble-time {
  margin-top: 4px;
  font-size: 11px;
  color: #999;
  text-align: right;
}

/* 输入区域 */
.input-area {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
  background: #f5f5f5;
  border-top: 1px solid #d9d9d9;
}

.message-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  font-size: 14px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  outline: none;
}

.message-input:focus {
  border-color: #07c160;
}

.message-input:disabled {
  background: #f5f5f5;
  color: #999;
}

.send-button {
  flex-shrink: 0;
  height: 36px;
  padding: 0 20px;
  font-size: 14px;
  color: #fff;
  cursor: pointer;
  background: #07c160;
  border: none;
  border-radius: 4px;
  transition: background 0.2s;
}

.send-button:hover:not(:disabled) {
  background: #06ae56;
}

.send-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* 空状态 */
:deep(.el-empty) {
  padding: 100px 0;
}

/* 触发词提示框 */
.trigger-suggestion {
  position: fixed;
  z-index: 1000;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  max-height: 200px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 8px 12px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  transition: background 0.2s;
}

.suggestion-item:hover {
  background: #f5f5f5;
  color: #07c160;
}

.suggestion-item:first-child {
  border-radius: 6px 6px 0 0;
}

.suggestion-item:last-child {
  border-radius: 0 0 6px 6px;
}

/* 下拉菜单样式 */
:deep(.el-dropdown-menu__item) {
  padding: 8px 20px;
  font-size: 14px;
}
</style>