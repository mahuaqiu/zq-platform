<script lang="ts" setup>
import { computed, ref } from 'vue';

import { ElButton, ElDialog } from 'element-plus';

import type { DeviceType } from '../types';
import {
  CAPS_ROW,
  combineKeys,
  MAC_SHORTCUTS,
  NUMBER_ROW,
  SHIFT_ROW,
  TAB_ROW,
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

// 根据平台选择快捷键列表（精简为6个）
const shortcuts = computed(() =>
  isMac.value ? MAC_SHORTCUTS.slice(0, 6) : WINDOWS_SHORTCUTS.slice(0, 6)
);

// 精简的功能键行（Esc + 运算符号）
const miniFunctionKeys: KeyDefinition[] = [
  { value: 'escape', label: 'Esc', type: 'normal', width: 44 },
  { value: '+', label: '+', type: 'normal', width: 32 },
  { value: '-', label: '-', type: 'normal', width: 32 },
  { value: '*', label: '*', type: 'normal', width: 32 },
  { value: '/', label: '/', type: 'normal', width: 32 },
];

// 精简的数字行（去掉减号，避免重复）
const filteredNumberRow = computed(() =>
  NUMBER_ROW.filter(key => key.value !== '-')
);

// 精简的 Shift 行（只保留左边 Shift）
const filteredShiftRow = computed(() =>
  SHIFT_ROW.slice(0, -1) // 去掉最后一个 Shift
);

// 精简的底行修饰键（去掉右侧重复，添加编辑键）
const customBottomRow = computed(() => {
  if (isMac.value) {
    return [
      { value: 'ctrl', label: 'Ctrl', type: 'modifier', width: 56, color: '#e6a23c' },
      { value: 'opt', label: 'Opt', type: 'modifier', width: 44, color: '#e6a23c' },
      { value: 'cmd', label: 'Cmd', type: 'modifier', width: 44, color: '#e6a23c' },
      { value: 'space', label: 'Space', type: 'normal', width: 120 },
      { value: 'insert', label: 'Ins', type: 'normal', width: 36 },
      { value: 'delete', label: 'Del', type: 'normal', width: 36 },
      { value: 'pageup', label: 'PgUp', type: 'normal', width: 40 },
      { value: 'pagedown', label: 'PgDn', type: 'normal', width: 40 },
    ];
  }
  return [
    { value: 'ctrl', label: 'Ctrl', type: 'modifier', width: 56, color: '#e6a23c' },
    { value: 'win', label: 'Win', type: 'modifier', width: 44, color: '#e6a23c' },
    { value: 'alt', label: 'Alt', type: 'modifier', width: 44, color: '#e6a23c' },
    { value: 'space', label: 'Space', type: 'normal', width: 120 },
    { value: 'insert', label: 'Ins', type: 'normal', width: 36 },
    { value: 'delete', label: 'Del', type: 'normal', width: 36 },
    { value: 'pageup', label: 'PgUp', type: 'normal', width: 40 },
    { value: 'pagedown', label: 'PgDn', type: 'normal', width: 40 },
  ];
});

// 按键是否激活
function isKeyActive(key: string): boolean {
  return activeModifiers.value.includes(key);
}

// 点击修饰键
function handleModifierClick(key: string) {
  const index = activeModifiers.value.indexOf(key);
  if (index >= 0) {
    activeModifiers.value.splice(index, 1);
  } else {
    activeModifiers.value.push(key);
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
    activeModifiers.value = [];
  } else {
    emit('press', key);
  }
}

// 点击快捷键按钮
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
    draggable
    align-center
    @update:model-value="emit('update:visible', $event)"
  >
    <!-- 只有桌面端设备才显示完整键盘 -->
    <template v-if="isDesktop">
      <div class="mini-keyboard">
        <!-- 简化键盘主体 -->
        <div class="keyboard-body">
          <!-- 第一排：Esc + 运算符号 + 快捷键（右侧） -->
          <div class="key-row">
            <ElButton
              v-for="key in miniFunctionKeys"
              :key="key.value"
              :style="getKeyStyle(key)"
              class="key-btn"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
            <!-- 快捷键按钮（靠右放） -->
            <div class="key-row-gap" />
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
            <!-- Ctrl+Alt+Del -->
            <ElButton
              style="background: #f56c6c; color: #fff;"
              class="key-btn"
              :disabled="disabled"
              size="small"
              @click="handleShortcutClick('ctrl+alt+delete')"
            >
              Ctrl+Alt+Del
            </ElButton>
          </div>

          <!-- 数字行（去掉减号） -->
          <div class="key-row">
            <ElButton
              v-for="key in filteredNumberRow"
              :key="key.value"
              style="width: 32px;"
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

          <!-- Shift 行（去掉右边 Shift） -->
          <div class="key-row">
            <ElButton
              v-for="key in filteredShiftRow"
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

          <!-- 底行：修饰键 + Space + 编辑键 -->
          <div class="key-row">
            <ElButton
              v-for="key in customBottomRow"
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

        <!-- 底部：修饰键状态 + 操作按钮 -->
        <div class="keyboard-footer">
          <div class="modifier-status">
            <span v-if="activeModifiers.length > 0" class="active-modifiers">
              当前: <strong>{{ activeModifiers.join('+') }}</strong>
            </span>
            <span v-else class="no-modifiers">点击修饰键组合发送</span>
          </div>
          <div class="footer-actions">
            <ElButton size="small" :disabled="disabled" @click="clearModifiers">
              清空
            </ElButton>
            <ElButton size="small" type="danger" :disabled="disabled" @click="handleClose">
              关闭
            </ElButton>
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
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
/* 精简键盘整体 */
.mini-keyboard {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: #f5f7fa;
}

/* 键盘主体 */
.keyboard-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #fff;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #ddd;
}

/* 按键行 */
.key-row {
  display: flex;
  gap: 2px;
}

.key-row-gap {
  flex: 1;
  min-width: 16px;
}

.key-gap {
  width: 8px;
}

/* 按键基础样式 */
.key-btn {
  min-width: 32px;
  height: 28px;
  padding: 0 4px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 3px;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
  color: #606266;
  transition: all 0.15s;
}

.key-btn:hover:not(:disabled) {
  background-color: #e9ecf0;
}

/* 修饰键样式 */
.key-modifier {
  background-color: #fdf6ec;
  border-color: #f5dab1;
  color: #e6a23c;
}

.key-modifier.key-active {
  background-color: #e6a23c;
  border-color: #e6a23c;
  color: #fff;
}

/* 底部操作区 */
.keyboard-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
}

.modifier-status {
  font-size: 11px;
  color: #909399;
}

.active-modifiers strong {
  color: #e6a23c;
}

.footer-actions {
  display: flex;
  gap: 4px;
}

/* 移动端键盘样式 */
.mobile-keyboard {
  min-width: 280px;
}

.key-desc-top {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.key-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.key-item-btn {
  width: 100%;
  padding: 8px;
  text-align: left;
  justify-content: flex-start;
}

.key-item-btn :deep(.el-button__content) {
  justify-content: flex-start;
}

.key-icon {
  display: inline-block;
  width: 20px;
  text-align: center;
}

.key-text {
  font-size: 12px;
  min-width: 80px;
}

.key-desc {
  font-size: 11px;
  opacity: 0.8;
}
</style>