<script lang="ts" setup>
import type { OperationRecord } from '../types';

import { ref } from 'vue';

import { ElMessage } from 'element-plus';

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
    <div class="device-info-row">
      <span v-if="udid"><span class="info-label">UDID:</span> {{ udid }}</span>
    </div>

    <!-- 快捷按键 -->
    <div class="panel-section">
      <div class="section-title">快捷按键</div>
      <div class="quick-buttons">
        <button class="quick-btn" @click="handleQuickPress('HOME')">HOME</button>
        <button class="quick-btn" @click="handleQuickPress('BACK')">BACK</button>
        <button class="quick-btn" @click="handleQuickPress('POWER')">电源</button>
      </div>
    </div>

    <!-- 文本输入 -->
    <div class="panel-section">
      <div class="section-title">文本输入</div>
      <div class="text-input-row">
        <input
          v-model="textInputValue"
          type="text"
          class="text-input"
          placeholder="输入文本..."
        />
        <button class="send-btn" :disabled="!textInputValue.trim()" @click="handleTextInput">
          发送
        </button>
      </div>
    </div>

    <!-- 操作历史 -->
    <div class="panel-section history-section">
      <div class="section-title">操作历史</div>
      <div class="history-list">
        <div
          v-for="(record, index) in operationHistory"
          :key="index"
          class="history-item"
          :class="{ 'history-failed': record.status === 'failed' }"
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
          <span class="history-time">{{ record.time }}</span>
          <span class="history-params">{{ record.params }}</span>
          <span v-if="record.error" class="history-error-inline">{{ record.error }}</span>
        </div>
        <div v-if="operationHistory.length === 0" class="history-empty">
          暂无操作记录
        </div>
      </div>
    </div>

    <!-- 功能按钮 -->
    <div class="panel-section bottom-section">
      <button class="func-btn light" @click="handleScreenshot">📷 截图保存</button>
      <button class="func-btn light" @click="handleUnlock">🔒 解锁屏幕</button>
      <button class="func-btn light" @click="handleInstall">📦 安装 APP</button>
    </div>

    <!-- 解锁弹窗 -->
    <div v-if="unlockDialogVisible" class="unlock-dialog-overlay">
      <div class="unlock-dialog">
        <div class="dialog-title">🔒 解锁屏幕</div>
        <div class="dialog-tip">输入解锁密码（可选）</div>
        <input
          v-model="unlockPassword"
          type="password"
          class="dialog-input"
          placeholder="密码（非必填）"
        />
        <div class="dialog-note">如果设备无密码锁，可直接解锁</div>
        <div class="dialog-actions">
          <button class="dialog-btn cancel" @click="unlockDialogVisible = false">取消</button>
          <button class="dialog-btn confirm" @click="handleUnlockConfirm">确认解锁</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mobile-panel {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-info-row {
  font-size: 13px;
  color: #666;
}

.info-label {
  color: #111;
  font-weight: 500;
}

.panel-section {
  border-top: 1px solid #e8e8e8;
  padding-top: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #111;
  margin-bottom: 12px;
}

.quick-buttons {
  display: flex;
  gap: 12px;
}

.quick-btn {
  flex: 1;
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  color: #333;
  padding: 12px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  background: #e8e8e8;
}

.text-input-row {
  display: flex;
  gap: 8px;
}

.text-input {
  flex: 1;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 14px;
}

.text-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.send-btn {
  background: #3b82f6;
  color: #fff;
  padding: 10px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.history-section {
  flex: 1;
  overflow: hidden;
  border-top: 1px solid #e8e8e8;
  min-height: 0;
}

.history-list {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  color: #666;
  overflow: auto;
  height: 100%;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
}

.history-item:not(.history-failed) {
  background: transparent;
}

.history-status {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}

.status-success {
  color: #22c55e;
}

.status-failed {
  color: #ef4444;
}

.history-time {
  color: #999;
  flex-shrink: 0;
}

.history-params {
  color: #666;
}

.history-error-inline {
  color: #ef4444;
  font-size: 11px;
  flex: 1;
}

.history-failed {
  background: #fef2f2;
}

.history-empty {
  text-align: center;
  color: #999;
  padding: 20px;
}

.bottom-section {
  display: flex;
  gap: 8px;
  border-top: 1px solid #e8e8e8;
  padding-top: 16px;
}

.func-btn {
  flex: 1;
  padding: 12px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.func-btn.light {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
}

.func-btn.light:hover {
  background: #e8e8e8;
}

.unlock-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.unlock-dialog {
  width: 360px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 24px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: #111;
  margin-bottom: 20px;
}

.dialog-tip {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.dialog-input {
  width: 100%;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.dialog-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.dialog-note {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.dialog-btn {
  flex: 1;
  padding: 10px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.dialog-btn.cancel {
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
}

.dialog-btn.cancel:hover {
  background: #e8e8e8;
}

.dialog-btn.confirm {
  background: #22c55e;
  color: #fff;
  border: none;
  font-weight: 500;
}

.dialog-btn.confirm:hover {
  background: #16a34a;
}
</style>