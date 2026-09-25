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
        <button class="quick-btn" @click="handleQuickPress('HOME')">
          HOME
        </button>
        <button class="quick-btn" @click="handleQuickPress('BACK')">
          BACK
        </button>
        <button class="quick-btn" @click="handleQuickPress('POWER')">
          电源
        </button>
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
        <button
          class="send-btn"
          :disabled="!textInputValue.trim()"
          @click="handleTextInput"
        >
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
          <span v-if="record.error" class="history-error-inline">{{
            record.error
          }}</span>
        </div>
        <div v-if="operationHistory.length === 0" class="history-empty">
          暂无操作记录
        </div>
      </div>
    </div>

    <!-- 功能按钮 -->
    <div class="panel-section bottom-section">
      <button class="func-btn light" @click="handleUnlock">🔒 解锁屏幕</button>
      <button class="func-btn light" @click="handleScreenshot">
        📷 截图保存
      </button>
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
          <button
            class="dialog-btn cancel"
            @click="unlockDialogVisible = false"
          >
            取消
          </button>
          <button class="dialog-btn confirm" @click="handleUnlockConfirm">
            确认解锁
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mobile-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(0 0 0 / 8%);
}

.device-info-row {
  font-size: 13px;
  color: #666;
}

.info-label {
  font-weight: 500;
  color: #111;
}

.panel-section {
  padding-top: 16px;
  border-top: 1px solid #e8e8e8;
}

.section-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #111;
}

.quick-buttons {
  display: flex;
  gap: 12px;
}

.quick-btn {
  flex: 1;
  padding: 12px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
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
  padding: 10px 12px;
  font-size: 14px;
  color: #333;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}

.text-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.send-btn {
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  background: #3b82f6;
  border: none;
  border-radius: 6px;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.history-section {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-top: 1px solid #e8e8e8;
}

.history-list {
  height: 100%;
  padding: 12px;
  overflow: auto;
  font-size: 12px;
  color: #666;
  background: #f5f5f5;
  border-radius: 8px;
}

.history-item {
  display: flex;
  gap: 8px;
  align-items: center;
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
  flex-shrink: 0;
  color: #999;
}

.history-params {
  color: #666;
}

.history-error-inline {
  flex: 1;
  font-size: 11px;
  color: #ef4444;
}

.history-failed {
  background: #fef2f2;
}

.history-empty {
  padding: 20px;
  color: #999;
  text-align: center;
}

.bottom-section {
  display: flex;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #e8e8e8;
}

.func-btn {
  flex: 1;
  padding: 12px;
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.func-btn.light {
  color: #333;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
}

.func-btn.light:hover {
  background: #e8e8e8;
}

.unlock-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  background: rgb(0 0 0 / 30%);
}

.unlock-dialog {
  width: 360px;
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgb(0 0 0 / 15%);
}

.dialog-title {
  margin-bottom: 20px;
  font-size: 16px;
  font-weight: 600;
  color: #111;
}

.dialog-tip {
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.dialog-input {
  box-sizing: border-box;
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  color: #333;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}

.dialog-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.dialog-note {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.dialog-btn {
  flex: 1;
  padding: 10px;
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.dialog-btn.cancel {
  color: #333;
  background: #f5f5f5;
  border: 1px solid #d9d9d9;
}

.dialog-btn.cancel:hover {
  background: #e8e8e8;
}

.dialog-btn.confirm {
  font-weight: 500;
  color: #fff;
  background: #22c55e;
  border: none;
}

.dialog-btn.confirm:hover {
  background: #16a34a;
}
</style>
