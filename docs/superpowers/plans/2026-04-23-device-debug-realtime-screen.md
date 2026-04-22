# 设备调试实时屏幕推流实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将设备调试功能从单次 HTTP 截图弹窗改为 WebSocket 实时屏幕推流独立页面，支持 Windows/Mac 全屏调试。

**Architecture:** 前端直接连接 Worker WebSocket 端点接收实时 JPEG 二进制流，操作（点击/滑动/按键/输入）继续使用现有 HTTP API。独立页面布局：Windows/Mac 大屏展示，移动端左侧屏幕+右侧面板。

**Tech Stack:** Vue 3 + Element Plus + WebSocket API + TypeScript

---

## 文件结构

### 需创建的文件

| 文件 | 负责内容 |
|------|----------|
| `web/apps/web-ele/src/views/device-debug/index.vue` | 主页面入口，根据设备类型切换布局 |
| `web/apps/web-ele/src/views/device-debug/components/ScreenDisplay.vue` | 实时屏幕展示，WebSocket 接收画面 |
| `web/apps/web-ele/src/views/device-debug/components/TopNavbar.vue` | 顶部导航栏，设备信息和连接状态 |
| `web/apps/web-ele/src/views/device-debug/components/BottomToolbar.vue` | 底部工具栏，操作按钮 |
| `web/apps/web-ele/src/views/device-debug/components/MobilePanel.vue` | 移动端右侧面板，快捷按键+输入 |
| `web/apps/web-ele/src/views/device-debug/components/UnlockDialog.vue` | 解锁屏幕弹窗（仅移动端） |
| `web/apps/web-ele/src/views/device-debug/components/InstallAppDialog.vue` | 安装 APP 弹窗 |
| `web/apps/web-ele/src/views/device-debug/components/InputTextDialog.vue` | 输入文本弹窗（Windows/Mac） |
| `web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts` | WebSocket 连接管理 |
| `web/apps/web-ele/src/views/device-debug/hooks/useScreenInteraction.ts` | 屏幕交互（点击/滑动坐标转换） |
| `web/apps/web-ele/src/views/device-debug/hooks/useDeviceAction.ts` | 设备操作（按键/输入/安装 API） |
| `web/apps/web-ele/src/views/device-debug/types.ts` | 类型定义 |
| `web/apps/web-ele/src/views/device-debug/utils.ts` | 工具函数（坐标转换等） |
| `web/apps/web-ele/src/router/routes/modules/device-debug.ts` | 路由配置 |

### 需修改的文件

| 文件 | 修改内容 |
|------|----------|
| `web/apps/web-ele/src/views/env-machine/list.vue` | 调试按钮跳转到独立页面 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 添加获取设备详情 API |

### 可复用组件

| 文件 | 复用内容 |
|------|----------|
| `web/apps/web-ele/src/views/env-machine/modules/KeyPressDialog.vue` | 按键操作弹窗（可复用或复制） |
| `web/apps/web-ele/src/views/env-machine/DebugDialog.vue` | 参考 HTTP API 调用方式 |

---

## Task 1: 类型定义和工具函数

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/types.ts`
- Create: `web/apps/web-ele/src/views/device-debug/utils.ts`

- [ ] **Step 1: 创建类型定义文件**

```typescript
// web/apps/web-ele/src/views/device-debug/types.ts

/**
 * 设备类型
 */
export type DeviceType = 'windows' | 'mac' | 'ios' | 'android';

/**
 * WebSocket 连接状态
 */
export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

/**
 * WebSocket 关闭原因
 */
export interface WebSocketCloseInfo {
  code: number;
  reason: string;
}

/**
 * 设备操作类型
 */
export type DeviceActionType = 'click' | 'swipe' | 'input' | 'press' | 'screenshot';

/**
 * 操作参数
 */
export interface ClickParams {
  x: number;
  y: number;
}

export interface SwipeParams {
  from_x: number;
  from_y: number;
  to_x: number;
  to_y: number;
  duration?: number;
}

export interface InputParams {
  text: string;
}

export interface PressParams {
  key: string;
}

/**
 * 设备详情（从 API 获取）
 */
export interface DeviceDetail {
  id: string;
  udid: string;
  device_type: string;
  asset_number: string;
  ip: string;
  port: string;
  worker_host: string;
  worker_port: number;
  status: string;
  device_sn?: string;
}

/**
 * 操作历史记录
 */
export interface OperationRecord {
  type: string;
  params: string;
  status: 'pending' | 'success' | 'failed';
  time: string;
}

/**
 * 屏幕尺寸信息
 */
export interface ScreenSize {
  width: number;
  height: number;
}
```

- [ ] **Step 2: 创建工具函数文件**

```typescript
// web/apps/web-ele/src/views/device-debug/utils.ts

import type { ScreenSize } from './types';

/**
 * 将屏幕展示区的鼠标坐标转换为设备实际坐标
 */
export function convertToDeviceCoords(
  mouseX: number,
  mouseY: number,
  displayWidth: number,
  displayHeight: number,
  deviceWidth: number,
  deviceHeight: number
): { x: number; y: number } {
  const scaleX = deviceWidth / displayWidth;
  const scaleY = deviceHeight / displayHeight;
  return {
    x: Math.round(mouseX * scaleX),
    y: Math.round(mouseY * scaleY)
  };
}

/**
 * 判断是否为移动端设备
 */
export function isMobileDevice(deviceType: string): boolean {
  return ['ios', 'android'].includes(deviceType);
}

/**
 * 判断是否为桌面端设备
 */
export function isDesktopDevice(deviceType: string): boolean {
  return ['windows', 'mac'].includes(deviceType);
}

/**
 * 格式化时间（HH:MM:SS）
 */
export function formatTime(): string {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

/**
 * 格式化操作历史显示文本
 */
export function formatHistoryDisplay(type: string, params: Record<string, any>): string {
  switch (type) {
    case 'screenshot':
      return ''; // 截图操作不显示在历史中
    case 'click':
      return `点击(${params.x}, ${params.y})`;
    case 'swipe':
      return '滑动';
    case 'input':
      const text = params.text || '';
      return `输入"${text.length > 10 ? text.slice(0, 10) + '...' : text}"`;
    case 'press':
      return `${params.key}`;
    case 'unlock_screen':
      return `解锁屏幕`;
    default:
      return type;
  }
}

/**
 * 构建 WebSocket URL
 */
export function buildWebSocketUrl(host: string, port: number, udid: string): string {
  return `ws://${host}:${port}/ws/screen/${udid}`;
}
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/types.ts web/apps/web-ele/src/views/device-debug/utils.ts
git commit -m "feat(device-debug): 添加类型定义和工具函数"
```

---

## Task 2: WebSocket 连接管理 Hook

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts`

- [ ] **Step 1: 创建 WebSocket Hook**

```typescript
// web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts

import { onUnmounted, ref } from 'vue';

import type { WebSocketCloseInfo, WebSocketStatus, ScreenSize } from '../types';
import { buildWebSocketUrl } from '../utils';

const MAX_RETRIES = 3;
const RETRY_INTERVAL = 2000; // 2秒

export function useWebSocket() {
  const status = ref<WebSocketStatus>('disconnected');
  const screenshotBase64 = ref('');
  const screenSize = ref<ScreenSize>({ width: 0, height: 0 });
  const fps = ref(0);
  const closeInfo = ref<WebSocketCloseInfo | null>(null);
  const errorMessage = ref('');

  let ws: WebSocket | null = null;
  let retryCount = 0;
  let lastFrameTime = 0;
  let frameCount = 0;
  let fpsTimer: ReturnType<typeof setInterval> | null = null;

  /**
   * 连接 WebSocket
   */
  function connect(host: string, port: number, udid: string): void {
    if (ws) {
      ws.close();
    }

    status.value = 'connecting';
    errorMessage.value = '';
    closeInfo.value = null;

    const url = buildWebSocketUrl(host, port, udid);
    ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      status.value = 'connected';
      retryCount = 0;
      startFpsTimer();
    };

    ws.onmessage = (event) => {
      // event.data 是 ArrayBuffer，JPEG 原始数据
      const arrayBuffer = event.data as ArrayBuffer;
      const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);

      // 释放之前的 URL
      if (screenshotBase64.value && screenshotBase64.value.startsWith('blob:')) {
        URL.revokeObjectURL(screenshotBase64.value);
      }

      screenshotBase64.value = url;

      // 更新帧率计数
      frameCount++;
      lastFrameTime = Date.now();

      // 解析图片尺寸
      const img = new Image();
      img.onload = () => {
        screenSize.value = { width: img.width, height: img.height };
      };
      img.src = url;
    };

    ws.onclose = (event) => {
      stopFpsTimer();
      status.value = 'disconnected';
      closeInfo.value = { code: event.code, reason: event.reason };

      // 非正常关闭时尝试重连
      if (event.code !== 1000 && retryCount < MAX_RETRIES) {
        retryCount++;
        setTimeout(() => {
          if (retryCount <= MAX_RETRIES) {
            connect(host, port, udid);
          }
        }, RETRY_INTERVAL);
      }
    };

    ws.onerror = () => {
      status.value = 'error';
      errorMessage.value = 'WebSocket 连接失败';
    };
  }

  /**
   * 断开连接
   */
  function disconnect(): void {
    if (ws) {
      retryCount = MAX_RETRIES; // 阻止自动重连
      ws.close(1000);
      ws = null;
    }
    stopFpsTimer();
    status.value = 'disconnected';
  }

  /**
   * 重新连接
   */
  function reconnect(host: string, port: number, udid: string): void {
    retryCount = 0;
    connect(host, port, udid);
  }

  /**
   * 开始帧率计算
   */
  function startFpsTimer(): void {
    fpsTimer = setInterval(() => {
      const now = Date.now();
      const elapsed = now - lastFrameTime;
      if (elapsed < 1000) {
        fps.value = Math.round(frameCount * 1000 / elapsed);
      }
      frameCount = 0;
    }, 1000);
  }

  /**
   * 停止帧率计算
   */
  function stopFpsTimer(): void {
    if (fpsTimer) {
      clearInterval(fpsTimer);
      fpsTimer = null;
    }
    fps.value = 0;
  }

  // 组件卸载时断开连接
  onUnmounted(() => {
    disconnect();
    // 释放 blob URL
    if (screenshotBase64.value && screenshotBase64.value.startsWith('blob:')) {
      URL.revokeObjectURL(screenshotBase64.value);
    }
  });

  return {
    status,
    screenshotBase64,
    screenSize,
    fps,
    closeInfo,
    errorMessage,
    connect,
    disconnect,
    reconnect,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/hooks/useWebSocket.ts
git commit -m "feat(device-debug): 添加 WebSocket 连接管理 Hook"
```

---

## Task 3: 屏幕交互 Hook

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/hooks/useScreenInteraction.ts`

- [ ] **Step 1: 创建屏幕交互 Hook**

```typescript
// web/apps/web-ele/src/views/device-debug/hooks/useScreenInteraction.ts

import { ref } from 'vue';
import type { Ref } from 'vue';

import type { ScreenSize } from '../types';
import { convertToDeviceCoords } from '../utils';

export function useScreenInteraction(screenSize: Ref<ScreenSize>) {
  const mouseCoord = ref<{ x: number; y: number } | null>(null);
  const clickIndicator = ref<{ x: number; y: number; show: boolean }>({ x: 0, y: 0, show: false });
  const isDragging = ref(false);
  const dragStart = ref<{ x: number; y: number } | null>(null);
  const dragEnd = ref<{ x: number; y: number } | null>(null);

  /**
   * 获取图片上的坐标（相对于展示区域）
   */
  function getDisplayCoords(event: MouseEvent): { x: number; y: number } {
    const img = event.currentTarget as HTMLImageElement;
    const rect = img.getBoundingClientRect();
    const x = Math.round(event.clientX - rect.left);
    const y = Math.round(event.clientY - rect.top);
    return { x, y };
  }

  /**
   * 获取设备实际坐标
   */
  function getDeviceCoords(event: MouseEvent): { x: number; y: number } {
    const display = getDisplayCoords(event);
    const img = event.currentTarget as HTMLImageElement;
    const rect = img.getBoundingClientRect();

    return convertToDeviceCoords(
      display.x,
      display.y,
      rect.width,
      rect.height,
      screenSize.value.width,
      screenSize.value.height
    );
  }

  /**
   * 拖拽开始
   */
  function handleDragStart(event: MouseEvent): { x: number; y: number } | null {
    event.preventDefault();
    isDragging.value = true;
    const coords = getDeviceCoords(event);
    dragStart.value = coords;
    dragEnd.value = null;
    return coords;
  }

  /**
   * 拖拽移动
   */
  function handleDragMove(event: MouseEvent): { x: number; y: number } | null {
    const coords = getDeviceCoords(event);
    if (isDragging.value) {
      dragEnd.value = coords;
      mouseCoord.value = coords;
    } else {
      mouseCoord.value = coords;
    }
    return coords;
  }

  /**
   * 拖拽结束，判断是点击还是滑动
   */
  function handleDragEnd(event: MouseEvent): {
    type: 'click' | 'swipe';
    params: { x: number; y: number } | { from_x: number; from_y: number; to_x: number; to_y: number };
  } | null {
    if (!isDragging.value || !dragStart.value) return null;

    isDragging.value = false;
    const endCoords = getDeviceCoords(event);

    // 计算滑动距离
    const dx = Math.abs(endCoords.x - dragStart.value.x);
    const dy = Math.abs(endCoords.y - dragStart.value.y);

    // 距离小于 20 像素视为点击
    if (dx < 20 && dy < 20) {
      // 点击操作
      clickIndicator.value = { x: dragStart.value.x, y: dragStart.value.y, show: true };
      setTimeout(() => {
        clickIndicator.value.show = false;
      }, 500);

      const result = {
        type: 'click',
        params: { x: dragStart.value.x, y: dragStart.value.y }
      };
      dragStart.value = null;
      dragEnd.value = null;
      return result;
    } else {
      // 滑动操作
      const result = {
        type: 'swipe',
        params: {
          from_x: dragStart.value.x,
          from_y: dragStart.value.y,
          to_x: endCoords.x,
          to_y: endCoords.y,
          duration: 500
        }
      };
      dragStart.value = null;
      dragEnd.value = null;
      return result;
    }
  }

  /**
   * 鼠标移动显示坐标
   */
  function handleMouseMove(event: MouseEvent): void {
    mouseCoord.value = getDeviceCoords(event);
  }

  /**
   * 鼠标离开
   */
  function handleMouseLeave(): void {
    mouseCoord.value = null;
    if (isDragging.value) {
      isDragging.value = false;
      dragStart.value = null;
      dragEnd.value = null;
    }
  }

  return {
    mouseCoord,
    clickIndicator,
    isDragging,
    dragStart,
    dragEnd,
    getDeviceCoords,
    handleDragStart,
    handleDragMove,
    handleDragEnd,
    handleMouseMove,
    handleMouseLeave,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/hooks/useScreenInteraction.ts
git commit -m "feat(device-debug): 添加屏幕交互 Hook"
```

---

## Task 4: 设备操作 Hook

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/hooks/useDeviceAction.ts`

- [ ] **Step 1: 创建设备操作 Hook**

```typescript
// web/apps/web-ele/src/views/device-debug/hooks/useDeviceAction.ts

import { ref } from 'vue';

import { debugDeviceActionApi } from '#/api/core/env-machine';
import type { OperationRecord } from '../types';
import { formatTime, formatHistoryDisplay } from '../utils';

const OPERATION_TIMEOUT = 20000; // 普通操作超时：20秒
const UNLOCK_TIMEOUT = 30000;    // 解锁操作超时：30秒
const MIN_OPERATION_INTERVAL = 300; // 最小操作间隔

export function useDeviceAction(deviceId: string) {
  const isOperating = ref(false);
  const lastOperationTime = ref(0);
  const operationHistory = ref<OperationRecord[]>([]);

  /**
   * 等待
   */
  function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 添加历史记录
   */
  function addHistory(type: string, params: string, status: 'pending' | 'success' | 'failed'): void {
    operationHistory.value.unshift({
      type,
      params,
      status,
      time: formatTime(),
    });
    if (operationHistory.value.length > 20) {
      operationHistory.value = operationHistory.value.slice(0, 20);
    }
  }

  /**
   * 更新历史记录状态
   */
  function updateHistoryStatus(status: 'success' | 'failed'): void {
    const record = operationHistory.value[0];
    if (record) {
      record.status = status;
    }
  }

  /**
   * 执行操作
   */
  async function executeOperation(
    actionType: string,
    params: Record<string, any>,
    skipRefresh = true, // WebSocket 实时刷新，不需要手动刷新
    isAuto = false
  ): Promise<boolean> {
    // 检查最小间隔
    const now = Date.now();
    const elapsed = now - lastOperationTime.value;
    if (elapsed < MIN_OPERATION_INTERVAL) {
      await sleep(MIN_OPERATION_INTERVAL - elapsed);
    }

    isOperating.value = true;
    lastOperationTime.value = Date.now();

    // 记录操作开始
    if (!isAuto && actionType !== 'screenshot') {
      const displayText = formatHistoryDisplay(actionType, params);
      addHistory(actionType, displayText, 'pending');
    }

    try {
      const timeout = actionType === 'unlock_screen' ? UNLOCK_TIMEOUT : OPERATION_TIMEOUT;

      const result = await debugDeviceActionApi(
        deviceId,
        { action_type: actionType as any, params },
        timeout,
      );

      if (result && result.success) {
        if (!isAuto) {
          updateHistoryStatus('success');
        }
        return true;
      } else {
        const errorMsg = result?.result?.error || '操作失败';
        if (!isAuto) {
          updateHistoryStatus('failed');
        }
        return false;
      }
    } catch (error: any) {
      if (!isAuto) {
        updateHistoryStatus('failed');
      }
      return false;
    } finally {
      isOperating.value = false;
    }
  }

  /**
   * 点击操作
   */
  async function click(x: number, y: number): Promise<boolean> {
    return executeOperation('click', { x, y });
  }

  /**
   * 滑动操作
   */
  async function swipe(fromX: number, fromY: number, toX: number, toY: number, duration = 500): Promise<boolean> {
    return executeOperation('swipe', { from_x: fromX, from_y: fromY, to_x: toX, to_y: toY, duration });
  }

  /**
   * 输入文本
   */
  async function inputText(text: string): Promise<boolean> {
    return executeOperation('input', { x: 0, y: 0, text });
  }

  /**
   * 按键操作
   */
  async function pressKey(key: string): Promise<boolean> {
    return executeOperation('press', { key });
  }

  /**
   * 解锁屏幕
   */
  async function unlockScreen(password?: string): Promise<boolean> {
    return executeOperation('unlock_screen', { value: password || '' });
  }

  return {
    isOperating,
    operationHistory,
    executeOperation,
    click,
    swipe,
    inputText,
    pressKey,
    unlockScreen,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/hooks/useDeviceAction.ts
git commit -m "feat(device-debug): 添加设备操作 Hook"
```

---

## Task 5: 获取设备详情 API

**文件:**
- Modify: `web/apps/web-ele/src/api/core/env-machine.ts`

- [ ] **Step 1: 扩展 EnvMachine 接口添加 Worker 连接字段**

在 `EnvMachine` 接口中添加缺失的字段：

```typescript
export interface EnvMachine {
  id: string;
  namespace: string;
  ip: string;
  port: string;
  mark?: string;
  device_type: string;
  device_sn?: string;
  asset_number?: string;
  available: boolean;
  status: string;
  status_display?: string;
  note?: string;
  extra_message?: Record<string, any>;
  version?: string;
  sync_time?: string;
  last_keepusing_time?: string;
  sort: number;
  is_deleted: boolean;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
  // 新增字段（用于 WebSocket 连接）
  udid?: string;
  worker_host?: string;
  worker_port?: number;
}
```

- [ ] **Step 2: 添加获取单个设备详情 API**

在文件末尾添加：

```typescript
/**
 * 获取单个设备详情
 */
export async function getEnvMachineDetailApi(id: string) {
  return requestClient.get<EnvMachine>(`/api/core/env/${id}`);
}
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/api/core/env-machine.ts
git commit -m "feat(env-machine): 扩展 EnvMachine 接口并添加获取设备详情 API"
```

---

## Task 6: 路由配置

**文件:**
- Create: `web/apps/web-ele/src/router/routes/modules/device-debug.ts`

- [ ] **Step 1: 创建路由配置**

```typescript
// web/apps/web-ele/src/router/routes/modules/device-debug.ts

import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/device-debug/:deviceId',
    name: 'DeviceDebug',
    component: () => import('#/views/device-debug/index.vue'),
    meta: {
      title: '设备调试',
      hideInMenu: true,
    },
  },
];

export default routes;
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/router/routes/modules/device-debug.ts
git commit -m "feat(device-debug): 添加设备调试页面路由"
```

---

## Task 7: 顶部导航栏组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/TopNavbar.vue`

- [ ] **Step 1: 创建顶部导航栏组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/TopNavbar.vue -->

<script lang="ts" setup>
import type { WebSocketStatus } from '../types';
import { isDesktopDevice } from '../utils';

import { computed } from 'vue';

import { ElButton, ElTag } from 'element-plus';

interface Props {
  deviceType: string;
  assetNumber: string;
  deviceSn?: string;
  wsStatus: WebSocketStatus;
  fps: number;
}

interface Emits {
  (e: 'back'): void;
  (e: 'disconnect'): void;
  (e: 'reconnect'): void;
  (e: 'fullscreen'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isDesktop = computed(() => isDesktopDevice(props.deviceType));

const wsStatusDisplay = computed(() => {
  switch (props.wsStatus) {
    case 'connecting':
      return { text: '连接中', type: 'warning' };
    case 'connected':
      return { text: '已连接', type: 'success' };
    case 'disconnected':
      return { text: '已断开', type: 'info' };
    case 'error':
      return { text: '连接错误', type: 'danger' };
    default:
      return { text: '未知', type: 'info' };
  }
});

function handleBack() {
  emit('back');
}

function handleDisconnect() {
  emit('disconnect');
}

function handleReconnect() {
  emit('reconnect');
}

function handleFullscreen() {
  emit('fullscreen');
}
</script>

<template>
  <div class="top-navbar">
    <!-- 设备信息 -->
    <div class="navbar-left">
      <ElButton size="small" @click="handleBack">
        返回
      </ElButton>
      <span class="device-icon">{{ isDesktop ? '💻' : '📱' }}</span>
      <span class="device-name">{{ assetNumber }}</span>
      <span v-if="deviceSn" class="device-sn">| {{ deviceSn }}</span>
      <ElTag type="success" size="small">在线</ElTag>
    </div>

    <!-- 连接状态和操作 -->
    <div class="navbar-right">
      <ElTag :type="wsStatusDisplay.type" size="small">
        {{ wsStatusDisplay.text }}
      </ElTag>
      <span v-if="fps > 0" class="fps-display">{{ fps }} fps</span>
      <ElButton v-if="isDesktop" size="small" @click="handleFullscreen">
        全屏
      </ElButton>
      <ElButton
        v-if="wsStatus === 'connected'"
        size="small"
        type="danger"
        @click="handleDisconnect"
      >
        断开
      </ElButton>
      <ElButton
        v-if="wsStatus === 'disconnected' || wsStatus === 'error'"
        size="small"
        type="primary"
        @click="handleReconnect"
      >
        重连
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.top-navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  height: 56px;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-icon {
  font-size: 18px;
}

.device-name {
  font-size: 16px;
  font-weight: 600;
  color: #111;
}

.device-sn {
  font-size: 14px;
  color: #666;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fps-display {
  font-size: 12px;
  color: #666;
  padding: 2px 8px;
  background: #f5f5f5;
  border-radius: 4px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/TopNavbar.vue
git commit -m "feat(device-debug): 添加顶部导航栏组件"
```

---

## Task 8: 底部工具栏组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/BottomToolbar.vue`

- [ ] **Step 1: 创建底部工具栏组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/BottomToolbar.vue -->

<script lang="ts" setup>
import type { OperationRecord } from '../types';
import { isDesktopDevice } from '../utils';

import { computed } from 'vue';

import { ElButton } from 'element-plus';

interface Props {
  deviceType: string;
  operationHistory: OperationRecord[];
  clickCount: number;
  swipeCount: number;
}

interface Emits {
  (e: 'keypress'): void;
  (e: 'input'): void;
  (e: 'install'): void;
  (e: 'screenshot'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isDesktop = computed(() => isDesktopDevice(props.deviceType));

function handleKeyPress() {
  emit('keypress');
}

function handleInput() {
  emit('input');
}

function handleInstall() {
  emit('install');
}

function handleScreenshot() {
  emit('screenshot');
}
</script>

<template>
  <div class="bottom-toolbar">
    <!-- 左侧操作按钮 -->
    <div class="toolbar-left">
      <ElButton size="small" @click="handleKeyPress">
        按键操作
      </ElButton>
      <ElButton v-if="isDesktop" size="small" @click="handleInput">
        输入文本
      </ElButton>
      <ElButton size="small" @click="handleInstall">
        安装 APP
      </ElButton>
    </div>

    <!-- 右侧截图和统计 -->
    <div class="toolbar-right">
      <ElButton size="small" type="primary" @click="handleScreenshot">
        截图保存
      </ElButton>
      <span class="stats-display">
        点击: {{ clickCount }} | 滑动: {{ swipeCount }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.bottom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  height: 56px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stats-display {
  font-size: 12px;
  color: #666;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/BottomToolbar.vue
git commit -m "feat(device-debug): 添加底部工具栏组件"
```

---

## Task 9: 屏幕展示组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/ScreenDisplay.vue`

- [ ] **Step 1: 创建屏幕展示组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/ScreenDisplay.vue -->

<script lang="ts" setup>
import type { WebSocketStatus, ScreenSize, OperationRecord } from '../types';

import { computed } from 'vue';

interface Props {
  screenshotUrl: string;
  screenSize: ScreenSize;
  wsStatus: WebSocketStatus;
  mouseCoord: { x: number; y: number } | null;
  clickIndicator: { x: number; y: number; show: boolean };
  isDragging: boolean;
  dragStart: { x: number; y: number } | null;
  dragEnd: { x: number; y: number } | null;
}

interface Emits {
  (e: 'mousedown', event: MouseEvent): void;
  (e: 'mousemove', event: MouseEvent): void;
  (e: 'mouseup', event: MouseEvent): void;
  (e: 'mouseleave'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const isConnected = computed(() => props.wsStatus === 'connected');

function handleMouseDown(event: MouseEvent) {
  emit('mousedown', event);
}

function handleMouseMove(event: MouseEvent) {
  emit('mousemove', event);
}

function handleMouseUp(event: MouseEvent) {
  emit('mouseup', event);
}

function handleMouseLeave() {
  emit('mouseleave');
}

// 计算指示器位置百分比
function getIndicatorPercent(coord: number, size: number): string {
  if (size === 0) return '0%';
  return `${(coord / size) * 100}%`;
}
</script>

<template>
  <div class="screen-display">
    <!-- LIVE 标识 -->
    <div v-if="isConnected" class="live-badge live-active">
      LIVE
    </div>
    <div v-else class="live-badge live-inactive">
      LIVE
    </div>

    <!-- 坐标显示 -->
    <div v-if="mouseCoord" class="coord-display">
      X: {{ mouseCoord.x }}, Y: {{ mouseCoord.y }}
    </div>

    <!-- 断开提示 -->
    <div v-if="wsStatus === 'disconnected'" class="disconnect-banner">
      连接已断开
    </div>

    <!-- 屏幕区域 -->
    <div class="screen-wrapper">
      <img
        v-if="screenshotUrl"
        :src="screenshotUrl"
        class="screen-img"
        draggable="false"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseLeave"
      />
      <div v-else class="screen-placeholder">
        <span v-if="wsStatus === 'connecting'">连接中...</span>
        <span v-else>暂无画面</span>
      </div>

      <!-- 点击指示器 -->
      <div
        v-if="clickIndicator.show"
        class="click-indicator"
        :style="{
          left: getIndicatorPercent(clickIndicator.x, screenSize.width),
          top: getIndicatorPercent(clickIndicator.y, screenSize.height),
        }"
      />

      <!-- 拖拽轨迹 -->
      <div
        v-if="isDragging && dragStart && dragEnd"
        class="drag-track"
      >
        <div
          class="drag-point drag-start"
          :style="{
            left: getIndicatorPercent(dragStart.x, screenSize.width),
            top: getIndicatorPercent(dragStart.y, screenSize.height),
          }"
        />
        <div
          class="drag-point drag-end"
          :style="{
            left: getIndicatorPercent(dragEnd.x, screenSize.width),
            top: getIndicatorPercent(dragEnd.y, screenSize.height),
          }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.screen-display {
  position: relative;
  width: 100%;
  height: 100%;
  background: #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
}

.live-active {
  background: #22c55e;
  color: #fff;
}

.live-inactive {
  background: #d4d4d4;
  color: #666;
}

.coord-display {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 4px;
}

.disconnect-banner {
  position: absolute;
  top: 50px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 8px 24px;
  font-size: 14px;
  border-radius: 8px;
}

.screen-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.screen-img {
  max-width: 100%;
  max-height: 100%;
  cursor: crosshair;
}

.screen-placeholder {
  color: #666;
  font-size: 14px;
}

.click-indicator {
  position: absolute;
  width: 32px;
  height: 32px;
  background: rgba(24, 144, 255, 0.8);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  animation: clickPulse 0.5s ease-out;
}

@keyframes clickPulse {
  0% {
    transform: translate(-50%, -50%) scale(0);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0;
  }
}

.drag-track {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.drag-point {
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  border: 3px solid #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
}

.drag-start {
  background: #22c55e;
}

.drag-end {
  background: #ef4444;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/ScreenDisplay.vue
git commit -m "feat(device-debug): 添加屏幕展示组件"
```

---

## Task 10: 移动端右侧面板组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/MobilePanel.vue`

- [ ] **Step 1: 创建移动端右侧面板组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/MobilePanel.vue -->

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

const props = defineProps<Props>();
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
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/MobilePanel.vue
git commit -m "feat(device-debug): 添加移动端右侧面板组件"
```

---

## Task 11: 解锁屏幕弹窗组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/UnlockDialog.vue`

- [ ] **Step 1: 创建解锁屏幕弹窗组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/UnlockDialog.vue -->

<script lang="ts" setup>
import { ref, computed } from 'vue';

import { ElDialog, ElInput, ElButton } from 'element-plus';

interface Props {
  visible: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', password?: string): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const password = ref('');

function handleConfirm() {
  emit('confirm', password.value);
  password.value = '';
}

function handleCancel() {
  password.value = '';
  dialogVisible.value = false;
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    title="解锁屏幕"
    width="400px"
    :close-on-click-modal="false"
  >
    <div class="unlock-content">
      <div class="unlock-tip">
        如果设备无密码锁，可直接解锁
      </div>
      <ElInput
        v-model="password"
        placeholder="输入解锁密码（可选）"
        type="password"
        show-password
      />
    </div>
    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton type="primary" @click="handleConfirm">确认解锁</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.unlock-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.unlock-tip {
  font-size: 12px;
  color: #666;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/UnlockDialog.vue
git commit -m "feat(device-debug): 添加解锁屏幕弹窗组件"
```

---

## Task 12: 安装 APP 弹窗组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/InstallAppDialog.vue`

- [ ] **Step 1: 创建安装 APP 弹窗组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/InstallAppDialog.vue -->

<script lang="ts" setup>
import { ref, computed } from 'vue';

import { ElDialog, ElButton, ElMessage, ElProgress } from 'element-plus';

interface Props {
  visible: boolean;
  deviceType: string;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'upload', file: File): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const selectedFile = ref<File | null>(null);
const isUploading = ref(false);
const uploadProgress = ref(0);

const allowedExtensions = computed(() => {
  switch (props.deviceType) {
    case 'android':
      return '.apk';
    case 'ios':
      return '.ipa';
    case 'windows':
      return '.exe';
    case 'mac':
      return '.dmg, .pkg';
    default:
      return '';
  }
});

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
  }
}

function handleDrop(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    selectedFile.value = event.dataTransfer.files[0];
  }
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择安装包文件');
    return;
  }

  isUploading.value = true;
  uploadProgress.value = 0;

  // 模拟上传进度（实际需要调用后端 API）
  emit('upload', selectedFile.value);

  // 清理状态
  selectedFile.value = null;
  isUploading.value = false;
  uploadProgress.value = 0;
  dialogVisible.value = false;
}

function handleCancel() {
  selectedFile.value = null;
  dialogVisible.value = false;
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    title="安装 APP"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="install-content">
      <!-- 文件上传区域 -->
      <div
        class="upload-area"
        @drop="handleDrop"
        @dragover.prevent
      >
        <div class="upload-icon">📦</div>
        <div class="upload-text">
          拖拽文件到此处，或点击选择
        </div>
        <input
          type="file"
          :accept="allowedExtensions"
          class="file-input"
          @change="handleFileSelect"
        />
      </div>

      <!-- 已选文件 -->
      <div v-if="selectedFile" class="selected-file">
        <span class="file-name">{{ selectedFile.name }}</span>
        <span class="file-size">{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB</span>
      </div>

      <!-- 支持格式提示 -->
      <div class="format-tip">
        支持格式: {{ allowedExtensions }}
      </div>

      <!-- 上传进度 -->
      <ElProgress v-if="isUploading" :percentage="uploadProgress" />
    </div>

    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton
        type="primary"
        :disabled="!selectedFile || isUploading"
        @click="handleUpload"
      >
        上传并安装
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.install-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s;
}

.upload-area:hover {
  border-color: #3b82f6;
}

.upload-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.upload-text {
  font-size: 14px;
  color: #666;
}

.file-input {
  display: none;
}

.selected-file {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.file-name {
  font-size: 14px;
  color: #111;
}

.file-size {
  font-size: 12px;
  color: #666;
}

.format-tip {
  font-size: 12px;
  color: #999;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/InstallAppDialog.vue
git commit -m "feat(device-debug): 添加安装 APP 弹窗组件"
```

---

## Task 13: 输入文本弹窗组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/components/InputTextDialog.vue`

- [ ] **Step 1: 创建输入文本弹窗组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/components/InputTextDialog.vue -->

<script lang="ts" setup>
import { ref, computed } from 'vue';

import { ElDialog, ElInput, ElButton, ElMessage } from 'element-plus';

interface Props {
  visible: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'send', text: string): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const textValue = ref('');

function handleSend() {
  if (!textValue.value.trim()) {
    ElMessage.warning('请输入文本内容');
    return;
  }
  emit('send', textValue.value);
  textValue.value = '';
}

function handleCancel() {
  textValue.value = '';
  dialogVisible.value = false;
}
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    title="输入文本"
    width="400px"
    :close-on-click-modal="false"
  >
    <ElInput
      v-model="textValue"
      placeholder="输入要发送的文本..."
      type="textarea"
      :rows="4"
    />
    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton type="primary" :disabled="!textValue.trim()" @click="handleSend">
        发送
      </ElButton>
    </template>
  </ElDialog>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/InputTextDialog.vue
git commit -m "feat(device-debug): 添加输入文本弹窗组件"
```

---

## Task 14: 按键操作弹窗组件（复用现有）

**文件:**
- Copy: `web/apps/web-ele/src/views/env-machine/modules/KeyPressDialog.vue`
- To: `web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue`

- [ ] **Step 1: 使用 Read 工具读取现有组件内容**

使用 Read 工具读取以下文件：
- `web/apps/web-ele/src/views/env-machine/modules/KeyPressDialog.vue`

- [ ] **Step 2: 复制内容到新位置并调整导入路径**

使用 Write 工具将读取的内容写入新位置：
`web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue`

需要修改的导入路径：
- 移除 `import type { EnvMachine } from '#/api/core/env-machine';`（该组件不再需要）
- 将 `import type { DeviceType } from '../types'` 改为 `import type { DeviceType } from '../types'`（相对路径保持不变）

确保 Task 1 的 types.ts 包含 `DeviceType` 类型定义。

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/components/KeyPressDialog.vue
git commit -m "feat(device-debug): 复用按键操作弹窗组件"
```

---

## Task 15: 主页面入口组件

**文件:**
- Create: `web/apps/web-ele/src/views/device-debug/index.vue`

- [ ] **Step 1: 创建主页面组件**

```vue
<!-- web/apps/web-ele/src/views/device-debug/index.vue -->

<script lang="ts" setup>
import { onMounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ElMessage } from 'element-plus';

import { getEnvMachineDetailApi } from '#/api/core/env-machine';

import { isDesktopDevice, isMobileDevice } from './utils';
import { useWebSocket } from './hooks/useWebSocket';
import { useScreenInteraction } from './hooks/useScreenInteraction';
import { useDeviceAction } from './hooks/useDeviceAction';

import TopNavbar from './components/TopNavbar.vue';
import BottomToolbar from './components/BottomToolbar.vue';
import ScreenDisplay from './components/ScreenDisplay.vue';
import MobilePanel from './components/MobilePanel.vue';
import KeyPressDialog from './components/KeyPressDialog.vue';
import InputTextDialog from './components/InputTextDialog.vue';
import UnlockDialog from './components/UnlockDialog.vue';
import InstallAppDialog from './components/InstallAppDialog.vue';

const route = useRoute();
const router = useRouter();

const deviceId = route.params.deviceId as string;

// 设备详情
const deviceDetail = ref<any>(null);
const loading = ref(true);

// WebSocket
const {
  status: wsStatus,
  screenshotBase64,
  screenSize,
  fps,
  connect,
  disconnect,
  reconnect,
} = useWebSocket();

// 屏幕交互
const {
  mouseCoord,
  clickIndicator,
  isDragging,
  dragStart,
  dragEnd,
  handleDragStart,
  handleDragMove,
  handleDragEnd,
  handleMouseMove,
  handleMouseLeave,
} = useScreenInteraction(screenSize);

// 设备操作
const {
  isOperating,
  operationHistory,
  click,
  swipe,
  inputText,
  pressKey,
  unlockScreen,
} = useDeviceAction(deviceId);

// 操作统计
const clickCount = ref(0);
const swipeCount = ref(0);

// 弹窗状态
const keyPressDialogVisible = ref(false);
const inputTextDialogVisible = ref(false);
const unlockDialogVisible = ref(false);
const installAppDialogVisible = ref(false);

// 全屏状态
const isFullscreen = ref(false);

// 设备类型判断
const isDesktop = computed(() => deviceDetail.value && isDesktopDevice(deviceDetail.value.device_type));
const isMobile = computed(() => deviceDetail.value && isMobileDevice(deviceDetail.value.device_type));

// 加载设备详情
async function loadDeviceDetail() {
  try {
    loading.value = true;
    const result = await getEnvMachineDetailApi(deviceId);
    deviceDetail.value = result;

    // 连接 WebSocket
    if (result.worker_host && result.worker_port && result.udid) {
      connect(result.worker_host, result.worker_port, result.udid);
    } else {
      ElMessage.error('设备缺少 Worker 连接信息');
    }
  } catch (error: any) {
    ElMessage.error('获取设备详情失败: ' + error.message);
  } finally {
    loading.value = false;
  }
}

// 返回上一页
function handleBack() {
  disconnect();
  router.back();
}

// 断开连接
function handleDisconnect() {
  disconnect();
}

// 重新连接
function handleReconnect() {
  if (deviceDetail.value?.worker_host && deviceDetail.value?.worker_port && deviceDetail.value?.udid) {
    reconnect(deviceDetail.value.worker_host, deviceDetail.value.worker_port, deviceDetail.value.udid);
  }
}

// 全屏切换
function handleFullscreen() {
  isFullscreen.value = !isFullscreen.value;
  // 实际全屏切换逻辑可通过 document fullscreen API 实现
}

// 屏幕交互事件处理
function handleScreenMouseDown(event: MouseEvent) {
  if (isOperating.value || wsStatus.value !== 'connected') return;
  handleDragStart(event);
}

function handleScreenMouseMove(event: MouseEvent) {
  handleDragMove(event);
}

async function handleScreenMouseUp(event: MouseEvent) {
  if (isOperating.value) return;
  const result = handleDragEnd(event);
  if (result) {
    if (result.type === 'click') {
      const success = await click(result.params.x, result.params.y);
      if (success) clickCount.value++;
    } else if (result.type === 'swipe') {
      const success = await swipe(
        result.params.from_x,
        result.params.from_y,
        result.params.to_x,
        result.params.to_y
      );
      if (success) swipeCount.value++;
    }
  }
}

function handleScreenMouseLeave() {
  handleMouseLeave();
}

// 按键操作
function handleKeyPress(key: string) {
  pressKey(key);
}

// 输入文本
function handleInputText(text: string) {
  inputText(text);
}

// 解锁屏幕
function handleUnlock(password?: string) {
  unlockScreen(password);
}

// 安装 APP
function handleInstallApp(file: File) {
  // TODO: 实现上传安装逻辑（后端 API 待实现）
  ElMessage.info('APP 安装功能待后端支持');
}

// 截图保存
function handleScreenshot() {
  if (screenshotBase64.value) {
    const link = document.createElement('a');
    link.href = screenshotBase64.value;
    link.download = `screenshot_${Date.now()}.png`;
    link.click();
  } else {
    ElMessage.warning('暂无截图可保存');
  }
}

// 打开按键弹窗
function handleOpenKeyPressDialog() {
  keyPressDialogVisible.value = true;
}

// 打开输入文本弹窗
function handleOpenInputDialog() {
  inputTextDialogVisible.value = true;
}

// 打开解锁弹窗
function handleOpenUnlockDialog() {
  unlockDialogVisible.value = true;
}

// 打开安装弹窗
function handleOpenInstallDialog() {
  installAppDialogVisible.value = true;
}

onMounted(() => {
  loadDeviceDetail();
});
</script>

<template>
  <div class="device-debug-page" :class="{ fullscreen: isFullscreen }">
    <!-- 顶部导航栏 -->
    <TopNavbar
      v-if="deviceDetail"
      :device-type="deviceDetail.device_type"
      :asset-number="deviceDetail.asset_number || deviceDetail.ip"
      :device-sn="deviceDetail.device_sn"
      :ws-status="wsStatus"
      :fps="fps"
      @back="handleBack"
      @disconnect="handleDisconnect"
      @reconnect="handleReconnect"
      @fullscreen="handleFullscreen"
    />

    <!-- 主内容区 -->
    <div class="debug-content">
      <!-- 桌面端布局：单屏幕展示 -->
      <template v-if="isDesktop">
        <ScreenDisplay
          :screenshot-url="screenshotBase64"
          :screen-size="screenSize"
          :ws-status="wsStatus"
          :mouse-coord="mouseCoord"
          :click-indicator="clickIndicator"
          :is-dragging="isDragging"
          :drag-start="dragStart"
          :drag-end="dragEnd"
          @mousedown="handleScreenMouseDown"
          @mousemove="handleScreenMouseMove"
          @mouseup="handleScreenMouseUp"
          @mouseleave="handleScreenMouseLeave"
        />
      </template>

      <!-- 移动端布局：左侧屏幕 + 右侧面板 -->
      <template v-if="isMobile">
        <div class="mobile-layout">
          <div class="mobile-screen">
            <ScreenDisplay
              :screenshot-url="screenshotBase64"
              :screen-size="screenSize"
              :ws-status="wsStatus"
              :mouse-coord="mouseCoord"
              :click-indicator="clickIndicator"
              :is-dragging="isDragging"
              :drag-start="dragStart"
              :drag-end="dragEnd"
              @mousedown="handleScreenMouseDown"
              @mousemove="handleScreenMouseMove"
              @mouseup="handleScreenMouseUp"
              @mouseleave="handleScreenMouseLeave"
            />
          </div>
          <div class="mobile-right">
            <MobilePanel
              :operation-history="operationHistory"
              :udid="deviceDetail?.udid"
              @keypress="handleKeyPress"
              @input="handleInputText"
              @unlock="handleUnlock"
              @install="handleOpenInstallDialog"
              @screenshot="handleScreenshot"
            />
          </div>
        </div>
      </template>
    </div>

    <!-- 底部工具栏（桌面端） -->
    <BottomToolbar
      v-if="isDesktop"
      :device-type="deviceDetail?.device_type"
      :operation-history="operationHistory"
      :click-count="clickCount"
      :swipe-count="swipeCount"
      @keypress="handleOpenKeyPressDialog"
      @input="handleOpenInputDialog"
      @install="handleOpenInstallDialog"
      @screenshot="handleScreenshot"
    />

    <!-- 弹窗组件 -->
    <KeyPressDialog
      v-model:visible="keyPressDialogVisible"
      :disabled="isOperating"
      :device-type="deviceDetail?.device_type"
      @press="handleKeyPress"
    />

    <InputTextDialog
      v-model:visible="inputTextDialogVisible"
      @send="handleInputText"
    />

    <UnlockDialog
      v-model:visible="unlockDialogVisible"
      @confirm="handleUnlock"
    />

    <InstallAppDialog
      v-model:visible="installAppDialogVisible"
      :device-type="deviceDetail?.device_type"
      @upload="handleInstallApp"
    />
  </div>
</template>

<style scoped>
.device-debug-page {
  background: #f0f2f5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.device-debug-page.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 100;
}

.debug-content {
  flex: 1;
  display: flex;
  padding: 16px;
}

/* 桌面端布局 */
.debug-content:not(.mobile-layout) {
  height: calc(100vh - 112px); /* 56px navbar + 56px toolbar */
}

/* 移动端布局 */
.mobile-layout {
  display: flex;
  gap: 16px;
  height: 100%;
}

.mobile-screen {
  flex: 1;
  max-width: 340px;
  min-width: 300px;
}

.mobile-right {
  width: 280px;
  flex-shrink: 0;
}
</style>
```

注：TopNavbar 需要添加 slot 支持，或者将返回按钮直接放在页面顶部。上述代码已简化处理。

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/device-debug/index.vue
git commit -m "feat(device-debug): 添加主页面入口组件"
```

---

## Task 16: 修改设备列表页面跳转

**文件:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 添加跳转逻辑**

找到调试按钮的点击事件处理函数，修改为跳转到独立页面：

```typescript
// 原来的弹窗方式
// function handleDebug(row: EnvMachine) {
//   debugDialogVisible.value = true;
//   currentMachine.value = row;
// }

// 新的独立页面方式
import { useRouter } from 'vue-router';

const router = useRouter();

function handleDebug(row: EnvMachine) {
  router.push(`/device-debug/${row.id}`);
}
```

同时移除 DebugDialog 组件的引入和使用。

- [ ] **Step 2: 验证跳转**

启动开发服务器，访问设备列表页面，点击调试按钮，验证能正确跳转到 `/device-debug/{deviceId}` 页面。

```bash
cd web && pnpm dev
```

- [ ] **Step 3: Commit**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat(env-machine): 调试按钮跳转到独立页面"
```

---

## Task 17: 最终验收

- [ ] **Step 1: 启动开发服务器**

```bash
cd web && pnpm dev
```

- [ ] **Step 2: 功能验收清单**

| 功能 | Windows/Mac | 移动端 | 验收状态 |
|------|-------------|--------|----------|
| WebSocket 连接 | ☐ | ☐ | |
| 实时屏幕显示 | ☐ | ☐ | |
| LIVE 标识 | ☐ | ☐ | |
| 坐标显示 | ☐ | ☐ | |
| 点击操作 | ☐ | ☐ | |
| 滑动操作 | ☐ | ☐ | |
| 按键操作弹窗 | ☐ | ☐ | |
| 文本输入弹窗 | ☐ | - | |
| 文本输入面板 | - | ☐ | |
| 截图保存 | ☐ | ☐ | |
| 解锁屏幕弹窗 | - | ☐ | |
| 安装 APP 弹窗 | ☐ | ☐ | |
| 断开/重连 | ☐ | ☐ | |
| 全屏按钮 | ☐ | ☐ | |
| 返回按钮 | ☐ | ☐ | |

- [ ] **Step 3: UI 验收清单**

| 检查项 | Windows/Mac | 移动端 | 验收状态 |
|--------|-------------|--------|----------|
| 页面背景 #f0f2f5 | ☐ | ☐ | |
| 白色卡片风格 | ☐ | ☐ | |
| 屏幕展示区黑色背景 | ☐ | ☐ | |
| 连接状态正确显示 | ☐ | ☐ | |
| fps 显示 | ☐ | ☐ | |
| 操作历史显示 | - | ☐ | |

- [ ] **Step 4: Final Commit**

```bash
git add -A
git commit -m "feat(device-debug): 设备调试实时屏幕推流功能完成

- WebSocket 实时屏幕推流（约 10 fps）
- 点击/滑动直接在屏幕操作
- 按键/输入/安装弹窗
- 截图保存功能
- Windows/Mac 大屏布局
- 移动端左侧屏幕+右侧面板布局

设计文档: docs/superpowers/specs/2026-04-22-device-debug-realtime-screen-design.md"
```

---

## 验收标准

1. ✅ WebSocket 实时连接成功
2. ✅ 屏幕画面实时显示（约 10 fps）
3. ✅ 点击操作正确执行
4. ✅ 滑动操作正确执行
5. ✅ 按键/输入/安装弹窗正常工作
6. ✅ 截图保存功能正常
7. ✅ Windows/Mac 大屏布局
8. ✅ 移动端左侧屏幕 + 右侧面板布局
9. ✅ UI 符合设计文档要求（白色背景风格）
10. ✅ 设备列表跳转正确

---

## 后端待支持功能

以下功能前端 UI 已实现，后端 API 待 Worker 支持：

1. **解锁屏幕密码**: 需要 Worker 实现带密码的解锁接口
2. **安装 APP**: 需要 Worker 实现 APP 上传和安装接口

---

**计划日期**: 2026-04-23
**计划状态**: 待审核