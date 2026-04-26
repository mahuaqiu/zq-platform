# Windows/MAC 按键操作弹窗实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为设备调试功能添加 Windows/MAC 按键操作弹窗，支持虚拟键盘发送按键和组合键。

**Architecture:** 重写 KeyPressDialog.vue 组件，实现 108 键虚拟键盘布局，包含常用快捷键区、主键盘区、编辑键区、数字小键盘区和右侧说明区。修饰键采用累加模式，支持组合键构建。

**Tech Stack:** Vue 3 + TypeScript + Element Plus

---

## 文件结构

```
web/apps/web-ele/src/views/device-debug/
├── components/
│   └── KeyPressDialog.vue      # 重写：完整虚拟键盘弹窗
├── hooks/
│   └── useDeviceAction.ts      # 已有，无需修改（pressKey 已支持组合键）
├── types.ts                    # 扩展：添加按键定义类型
└── keyboard-data.ts            # 新建：按键数据定义
```

---

### Task 1: 创建按键数据定义文件

**Files:**
- Create: `web/apps/web-ele/src/views/device-debug/keyboard-data.ts`

- [ ] **Step 1: 创建 keyboard-data.ts 文件**

定义按键数据结构、常用快捷键列表、主键盘按键列表、编辑键列表、数字小键盘按键列表、修饰键列表。

```typescript
/**
 * 按键类型
 */
export type KeyType = 'normal' | 'modifier' | 'shortcut';

/**
 * 按键定义
 */
export interface KeyDefinition {
  value: string;        // 发送的按键代码
  label: string;        // 显示文本
  type: KeyType;        // 按键类型
  width?: number;       // 按键宽度（可选，默认 38）
  platforms?: ('windows' | 'mac')[];  // 支持的平台（可选）
  color?: string;       // 按键颜色（可选）
}

/**
 * 修饰键列表
 */
export const MODIFIER_KEYS: KeyDefinition[] = [
  { value: 'ctrl', label: 'Ctrl', type: 'modifier', color: '#e6a23c' },
  { value: 'alt', label: 'Alt', type: 'modifier', color: '#e6a23c' },
  { value: 'shift', label: 'Shift', type: 'modifier', color: '#e6a23c' },
  { value: 'win', label: 'Win', type: 'modifier', platforms: ['windows'], color: '#e6a23c' },
  { value: 'cmd', label: '⌘ Cmd', type: 'modifier', platforms: ['mac'], color: '#e6a23c' },
  { value: 'opt', label: '⌥ Opt', type: 'modifier', platforms: ['mac'], color: '#e6a23c' },
  { value: 'fn', label: 'Fn', type: 'modifier', platforms: ['mac'], color: '#e6a23c' },
];

/**
 * Windows 常用快捷键
 */
export const WINDOWS_SHORTCUTS: KeyDefinition[] = [
  { value: 'ctrl+c', label: 'Ctrl+C', type: 'shortcut', color: '#409eff' },
  { value: 'ctrl+v', label: 'Ctrl+V', type: 'shortcut', color: '#409eff' },
  { value: 'ctrl+z', label: 'Ctrl+Z', type: 'shortcut', color: '#409eff' },
  { value: 'ctrl+s', label: 'Ctrl+S', type: 'shortcut', color: '#409eff' },
  { value: 'ctrl+a', label: 'Ctrl+A', type: 'shortcut', color: '#e6a23c' },
  { value: 'alt+tab', label: 'Alt+Tab', type: 'shortcut', color: '#67c23a' },
  { value: 'ctrl+alt+delete', label: 'Ctrl+Alt+Del', type: 'shortcut', color: '#f56c6c' },
  { value: 'shift+delete', label: 'Shift+Del', type: 'shortcut', color: '#909399' },
  { value: 'win+e', label: 'Win+E', type: 'shortcut', color: '#67c23a' },
  { value: 'win+d', label: 'Win+D', type: 'shortcut', color: '#67c23a' },
];

/**
 * MAC 常用快捷键
 */
export const MAC_SHORTCUTS: KeyDefinition[] = [
  { value: 'cmd+c', label: '⌘C', type: 'shortcut', color: '#409eff' },
  { value: 'cmd+v', label: '⌘V', type: 'shortcut', color: '#409eff' },
  { value: 'cmd+z', label: '⌘Z', type: 'shortcut', color: '#409eff' },
  { value: 'cmd+s', label: '⌘S', type: 'shortcut', color: '#409eff' },
  { value: 'cmd+a', label: '⌘A', type: 'shortcut', color: '#e6a23c' },
  { value: 'cmd+tab', label: '⌘Tab', type: 'shortcut', color: '#67c23a' },
  { value: 'cmd+space', label: '⌘Space', type: 'shortcut', color: '#67c23a' },
  { value: 'cmd+q', label: '⌘Q', type: 'shortcut', color: '#f56c6c' },
  { value: 'cmd+e', label: '⌘E', type: 'shortcut', color: '#67c23a' },
  { value: 'cmd+d', label: '⌘D', type: 'shortcut', color: '#67c23a' },
];

/**
 * 功能键行 (F1-F12 + Esc + PrtSc/ScrLk/Pause)
 */
export const FUNCTION_KEYS_ROW: KeyDefinition[] = [
  { value: 'printscreen', label: 'PrtSc', type: 'normal', width: 44 },
  { value: 'scrolllock', label: 'ScrLk', type: 'normal', width: 44 },
  { value: 'pause', label: 'Pause', type: 'normal', width: 44 },
  { value: 'escape', label: 'Esc', type: 'normal', width: 38 },
  { value: 'f1', label: 'F1', type: 'normal', width: 32 },
  { value: 'f2', label: 'F2', type: 'normal', width: 32 },
  { value: 'f3', label: 'F3', type: 'normal', width: 32 },
  { value: 'f4', label: 'F4', type: 'normal', width: 32 },
  { value: 'f5', label: 'F5', type: 'normal', width: 32 },
  { value: 'f6', label: 'F6', type: 'normal', width: 32 },
  { value: 'f7', label: 'F7', type: 'normal', width: 32 },
  { value: 'f8', label: 'F8', type: 'normal', width: 32 },
  { value: 'f9', label: 'F9', type: 'normal', width: 32 },
  { value: 'f10', label: 'F10', type: 'normal', width: 32 },
  { value: 'f11', label: 'F11', type: 'normal', width: 32 },
  { value: 'f12', label: 'F12', type: 'normal', width: 32 },
];

/**
 * 数字行
 */
export const NUMBER_ROW: KeyDefinition[] = [
  { value: '1', label: '1', type: 'normal' },
  { value: '2', label: '2', type: 'normal' },
  { value: '3', label: '3', type: 'normal' },
  { value: '4', label: '4', type: 'normal' },
  { value: '5', label: '5', type: 'normal' },
  { value: '6', label: '6', type: 'normal' },
  { value: '7', label: '7', type: 'normal' },
  { value: '8', label: '8', type: 'normal' },
  { value: '9', label: '9', type: 'normal' },
  { value: '0', label: '0', type: 'normal' },
  { value: '-', label: '-', type: 'normal' },
  { value: '=', label: '=', type: 'normal' },
  { value: 'backspace', label: 'Back', type: 'normal', width: 54, color: '#f56c6c' },
];

/**
 * Tab 行
 */
export const TAB_ROW: KeyDefinition[] = [
  { value: 'tab', label: 'Tab', type: 'normal', width: 54 },
  { value: 'q', label: 'Q', type: 'normal' },
  { value: 'w', label: 'W', type: 'normal' },
  { value: 'e', label: 'E', type: 'normal' },
  { value: 'r', label: 'R', type: 'normal' },
  { value: 't', label: 'T', type: 'normal' },
  { value: 'y', label: 'Y', type: 'normal' },
  { value: 'u', label: 'U', type: 'normal' },
  { value: 'i', label: 'I', type: 'normal' },
  { value: 'o', label: 'O', type: 'normal' },
  { value: 'p', label: 'P', type: 'normal' },
  { value: '[', label: '[', type: 'normal' },
  { value: ']', label: ']', type: 'normal' },
  { value: '\\', label: '\\', type: 'normal' },
];

/**
 * Caps 行
 */
export const CAPS_ROW: KeyDefinition[] = [
  { value: 'capslock', label: 'Caps', type: 'normal', width: 62 },
  { value: 'a', label: 'A', type: 'normal' },
  { value: 's', label: 'S', type: 'normal' },
  { value: 'd', label: 'D', type: 'normal' },
  { value: 'f', label: 'F', type: 'normal' },
  { value: 'g', label: 'G', type: 'normal' },
  { value: 'h', label: 'H', type: 'normal' },
  { value: 'j', label: 'J', type: 'normal' },
  { value: 'k', label: 'K', type: 'normal' },
  { value: 'l', label: 'L', type: 'normal' },
  { value: ';', label: ';', type: 'normal' },
  { value: "'", label: "'", type: 'normal' },
  { value: 'enter', label: 'Enter', type: 'normal', width: 74, color: '#67c23a' },
];

/**
 * Shift 行
 */
export const SHIFT_ROW: KeyDefinition[] = [
  { value: 'shift', label: 'Shift', type: 'modifier', width: 86, color: '#e6a23c' },
  { value: 'z', label: 'Z', type: 'normal' },
  { value: 'x', label: 'X', type: 'normal' },
  { value: 'c', label: 'C', type: 'normal' },
  { value: 'v', label: 'V', type: 'normal' },
  { value: 'b', label: 'B', type: 'normal' },
  { value: 'n', label: 'N', type: 'normal' },
  { value: 'm', label: 'M', type: 'normal' },
  { value: ',', label: ',', type: 'normal' },
  { value: '.', label: '.', type: 'normal' },
  { value: '/', label: '/', type: 'normal' },
  { value: 'shift', label: 'Shift', type: 'modifier', width: 86, color: '#e6a23c' },
];

/**
 * Windows 底行修饰键
 */
export const WINDOWS_BOTTOM_ROW: KeyDefinition[] = [
  { value: 'ctrl', label: 'Ctrl', type: 'modifier', width: 56, color: '#e6a23c' },
  { value: 'win', label: 'Win', type: 'modifier', width: 44, color: '#e6a23c' },
  { value: 'alt', label: 'Alt', type: 'modifier', width: 44, color: '#e6a23c' },
  { value: 'space', label: 'Space', type: 'normal', width: 200 },
  { value: 'alt', label: 'Alt', type: 'modifier', width: 44, color: '#e6a23c' },
  { value: 'win', label: 'Win', type: 'modifier', width: 44, color: '#e6a23c' },
  { value: 'menu', label: 'Menu', type: 'normal', width: 44 },
  { value: 'ctrl', label: 'Ctrl', type: 'modifier', width: 56, color: '#e6a23c' },
];

/**
 * MAC 底行修饰键
 */
export const MAC_BOTTOM_ROW: KeyDefinition[] = [
  { value: 'ctrl', label: 'Ctrl', type: 'modifier', width: 56, color: '#e6a23c' },
  { value: 'opt', label: '⌥ Opt', type: 'modifier', width: 44, color: '#e6a23c' },
  { value: 'cmd', label: '⌘ Cmd', type: 'modifier', width: 56, color: '#e6a23c' },
  { value: 'space', label: 'Space', type: 'normal', width: 200 },
  { value: 'cmd', label: '⌘ Cmd', type: 'modifier', width: 56, color: '#e6a23c' },
  { value: 'opt', label: '⌥ Opt', type: 'modifier', width: 44, color: '#e6a23c' },
  { value: 'fn', label: 'Fn', type: 'modifier', width: 44, color: '#e6a23c' },
];

/**
 * 编辑键区 (Ins/Home/PgUp/Del/End/PgDn + 方向键)
 */
export const EDIT_KEYS: KeyDefinition[] = [
  { value: 'insert', label: 'Ins', type: 'normal', width: 40 },
  { value: 'home', label: 'Home', type: 'normal', width: 40 },
  { value: 'pageup', label: 'PgUp', type: 'normal', width: 40 },
  { value: 'delete', label: 'Del', type: 'normal', width: 40 },
  { value: 'end', label: 'End', type: 'normal', width: 40 },
  { value: 'pagedown', label: 'PgDn', type: 'normal', width: 40 },
];

/**
 * 方向键
 */
export const ARROW_KEYS: KeyDefinition[] = [
  { value: 'up', label: '↑', type: 'normal', width: 40 },
  { value: 'left', label: '←', type: 'normal', width: 40 },
  { value: 'down', label: '↓', type: 'normal', width: 40 },
  { value: 'right', label: '→', type: 'normal', width: 40 },
];

/**
 * 数字小键盘
 */
export const NUMPAD_KEYS: KeyDefinition[][] = [
  [
    { value: 'numlock', label: 'Num', type: 'normal', width: 40 },
    { value: 'numpaddivide', label: '/', type: 'normal', width: 40 },
    { value: 'numpadmultiply', label: '*', type: 'normal', width: 40 },
    { value: 'numpadsubtract', label: '-', type: 'normal', width: 40 },
  ],
  [
    { value: 'numpad7', label: '7', type: 'normal', width: 40 },
    { value: 'numpad8', label: '8', type: 'normal', width: 40 },
    { value: 'numpad9', label: '9', type: 'normal', width: 40 },
    { value: 'numpadadd', label: '+', type: 'normal', width: 40, height: 2 },
  ],
  [
    { value: 'numpad4', label: '4', type: 'normal', width: 40 },
    { value: 'numpad5', label: '5', type: 'normal', width: 40 },
    { value: 'numpad6', label: '6', type: 'normal', width: 40 },
  ],
  [
    { value: 'numpad1', label: '1', type: 'normal', width: 40 },
    { value: 'numpad2', label: '2', type: 'normal', width: 40 },
    { value: 'numpad3', label: '3', type: 'normal', width: 40 },
    { value: 'numpadenter', label: 'Enter', type: 'normal', width: 40, height: 2, color: '#67c23a' },
  ],
  [
    { value: 'numpad0', label: '0', type: 'normal', width: 84 },
    { value: 'numpaddecimal', label: '.', type: 'normal', width: 40 },
  ],
];

/**
 * 获取平台对应的修饰键名称
 */
export function getModifierDisplayValue(key: string, platform: 'windows' | 'mac'): string {
  if (platform === 'mac') {
    const macMap: Record<string, string> = {
      'ctrl': 'ctrl',
      'alt': 'opt',
      'win': 'cmd',
    };
    return macMap[key] || key;
  }
  return key;
}

/**
 * 组合修饰键和普通键
 */
export function combineKeys(modifiers: string[], key: string): string {
  return [...modifiers, key].join('+');
}
```

- [ ] **Step 2: Commit keyboard-data.ts**

```bash
git add web/apps/web-ele/src/views/device-debug/keyboard-data.ts
git commit -m "feat: 添加按键数据定义文件"
```

---

### Task 2: 重写 KeyPressDialog.vue 组件

**Files:**
- Modify: `web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue`

- [ ] **Step 1: 重写 KeyPressDialog.vue**

完整重写组件，包含：
- Props: visible, disabled, deviceType
- 修饰键累加状态管理
- 常用快捷键区渲染（根据设备类型动态切换）
- 虚拟键盘区渲染（108键布局）
- 右侧使用说明区
- 清空修饰键和关闭按钮

```vue
<script lang="ts" setup>
import { computed, ref } from 'vue';
import { ElButton, ElDialog } from 'element-plus';
import type { DeviceType } from '../types';
import {
  WINDOWS_SHORTCUTS,
  MAC_SHORTCUTS,
  FUNCTION_KEYS_ROW,
  NUMBER_ROW,
  TAB_ROW,
  CAPS_ROW,
  SHIFT_ROW,
  WINDOWS_BOTTOM_ROW,
  MAC_BOTTOM_ROW,
  EDIT_KEYS,
  ARROW_KEYS,
  NUMPAD_KEYS,
  combineKeys,
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

// 判断是否为 Windows
const isWindows = computed(() => props.deviceType === 'windows');

// 判断是否为 MAC
const isMac = computed(() => props.deviceType === 'mac');

// 根据平台获取快捷键列表
const shortcuts = computed(() =>
  isMac.value ? MAC_SHORTCUTS : WINDOWS_SHORTCUTS
);

// 根据平台获取底行修饰键
const bottomRow = computed(() =>
  isMac.value ? MAC_BOTTOM_ROW : WINDOWS_BOTTOM_ROW
);

// 当前修饰键组合显示文本
const modifierDisplay = computed(() => {
  if (activeModifiers.value.length === 0) return '';
  return activeModifiers.value.map(m => {
    if (isMac.value) {
      const macSymbols: Record<string, string> = {
        'ctrl': 'Ctrl',
        'opt': '⌥',
        'cmd': '⌘',
        'shift': 'Shift',
        'fn': 'Fn',
      };
      return macSymbols[m] || m;
    }
    return m.toUpperCase();
  }).join('+');
});

// 关闭弹窗
function handleClose() {
  emit('update:visible', false);
}

// 点击修饰键
function handleModifierClick(key: string) {
  const index = activeModifiers.value.indexOf(key);
  if (index >= 0) {
    // 已激活，取消激活
    activeModifiers.value.splice(index, 1);
  } else {
    // 未激活，添加激活
    activeModifiers.value.push(key);
  }
}

// 点击快捷键按钮（直接发送组合键）
function handleShortcutClick(key: string) {
  // 清空修饰键状态，直接发送预设组合键
  activeModifiers.value = [];
  emit('press', key);
}

// 点击普通按键
function handleKeyClick(key: string, keyType: string) {
  if (keyType === 'modifier') {
    handleModifierClick(key);
    return;
  }

  // 有修饰键激活时，组装组合键发送
  if (activeModifiers.value.length > 0) {
    const combinedKey = combineKeys(activeModifiers.value, key);
    emit('press', combinedKey);
    // 发送后清空修饰键状态
    activeModifiers.value = [];
  } else {
    // 直接发送单个按键
    emit('press', key);
  }
}

// 清空修饰键状态
function clearModifiers() {
  activeModifiers.value = [];
}

// 检查修饰键是否激活
function isModifierActive(key: string): boolean {
  return activeModifiers.value.includes(key);
}

// 获取按键样式
function getKeyStyle(key: KeyDefinition): Record<string, string> {
  const style: Record<string, string> = {};
  if (key.width) {
    style.width = `${key.width}px`;
  }
  if (key.color && key.type !== 'modifier') {
    style.background = key.color;
    style.color = '#fff';
  }
  if (isModifierActive(key.value) && key.type === 'modifier') {
    style.background = '#e6a23c';
    style.color = '#fff';
  }
  return style;
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    title="按键操作"
    width="780px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <!-- 非桌面端设备提示 -->
    <div v-if="!isDesktop" class="not-desktop-tip">
      <p>当前设备类型不支持虚拟键盘操作</p>
      <p>请使用移动端按键操作</p>
    </div>

    <!-- 桌面端键盘布局 -->
    <div v-else class="keyboard-container">
      <!-- 常用快捷键区 -->
      <div class="shortcuts-section">
        <div class="section-label">常用快捷键（一键发送）</div>
        <div class="shortcuts-grid">
          <ElButton
            v-for="shortcut in shortcuts"
            :key="shortcut.value"
            :style="getKeyStyle(shortcut)"
            :disabled="disabled"
            size="small"
            @click="handleShortcutClick(shortcut.value)"
          >
            {{ shortcut.label }}
          </ElButton>
        </div>
      </div>

      <!-- 键盘主体 -->
      <div class="keyboard-body">
        <!-- 左侧：主键盘区 -->
        <div class="main-keyboard">
          <!-- 功能键行 -->
          <div class="keyboard-row">
            <ElButton
              v-for="key in FUNCTION_KEYS_ROW"
              :key="key.value"
              :style="getKeyStyle(key)"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>

          <!-- 数字行 -->
          <div class="keyboard-row">
            <ElButton
              v-for="key in NUMBER_ROW"
              :key="key.value"
              :style="getKeyStyle(key)"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>

          <!-- Tab 行 -->
          <div class="keyboard-row">
            <ElButton
              v-for="key in TAB_ROW"
              :key="key.value + '-tab'"
              :style="getKeyStyle(key)"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>

          <!-- Caps 行 -->
          <div class="keyboard-row">
            <ElButton
              v-for="key in CAPS_ROW"
              :key="key.value + '-caps'"
              :style="getKeyStyle(key)"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>

          <!-- Shift 行 -->
          <div class="keyboard-row">
            <ElButton
              v-for="key in SHIFT_ROW"
              :key="key.value + '-shift'"
              :style="getKeyStyle(key)"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>

          <!-- 底行修饰键 -->
          <div class="keyboard-row">
            <ElButton
              v-for="key in bottomRow"
              :key="key.value + '-bottom'"
              :style="getKeyStyle(key)"
              :class="{ 'modifier-active': isModifierActive(key.value) }"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>

          <!-- 当前修饰键状态 -->
          <div v-if="modifierDisplay" class="modifier-status">
            当前组合: {{ modifierDisplay }}
          </div>
        </div>

        <!-- 中间：编辑键区 -->
        <div class="edit-keyboard">
          <div class="edit-row">
            <ElButton
              v-for="key in EDIT_KEYS.slice(0, 3)"
              :key="key.value"
              :style="getKeyStyle(key)"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>
          <div class="edit-row">
            <ElButton
              v-for="key in EDIT_KEYS.slice(3, 6)"
              :key="key.value"
              :style="getKeyStyle(key)"
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
              :style="getKeyStyle(ARROW_KEYS[0])"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick('up', 'normal')"
            >
              ↑
            </ElButton>
            <div class="arrow-row">
              <ElButton
                :style="getKeyStyle(ARROW_KEYS[1])"
                :disabled="disabled"
                size="small"
                @click="handleKeyClick('left', 'normal')"
              >
                ←
              </ElButton>
              <ElButton
                :style="getKeyStyle(ARROW_KEYS[2])"
                :disabled="disabled"
                size="small"
                @click="handleKeyClick('down', 'normal')"
              >
                ↓
              </ElButton>
              <ElButton
                :style="getKeyStyle(ARROW_KEYS[3])"
                :disabled="disabled"
                size="small"
                @click="handleKeyClick('right', 'normal')"
              >
                →
              </ElButton>
            </div>
          </div>
        </div>

        <!-- 右侧：数字小键盘 -->
        <div class="numpad-keyboard">
          <div
            v-for="(row, rowIndex) in NUMPAD_KEYS"
            :key="'numpad-row-' + rowIndex"
            class="numpad-row"
          >
            <ElButton
              v-for="key in row"
              :key="key.value"
              :style="{ ...getKeyStyle(key), height: key.height ? `${key.height * 38}px` : '28px' }"
              :disabled="disabled"
              size="small"
              @click="handleKeyClick(key.value, key.type)"
            >
              {{ key.label }}
            </ElButton>
          </div>
        </div>
      </div>

      <!-- 右侧使用说明 -->
      <div class="usage-guide">
        <h4>使用说明</h4>
        <div class="guide-item">
          <span class="guide-icon">🔵</span>
          <span class="guide-title">常用快捷键</span>
          <p>点击按钮直接发送组合键</p>
        </div>
        <div class="guide-item">
          <span class="guide-icon">🟠</span>
          <span class="guide-title">修饰键 (Ctrl/Alt/Win)</span>
          <p>用于组合键累加操作：</p>
          <ul>
            <li>点击修饰键 → 高亮显示</li>
            <li>再点击其他键 → 发送组合</li>
            <li>例：点Ctrl，再点C → Ctrl+C</li>
          </ul>
        </div>
        <div class="guide-item">
          <span class="guide-icon">⚪</span>
          <span class="guide-title">普通按键</span>
          <p>点击直接发送单个按键</p>
        </div>
        <div class="guide-tip">
          💡 发送组合键后，修饰键状态自动清空
        </div>
      </div>
    </div>

    <!-- 底部操作按钮 -->
    <template #footer>
      <div class="dialog-footer">
        <ElButton @click="clearModifiers">清空修饰键</ElButton>
        <ElButton type="danger" @click="handleClose">关闭</ElButton>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.keyboard-container {
  display: flex;
  gap: 16px;
}

.not-desktop-tip {
  text-align: center;
  padding: 20px;
  color: #909399;
}

.shortcuts-section {
  margin-bottom: 12px;
}

.section-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
  text-align: center;
}

.shortcuts-grid {
  display: flex;
  gap: 6px;
  justify-content: center;
  flex-wrap: wrap;
}

.keyboard-body {
  display: flex;
  gap: 12px;
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #ddd;
}

.main-keyboard {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.keyboard-row {
  display: flex;
  gap: 4px;
  justify-content: center;
}

.keyboard-row .el-button {
  min-width: 38px;
  padding: 6px 0;
  font-size: 11px;
}

.modifier-active {
  background: #e6a23c !important;
  color: #fff !important;
}

.modifier-status {
  margin-top: 8px;
  font-size: 11px;
  color: #e6a23c;
  text-align: center;
}

.edit-keyboard {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.edit-row {
  display: flex;
  gap: 4px;
}

.edit-row .el-button {
  min-width: 40px;
  padding: 6px 0;
  font-size: 10px;
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

.arrow-keys .el-button {
  min-width: 40px;
  padding: 6px 0;
  font-size: 12px;
}

.numpad-keyboard {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.numpad-row {
  display: flex;
  gap: 4px;
}

.numpad-row .el-button {
  min-width: 40px;
  padding: 6px 0;
  font-size: 10px;
}

.usage-guide {
  width: 180px;
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

.guide-icon {
  font-size: 12px;
}

.guide-title {
  font-size: 11px;
  font-weight: bold;
  color: #1890ff;
  margin-left: 4px;
}

.guide-item p {
  font-size: 10px;
  color: #0050b3;
  margin: 4px 0 0 0;
  line-height: 1.5;
}

.guide-item ul {
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
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
```

- [ ] **Step 2: Commit KeyPressDialog.vue**

```bash
git add web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue
git commit -m "feat: 重写按键操作弹窗，支持 Windows/MAC 虚拟键盘"
```

---

### Task 3: 测试验证

**Files:**
- Verify: `web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue`

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd web && pnpm dev
```

Expected: 前端服务正常启动，无编译错误

- [ ] **Step 2: 在浏览器中测试按键弹窗**

打开设备调试页面，点击"按键操作"按钮，验证：
1. 弹窗正常显示虚拟键盘布局
2. Windows 设备显示 Windows 键盘，MAC 设备显示 MAC 键盘
3. 修饰键点击后高亮，再次点击取消高亮
4. 点击修饰键后再点击普通键，发送组合键格式正确
5. 常用快捷键一键发送
6. 右侧说明区域正常显示

- [ ] **Step 3: 测试按键发送功能**

连接 Windows 设备，测试以下按键发送：
1. 单键：点击 A 键 → 发送 'a'
2. 组合键：点击 Ctrl，再点击 C → 发送 'ctrl+c'
3. 预设快捷键：点击 Ctrl+C 按钮 → 发送 'ctrl+c'
4. Ctrl+Alt+Del 快捷键 → 发送 'ctrl+alt+delete'

- [ ] **Step 4: 修复发现的问题（如有）**

如有问题，修复并重新测试。

---

### Task 4: 文档更新和最终提交

- [ ] **Step 1: 更新 CLAUDE.md（如需要）**

如有新的开发规范需要记录，更新 CLAUDE.md。

- [ ] **Step 2: 最终提交**

```bash
git add -A
git status
git commit -m "feat(device-debug): 完成 Windows/MAC 按键操作弹窗功能"
```

---

## 成功标准

1. ✅ 按键操作弹窗正确显示 108 键虚拟键盘布局
2. ✅ Windows 和 MAC 平台自动适配，修饰键名称正确
3. ✅ 常用快捷键一键发送，响应及时
4. ✅ 修饰键累加模式正常工作，状态显示清晰
5. ✅ 右侧使用说明区域清晰易懂
6. ✅ 无编译错误，无运行时错误