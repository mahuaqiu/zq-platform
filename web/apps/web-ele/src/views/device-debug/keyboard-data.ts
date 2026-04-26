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
  height?: number;      // 按键高度倍数（可选，用于数字小键盘）
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
 * 编辑键区 (Ins/Home/PgUp/Del/End/PgDn)
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