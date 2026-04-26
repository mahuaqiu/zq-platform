<script lang="ts" setup>
import { computed, ref } from 'vue';

import { ElButton, ElDialog } from 'element-plus';

import type { DeviceType } from '../types';
import {
  ARROW_KEYS,
  CAPS_ROW,
  combineKeys,
  EDIT_KEYS,
  FUNCTION_KEYS_ROW,
  MAC_BOTTOM_ROW,
  MAC_SHORTCUTS,
  NUMPAD_KEYS,
  NUMBER_ROW,
  SHIFT_ROW,
  TAB_ROW,
  WINDOWS_BOTTOM_ROW,
  WINDOWS_SHORTCUTS,
  type KeyDefinition,
} from '../keyboard-data';

interface Props {
  visible: boolean;
  disabled?: boolean;
  deviceType?: DeviceType;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'press', key: string): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 修饰键累加状态
const activeModifiers = ref<string[]>([]);

// 判断是否为桌面端设备
const isDesktop = computed(() =>
  props.deviceType === 'windows' || props.deviceType === 'mac'
);

// 判断是否为 Mac 设备
const isMac = computed(() => props.deviceType === 'mac');

// 根据平台选择快捷键列表
const shortcuts = computed(() =>
  isMac.value ? MAC_SHORTCUTS : WINDOWS_SHORTCUTS
);

// 根据平台选择底行修饰键
const bottomRow = computed(() =>
  isMac.value ? MAC_BOTTOM_ROW : WINDOWS_BOTTOM_ROW
);

// 按键是否激活（用于修饰键高亮显示）
function isKeyActive(key: string): boolean {
  return activeModifiers.value.includes(key);
}

// 点击修饰键
function handleModifierClick(key: string) {
  const index = activeModifiers.value.indexOf(key);
  if (index >= 0) {
    activeModifiers.value.splice(index, 1); // 取消激活
  } else {
    activeModifiers.value.push(key); // 添加激活
  }
}

// 点击普通按键
function handleKeyClick(key: string, keyType: string) {
  if (keyType === 'modifier') {
    handleModifierClick(key);
    return;
  }
  if (activeModifiers.value.length > 0) {
    const combinedKey = combineKeys(activeModifiers.value, key);
    emit('press', combinedKey);
    activeModifiers.value = []; // 发送后清空
  } else {
    emit('press', key);
  }
}

// 点击快捷键按钮（直接发送，清空修饰键状态）
function handleShortcutClick(key: string) {
  activeModifiers.value = [];
  emit('press', key);
}

// 清空修饰键状态
function clearModifiers() {
  activeModifiers.value = [];
}

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 获取按键样式
function getKeyStyle(key: KeyDefinition): Record<string, string> {
  const style: Record<string, string> = {};
  if (key.width) {
    style.width = `${key.width}px`;
  }
  if (key.height) {
    style.height = `${key.height * 38 + (key.height - 1) * 6}px`;
  }
  if (key.color) {
    style.background = key.color;
    style.color = '#fff';
  }
  return style;
}

// 获取按键类名
function getKeyClass(key: KeyDefinition): Record<string, boolean> {
  return {
    'key-btn': true,
    'key-modifier': key.type === 'modifier',
    'key-active': key.type === 'modifier' && isKeyActive(key.value),
  };
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="按键操作"
    width="auto"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <!-- 只有桌面端设备才显示完整键盘 -->
    <template v-if="isDesktop">
      <div class="keyboard-wrapper">
        <!-- 左侧：键盘主体 -->
        <div class="keyboard-left">
          <!-- 常用快捷键区 -->
          <div class="shortcuts-section">
            <div class="section-label">常用快捷键（一键发送）</div>
            <div class="shortcuts-grid">
              <ElButton
                v-for="shortcut in shortcuts"
                :key="shortcut.value"
                :style="getKeyStyle(shortcut)"
                :class="getKeyClass(shortcut)"
                :disabled="disabled"
                size="small"
                @click="handleShortcutClick(shortcut.value)"
              >
                {{ shortcut.label }}
              </ElButton>
            </div>
          </div>

          <!-- 108键键盘布局 -->
          <div class="keyboard-body">
            <!-- 左侧主键盘区 -->
            <div class="main-keyboard">
              <!-- 功能键行 -->
              <div class="key-row">
                <ElButton
                  v-for="key in FUNCTION_KEYS_ROW"
                  :key="key.value"
                  :style="getKeyStyle(key)"
                  :class="getKeyClass(key)"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>

              <!-- 数字行 -->
              <div class="key-row">
                <ElButton
                  v-for="key in NUMBER_ROW"
                  :key="key.value"
                  :style="getKeyStyle(key)"
                  :class="getKeyClass(key)"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>

              <!-- Tab 行 -->
              <div class="key-row">
                <ElButton
                  v-for="key in TAB_ROW"
                  :key="key.value + '-tab'"
                  :style="getKeyStyle(key)"
                  :class="getKeyClass(key)"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>

              <!-- Caps 行 -->
              <div class="key-row">
                <ElButton
                  v-for="key in CAPS_ROW"
                  :key="key.value + '-caps'"
                  :style="getKeyStyle(key)"
                  :class="getKeyClass(key)"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>

              <!-- Shift 行 -->
              <div class="key-row">
                <ElButton
                  v-for="key in SHIFT_ROW"
                  :key="key.value + '-shift'"
                  :style="getKeyStyle(key)"
                  :class="getKeyClass(key)"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>

              <!-- 底行修饰键 -->
              <div class="key-row">
                <ElButton
                  v-for="key in bottomRow"
                  :key="key.value + '-bottom'"
                  :style="getKeyStyle(key)"
                  :class="getKeyClass(key)"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>
            </div>

            <!-- 中间编辑键区 -->
            <div class="edit-keyboard">
              <div class="key-row">
                <ElButton
                  v-for="key in EDIT_KEYS.slice(0, 3)"
                  :key="key.value"
                  :style="getKeyStyle(key)"
                  class="key-btn"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>
              <div class="key-row">
                <ElButton
                  v-for="key in EDIT_KEYS.slice(3, 6)"
                  :key="key.value"
                  :style="getKeyStyle(key)"
                  class="key-btn"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>
              <div class="spacer"></div>
              <!-- 方向键 -->
              <div class="arrow-keys">
                <ElButton
                  v-if="ARROW_KEYS[0]"
                  :style="getKeyStyle(ARROW_KEYS[0])"
                  class="key-btn"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(ARROW_KEYS[0].value, ARROW_KEYS[0].type)"
                >
                  {{ ARROW_KEYS[0].label }}
                </ElButton>
                <div class="arrow-row">
                  <ElButton
                    v-for="key in ARROW_KEYS.slice(1)"
                    :key="key.value"
                    :style="getKeyStyle(key)"
                    class="key-btn"
                    :disabled="disabled"
                    size="small"
                    @click="handleKeyClick(key.value, key.type)"
                  >
                    {{ key.label }}
                  </ElButton>
                </div>
              </div>
            </div>

            <!-- 右侧数字小键盘 -->
            <div class="numpad-keyboard">
              <div
                v-for="(row, rowIndex) in NUMPAD_KEYS"
                :key="'numpad-row-' + rowIndex"
                class="key-row"
              >
                <ElButton
                  v-for="key in row"
                  :key="key.value"
                  :style="getKeyStyle(key)"
                  class="key-btn"
                  :disabled="disabled"
                  size="small"
                  @click="handleKeyClick(key.value, key.type)"
                >
                  {{ key.label }}
                </ElButton>
              </div>
            </div>
          </div>

          <!-- 底部操作按钮 -->
          <div class="keyboard-footer">
            <ElButton :disabled="disabled" @click="clearModifiers">
              清空修饰键
            </ElButton>
            <ElButton type="danger" :disabled="disabled" @click="handleClose">
              关闭
            </ElButton>
          </div>
        </div>

        <!-- 右侧：使用说明 -->
        <div class="usage-guide">
          <h4>使用说明</h4>

          <div class="guide-item">
            <p class="guide-title">🔵 常用快捷键</p>
            <p class="guide-desc">点击按钮直接发送组合键，无需其他操作</p>
          </div>

          <div class="guide-item">
            <p class="guide-title-orange">🟠 修饰键 (Ctrl/Alt/Win)</p>
            <p class="guide-desc">用于组合键累加操作：</p>
            <ul class="guide-list">
              <li>点击修饰键 → 高亮显示</li>
              <li>再点击其他键 → 发送组合</li>
              <li>例：点Ctrl，再点C → 发送Ctrl+C</li>
            </ul>
          </div>

          <div class="guide-item">
            <p class="guide-title-gray">⚪ 普通按键</p>
            <p class="guide-desc">点击直接发送单个按键</p>
          </div>

          <div class="guide-tip">
            💡 发送组合键后，修饰键状态自动清空。<br>需手动清空请点"清空修饰键"
          </div>
        </div>
      </div>
    </template>

    <!-- 移动端设备显示简化的按键列表 -->
    <template v-else>
      <div class="mobile-keyboard">
        <div class="key-desc-top">选择按键类型</div>
        <div class="key-list">
          <ElButton
            v-for="key in [
              { value: 'HOME', icon: '🏠', text: 'Home', desc: '返回主页' },
              { value: 'BACK', icon: '↩️', text: 'Back', desc: '返回上一页', devices: ['android'] },
              { value: 'MENU', icon: '📋', text: 'Menu', desc: '菜单键', devices: ['android'] },
              { value: 'ENTER', icon: '⏎', text: 'Enter', desc: '确认' },
              { value: 'SEARCH', icon: '🔍', text: 'Search', desc: '搜索键', devices: ['android'] },
              { value: 'VOLUME_UP', icon: '🔊', text: 'Volume Up', desc: '音量+' },
              { value: 'VOLUME_DOWN', icon: '🔉', text: 'Volume Down', desc: '音量-' },
              { value: 'LOCK', icon: '🔴', text: 'Lock', desc: '电源键' },
            ].filter(k => !k.devices || k.devices.includes(deviceType || 'android'))"
            :key="key.value"
            type="primary"
            class="key-item-btn"
            :disabled="disabled"
            @click="handleKeyClick(key.value, 'normal')"
          >
            <span class="key-icon">{{ key.icon }}</span>
            <span class="key-text">{{ key.text }}</span>
            <span class="key-desc">({{ key.desc }})</span>
          </ElButton>
        </div>
        <div class="key-tip">点击按键立即执行</div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
/* 整体布局：键盘和使用说明在同一行 */
.keyboard-wrapper {
  display: flex;
  gap: 20px;
  padding: 16px;
  background: #f5f7fa;
}

/* 左侧键盘主体 */
.keyboard-left {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 常用快捷键区 */
.shortcuts-section {
  text-align: center;
}

.section-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}

.shortcuts-grid {
  display: flex;
  gap: 6px;
  justify-content: center;
  flex-wrap: wrap;
}

/* 108键键盘布局 */
.keyboard-body {
  display: flex;
  gap: 12px;
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
}

/* 主键盘区 */
.main-keyboard {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 编辑键区 */
.edit-keyboard {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.spacer {
  height: 20px;
}

.arrow-keys {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.arrow-row {
  display: flex;
  gap: 4px;
}

/* 数字小键盘 */
.numpad-keyboard {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 按键行 */
.key-row {
  display: flex;
  gap: 4px;
}

/* 按键基础样式 */
.key-btn {
  min-width: 38px;
  height: 32px;
  padding: 0 8px;
  font-size: 10px;
  font-weight: 500;
  border-radius: 4px;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
  color: #606266;
  transition: all 0.2s;
}

.key-btn:hover:not(:disabled) {
  background-color: #e9ecf0;
  border-color: #c0c4cc;
}

/* 修饰键样式 */
.key-modifier {
  background-color: #fdf6ec;
  border-color: #f5dab1;
  color: #e6a23c;
}

.key-modifier:hover:not(:disabled) {
  background-color: #faecd8;
  border-color: #e6be7b;
}

.key-modifier.key-active {
  background-color: #e6a23c;
  border-color: #e6a23c;
  color: #fff;
}

/* 底部操作按钮 */
.keyboard-footer {
  display: flex;
  justify-content: center;
  gap: 8px;
}

/* 右侧使用说明 */
.usage-guide {
  width: 200px;
  background: #e6f7ff;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #91d5ff;
}

.usage-guide h4 {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: #0050b3;
}

.guide-item {
  margin-bottom: 12px;
}

.guide-title {
  font-size: 11px;
  color: #1890ff;
  margin: 0 0 4px 0;
  font-weight: bold;
}

.guide-title-orange {
  font-size: 11px;
  color: #e6a23c;
  margin: 0 0 4px 0;
  font-weight: bold;
}

.guide-title-gray {
  font-size: 11px;
  color: #909399;
  margin: 0 0 4px 0;
  font-weight: bold;
}

.guide-desc {
  font-size: 10px;
  color: #0050b3;
  margin: 0;
  line-height: 1.5;
}

.guide-list {
  font-size: 10px;
  color: #0050b3;
  margin: 4px 0;
  padding-left: 14px;
  line-height: 1.6;
}

.guide-tip {
  font-size: 10px;
  color: #1890ff;
  border-top: 1px solid #91d5ff;
  padding-top: 10px;
  margin-top: 10px;
  line-height: 1.5;
}

/* 移动端键盘样式 */
.mobile-keyboard {
  min-width: 300px;
}

.key-desc-top {
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
}

.key-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.key-item-btn {
  width: 100%;
  padding: 10px;
  text-align: left;
  justify-content: flex-start;
}

.key-item-btn :deep(.el-button__content) {
  justify-content: flex-start;
}

.key-icon {
  display: inline-block;
  width: 24px;
  text-align: center;
}

.key-text {
  font-size: 13px;
  min-width: 100px;
}

.key-desc {
  font-size: 12px;
  opacity: 0.8;
}

.key-tip {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
  font-size: 12px;
  color: #999;
  text-align: center;
}
</style>