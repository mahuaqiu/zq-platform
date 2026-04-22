<script lang="ts" setup>
import type { OperationRecord } from '../types';

import { ref } from 'vue';

import { ElButton, ElInput, ElMessage } from 'element-plus';

interface Props {
  operationHistory: OperationRecord[];
  udid?: string;
}

interface Emits {
  (e: 'keypress', key: string): void;
  (e: 'input', text: string): void;
  (e: 'unlock', password?: string): void;
  (e: 'install'): void;
  (e: 'screenshot'): void;
}

defineProps<Props>();
const emit = defineEmits<Emits>();

const textInputValue = ref('');
const unlockDialogVisible = ref(false);
const unlockPassword = ref('');

function handleQuickPress(key: string) {
  emit('keypress', key);
}

function handleTextInput() {
  if (!textInputValue.value.trim()) {
    ElMessage.warning('请输入文本内容');
    return;
  }
  emit('input', textInputValue.value);
  textInputValue.value = '';
}

function handleUnlock() {
  unlockDialogVisible.value = true;
}

function handleUnlockConfirm() {
  emit('unlock', unlockPassword.value);
  unlockPassword.value = '';
  unlockDialogVisible.value = false;
}

function handleInstall() {
  emit('install');
}

function handleScreenshot() {
  emit('screenshot');
}
</script>

<template>
  <div class="mobile-panel">
    <!-- 设备信息 -->
    <div class="panel-section">
      <div class="section-title">设备信息</div>
      <div class="device-info">
        <span v-if="udid">UDID: {{ udid }}</span>
      </div>
    </div>

    <!-- 快捷按键 -->
    <div class="panel-section">
      <div class="section-title">快捷按键</div>
      <div class="quick-buttons">
        <ElButton size="small" @click="handleQuickPress('HOME')">HOME</ElButton>
        <ElButton size="small" @click="handleQuickPress('BACK')">BACK</ElButton>
        <ElButton size="small" @click="handleQuickPress('POWER')">电源</ElButton>
      </div>
    </div>

    <!-- 文本输入 -->
    <div class="panel-section">
      <div class="section-title">文本输入</div>
      <ElInput
        v-model="textInputValue"
        placeholder="输入文本内容..."
        size="small"
      />
      <ElButton
        type="primary"
        size="small"
        class="send-btn"
        :disabled="!textInputValue.trim()"
        @click="handleTextInput"
      >
        发送
      </ElButton>
    </div>

    <!-- 操作历史 -->
    <div class="panel-section history-section">
      <div class="section-title">操作历史</div>
      <div class="history-list">
        <div
          v-for="(record, index) in operationHistory"
          :key="index"
          class="history-item"
        >
          <span class="history-status">
            <template v-if="record.status === 'pending'">⏳</template>
            <template v-else-if="record.status === 'success'">
              <span class="status-success">✓</span>
            </template>
            <template v-else>
              <span class="status-failed">✗</span>
            </template>
          </span>
          <span class="history-params">{{ record.params }}</span>
          <span class="history-time">{{ record.time }}</span>
        </div>
        <div v-if="operationHistory.length === 0" class="history-empty">
          暂无操作记录
        </div>
      </div>
    </div>

    <!-- 功能按钮 -->
    <div class="panel-section">
      <ElButton size="small" @click="handleScreenshot">截图保存</ElButton>
      <ElButton size="small" @click="handleUnlock">解锁屏幕</ElButton>
      <ElButton size="small" @click="handleInstall">安装 APP</ElButton>
    </div>

    <!-- 解锁弹窗 -->
    <div v-if="unlockDialogVisible" class="unlock-dialog">
      <div class="dialog-title">解锁屏幕</div>
      <div class="dialog-tip">如果设备无密码锁，可直接解锁</div>
      <ElInput
        v-model="unlockPassword"
        placeholder="输入解锁密码（可选）"
        size="small"
      />
      <div class="dialog-actions">
        <ElButton size="small" @click="unlockDialogVisible = false">取消</ElButton>
        <ElButton size="small" type="primary" @click="handleUnlockConfirm">
          确认解锁
        </ElButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mobile-panel {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-section {
  border-bottom: 1px solid #e8e8e8;
  padding-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #111;
  margin-bottom: 8px;
}

.device-info {
  font-size: 12px;
  color: #666;
}

.quick-buttons {
  display: flex;
  gap: 8px;
}

.send-btn {
  width: 100%;
  margin-top: 8px;
}

.history-section {
  flex: 1;
  overflow: hidden;
  border-bottom: none;
}

.history-list {
  height: 120px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 12px;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 4px;
}

.status-success {
  color: #22c55e;
}

.status-failed {
  color: #ef4444;
}

.history-params {
  flex: 1;
  color: #666;
}

.history-time {
  color: #999;
}

.history-empty {
  text-align: center;
  color: #999;
  padding: 20px;
}

.unlock-dialog {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  width: 300px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: #111;
  margin-bottom: 12px;
}

.dialog-tip {
  font-size: 12px;
  color: #666;
  margin-bottom: 12px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>