<script lang="ts" setup>
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  useTemplateRef,
  watch,
} from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useTabs } from '@vben/hooks';

import { ElMessage } from 'element-plus';

import { getEnvMachineDetailApi } from '#/api/core/env-machine';

import InputTextDialog from './components/InputTextDialog.vue';
import KeyPressDialog from './components/KeyPressDialog.vue';
import MobilePanel from './components/MobilePanel.vue';
import ScreenDisplay from './components/ScreenDisplay.vue';
import TopNavbar from './components/TopNavbar.vue';
import UnlockDialog from './components/UnlockDialog.vue';
import { useDeviceAction } from './hooks/useDeviceAction';
import { useScreenInteraction } from './hooks/useScreenInteraction';
import { useWebSocket } from './hooks/useWebSocket';
import {
  calculateContainRenderArea,
  convertToDeviceCoords,
  formatDeviceDebugTitle,
  isDesktopDevice,
  isMobileDevice,
} from './utils';

const KEYBOARD_TEXT_FLUSH_DELAY_MS = 250;

const route = useRoute();
const router = useRouter();
const isRemotePopup = route.query.remotePopup === '1';
const { setTabTitle } = useTabs();

const deviceId = route.params.deviceId as string;

// 设备详情
const deviceDetail = ref<any>(null);
const loading = ref(true);

// 导航栏固定状态
const navbarFixed = ref(false);

// 当前使用的编码格式（Windows、鸿蒙移动和鸿蒙 PC 走 H.264；H.264 失败后内部自动降级为 JPEG）
const currentCodec = computed(() => {
  if (
    ['harmony_mobile', 'harmony_pc', 'windows'].includes(
      deviceDetail.value?.device_type ?? '',
    )
  ) {
    return 'h264';
  }
  return 'jpeg';
});

// WebSocket
const {
  status: wsStatus,
  userDisconnected,
  waitingUnlock,
  hasReceivedFrame,
  screenshotBase64,
  screenSize,
  fps,
  videoMode,
  realtimeInput,
  connect,
  disconnect,
  reconnect,
  resetActivityTime,
  attachVideoEl,
  sendInput,
} = useWebSocket();

// ScreenDisplay 组件实例引用：用于取出内部暴露的 <video> 元素并绑定给 MSE 解码器。
// 桌面端和移动端各用一个 ScreenDisplay，通过 useTemplateRef 按顺序绑定。
const desktopScreenRef =
  useTemplateRef<InstanceType<typeof ScreenDisplay>>('desktopScreen');
const mobileScreenRef =
  useTemplateRef<InstanceType<typeof ScreenDisplay>>('mobileScreen');

// 监听 videoMode 变化，在进入 H264 模式时把对应 ScreenDisplay 的 <video> 绑定给解码器。
// 实际依赖父组件重渲染后 ref 已就绪，故用 nextTick + watchEffect。
// 这里采用简单做法：connect 后由 ScreenDisplay 渲染 <video>，在其 ref 就绪后绑定。
watch(
  videoMode,
  async (_mode) => {
    await nextTick();
    const targetRef = desktopScreenRef.value || mobileScreenRef.value;
    const el = targetRef?.videoRef ?? null;
    attachVideoEl(el);
  },
  { immediate: true },
);

// 屏幕交互：realtime 路径（worker 声明能力时，down/move/up 逐事件走 WS）+
// legacy 路径（mouseup 合成 click/swipe 走 REST）双轨并存
const {
  mouseCoord,
  isInScreen,
  clickIndicator,
  isDragging,
  dragStart,
  dragEnd,
  handleDragStart,
  handleDragMove,
  handleDragEnd,
  // handleMouseMove - 未使用，保留备用
  handleMouseLeave,
  rtPointerDown,
  rtPointerMove,
  rtPointerUp,
  rtPointerCancel,
  rtWheel,
  rtContextMenu,
  rtPointerLeave,
} = useScreenInteraction(screenSize, {
  sendInput,
  realtimeInput,
  isPcDevice: computed(() =>
    ['harmony_pc', 'mac', 'windows'].includes(
      deviceDetail.value?.device_type ?? '',
    ),
  ),
});

// 设备操作
const {
  isOperating,
  operationHistory,
  click,
  rightClick,
  swipe,
  inputText,
  pasteText,
  pressKey,
  unlockScreen,
  screenshot,
  releaseSession,
} = useDeviceAction(deviceId);

// 操作统计
const clickCount = ref(0);
const swipeCount = ref(0);

// 弹窗状态
const keyPressDialogVisible = ref(false);
const inputTextDialogVisible = ref(false);
const unlockDialogVisible = ref(false);
const isUnlocking = ref(false);
const unlockCompletedWaitingFrame = ref(false);
const keyboardCaptureRef = ref<HTMLTextAreaElement | null>(null);
const keyboardCaptureActive = ref(false);
let keyboardTextBuffer = '';
let keyboardFlushTimer: null | ReturnType<typeof setTimeout> = null;
let keyboardActionQueue: Promise<void> = Promise.resolve();
let remotePageDisposed = false;
const pressedKeyboardModifiers = new Set<'ctrl' | 'alt' | 'shift' | 'meta'>();
const modifierKeyMap: Record<string, 'ctrl' | 'alt' | 'shift' | 'meta'> = {
  Alt: 'alt',
  Control: 'ctrl',
  Meta: 'meta',
  Shift: 'shift',
};

// 屏幕选择
const currentScreenIndex = ref(0);
const screenCount = computed(() => {
  if (!deviceDetail.value || !isDesktop.value) return 1;
  // 鸿蒙 PC 投屏视作单屏，隐藏多屏切换
  if (deviceDetail.value.device_type === 'harmony_pc') return 1;
  const extra = deviceDetail.value.extra_message;
  // 从设备扩展信息获取屏幕数量
  if (extra?.screen_count) return extra.screen_count;
  if (extra?.monitor_count) return extra.monitor_count;
  // 桌面端设备默认支持多屏幕选择（显示2个选项）
  return 2;
});

// 设备类型判断
const isDesktop = computed(
  () => deviceDetail.value && isDesktopDevice(deviceDetail.value.device_type),
);
const isMobile = computed(
  () => deviceDetail.value && isMobileDevice(deviceDetail.value.device_type),
);
const isHarmony = computed(
  () =>
    deviceDetail.value?.device_type === 'harmony_mobile' ||
    deviceDetail.value?.device_type === 'harmony_pc',
);
const isHarmonyPc = computed(
  () => deviceDetail.value?.device_type === 'harmony_pc',
);
const isWindowsDevice = computed(
  () => deviceDetail.value?.device_type === 'windows',
);
const isNativeKeyboardDevice = computed(() =>
  ['windows', 'harmony_pc'].includes(deviceDetail.value?.device_type ?? ''),
);
// 鸿蒙 WS 推流失败后的手动截图兜底（refreshHarmonyScreenshot 填充）
const harmonyScreenshotUrl = ref('');
const displayedWsStatus = computed(() => {
  // 截图兜底只保持最后画面，不掩盖真实 WebSocket 状态，确保断开后
  // 顶部能显示“已断开”并提供“重连”按钮。
  return wsStatus.value;
});
// 屏幕显示源：WS 帧优先，鸿蒙降级截图兜底
const displayedScreenshotUrl = computed(
  () => screenshotBase64.value || harmonyScreenshotUrl.value,
);
const hasDisplayedFrame = computed(
  () =>
    hasReceivedFrame.value ||
    Boolean(screenshotBase64.value) ||
    Boolean(harmonyScreenshotUrl.value),
);
const streamHint = computed(() => {
  if (hasDisplayedFrame.value) return '';
  if (isUnlocking.value) return '正在执行解锁操作，完成后会自动恢复远程画面';
  if (unlockCompletedWaitingFrame.value)
    return '解锁操作已完成，正在等待设备画面恢复';
  if (waitingUnlock.value)
    return '设备当前处于锁屏状态，请点击顶部“解锁屏幕”；解锁后画面会自动开始推流';
  if (wsStatus.value === 'connecting')
    return '正在连接 Worker 并启动设备实时画面';
  if (wsStatus.value === 'connected')
    return '实时通道已连接，正在等待设备画面';
  if (wsStatus.value === 'error')
    return '实时画面连接失败，请点击顶部“重连”';
  return '实时画面已断开，请点击顶部“重连”';
});
const streamBusy = computed(
  () =>
    isUnlocking.value ||
    unlockCompletedWaitingFrame.value ||
    waitingUnlock.value ||
    wsStatus.value === 'connecting' ||
    (wsStatus.value === 'connected' && !hasDisplayedFrame.value),
);

watch(hasReceivedFrame, (received) => {
  if (received) unlockCompletedWaitingFrame.value = false;
});

// 鸿蒙 WS 推流失败（重试耗尽）时自动拉一张截图兜底，避免黑屏。
// 用户主动"断开"除外：断开即完全断开，保持画面清空。
watch(wsStatus, (val) => {
  if (
    isHarmony.value &&
    !userDisconnected.value &&
    (val === 'disconnected' || val === 'error') &&
    !screenshotBase64.value
  ) {
    refreshHarmonyScreenshot();
  }
});

// 设备分辨率显示
const deviceResolution = computed(() => {
  if (!deviceDetail.value) return '';
  // 优先使用 WebSocket 获取的屏幕尺寸
  if (screenSize.value.width && screenSize.value.height) {
    return `${screenSize.value.width}×${screenSize.value.height}`;
  }
  // 其次使用 extra_message 中的分辨率
  const extra = deviceDetail.value.extra_message;
  if (extra) {
    if (extra.resolution) return extra.resolution;
    if (extra.screen_width && extra.screen_height) {
      return `${extra.screen_width}×${extra.screen_height}`;
    }
  }
  return '';
});

// 设备型号显示：根据设备类型生成默认名称
const deviceModel = computed(() => {
  if (!deviceDetail.value) return '';

  // 优先使用 extra_message 中的设备型号
  const extra = deviceDetail.value.extra_message;
  if (extra?.device_model) {
    return extra.device_model;
  }

  // 根据设备类型生成默认名称
  const deviceType = deviceDetail.value.device_type;
  switch (deviceType) {
    case 'android': {
      return 'Android';
    }
    case 'ios': {
      return 'iPhone';
    }
    case 'mac': {
      return 'Mac';
    }
    case 'harmony_pc': {
      return '鸿蒙 PC';
    }

    case 'windows': {
      return 'Windows';
    }
    default: {
      // 降级显示资产编号或IP
      return deviceDetail.value.asset_number || deviceDetail.value.ip || '';
    }
  }
});

// 系统版本显示
const osVersion = computed(() => {
  if (!deviceDetail.value) return '';
  const extra = deviceDetail.value.extra_message;
  if (extra?.os_version) {
    return extra.os_version;
  }
  if (extra?.os_name) {
    return extra.os_name;
  }
  return '';
});

// 加载设备详情
async function loadDeviceDetail() {
  try {
    loading.value = true;
    const result = await getEnvMachineDetailApi(deviceId);
    deviceDetail.value = result;

    // 设置独立远程窗口的设备标题。
    const title = formatDeviceDebugTitle(
      result.ip || '',
      result.device_sn || '',
      result.device_type,
    );
    if (isRemotePopup) {
      document.title = title;
    } else {
      setTabTitle(title);
    }

    // 连接 Worker 实时推流（鸿蒙优先 H.264，Worker 失败时自动降级 JPEG）。
    const workerHost = result.ip;
    const workerPort = Number.parseInt(result.port, 10);
    const udid = result.device_sn; // 移动设备 udid = device_sn
    const deviceType = result.device_type;

    if (workerHost && workerPort && deviceType) {
      connect(
        workerHost,
        workerPort,
        udid || '',
        deviceType,
        currentScreenIndex.value,
        currentCodec.value,
      );
    } else {
      ElMessage.error('设备缺少 Worker 连接信息');
    }
  } catch (error: any) {
    ElMessage.error(`获取设备详情失败: ${error.message}`);
  } finally {
    loading.value = false;
  }
}

// 返回上一页
async function handleBack() {
  disconnect(true);
  clearDisplayedScreen();
  await releaseSession();
  if (isRemotePopup) {
    window.close();
    return;
  }
  router.back();
}

// 断开连接：完全断开——清空画面、禁用操作（userDisconnected）、
// 通知 Worker 立即停止设备常驻会话（鸿蒙官方投屏），重连后才恢复。
function handleDisconnect() {
  disconnect(true);
  clearDisplayedScreen();
  releaseSession();
}

// 清空展示画面（WS 最后一帧与鸿蒙截图兜底），断开后显示占位图。
function clearDisplayedScreen() {
  if (screenshotBase64.value && screenshotBase64.value.startsWith('blob:')) {
    URL.revokeObjectURL(screenshotBase64.value);
  }
  screenshotBase64.value = '';
  harmonyScreenshotUrl.value = '';
}

// 重新连接
function handleReconnect() {
  if (
    deviceDetail.value?.ip &&
    deviceDetail.value?.port &&
    deviceDetail.value?.device_type
  ) {
    const workerHost = deviceDetail.value.ip;
    const workerPort = Number.parseInt(deviceDetail.value.port, 10);
    const udid = deviceDetail.value.device_sn || '';
    const deviceType = deviceDetail.value.device_type;
    reconnect(
      workerHost,
      workerPort,
      udid,
      deviceType,
      currentScreenIndex.value,
      currentCodec.value,
    );
  }
}

// 屏幕切换
function handleScreenChange(screenIndex: number) {
  currentScreenIndex.value = screenIndex;
  // 重连 WebSocket 到新屏幕
  if (
    deviceDetail.value?.ip &&
    deviceDetail.value?.port &&
    deviceDetail.value?.device_type
  ) {
    reconnect(
      deviceDetail.value.ip,
      Number.parseInt(deviceDetail.value.port, 10),
      deviceDetail.value.device_sn || '',
      deviceDetail.value.device_type,
      screenIndex,
      currentCodec.value,
    );
  }
}

// 屏幕交互事件处理（Pointer Events 统一鼠标/触摸）
// 实时路径：worker 声明 realtime_input 能力时 down/move/up 逐事件走 WS；
// 否则自动回退 legacy——mouseup 合成 click/swipe 走 REST。
function handleScreenPointerDown(event: PointerEvent) {
  // 桌面远程画面获得焦点后，直接接收本机键盘输入。
  if (isNativeKeyboardDevice.value) {
    keyboardCaptureActive.value = true;
    nextTick(() => keyboardCaptureRef.value?.focus({ preventScroll: true }));
  }
  // 用户主动断开后禁止一切屏幕操作，重连后才恢复
  if (userDisconnected.value) return;
  if (rtPointerDown(event)) {
    resetActivityTime();
    return;
  }
  // ===== legacy 路径 =====
  // 右键点击由 contextmenu 事件处理，这里忽略
  if (event.button === 2) return;
  if (isOperating.value || (!isHarmony.value && wsStatus.value !== 'connected'))
    return;
  // 如果点击在屏幕之外，返回 null，不开始操作
  handleDragStart(event);
}

function handleScreenPointerMove(event: PointerEvent) {
  if (realtimeInput.value) {
    rtPointerMove(event);
    return;
  }
  handleDragMove(event);
}

async function handleScreenPointerUp(event: PointerEvent) {
  // 用户主动断开后禁止一切屏幕操作，重连后才恢复
  if (userDisconnected.value) return;
  if (realtimeInput.value && rtPointerUp(event)) {
    resetActivityTime();
    return;
  }
  // ===== legacy 路径：mouseup 合成 click/swipe 走 REST =====
  if (event.button === 2) return;
  if (isOperating.value) return;
  if (!isHarmony.value && wsStatus.value !== 'connected') return;
  // 重置活动时间（用户有操作）
  resetActivityTime();
  const result = handleDragEnd(event);
  if (result) {
    // 桌面端设备传递 monitor 参数（从 1 开始：1=主屏幕，2=副屏幕）
    const monitor = isDesktop.value ? currentScreenIndex.value + 1 : undefined;
    if (result.type === 'click') {
      const clickParams = result.params as { x: number; y: number };
      const success = await click(clickParams.x, clickParams.y, monitor);
      if (success) {
        clickCount.value++;
        if (isHarmony.value && wsStatus.value !== 'connected')
          await refreshHarmonyScreenshot();
      }
    } else if (result.type === 'swipe') {
      const swipeParams = result.params as {
        duration: number;
        from_x: number;
        from_y: number;
        to_x: number;
        to_y: number;
      };
      const success = await swipe(
        swipeParams.from_x,
        swipeParams.from_y,
        swipeParams.to_x,
        swipeParams.to_y,
        swipeParams.duration,
        monitor,
      );
      if (success) {
        swipeCount.value++;
        if (isHarmony.value && wsStatus.value !== 'connected')
          await refreshHarmonyScreenshot();
      }
    }
  }
}

function handleScreenPointerCancel() {
  // 系统打断（如浏览器手势）：实时路径补发安全 up；legacy 清理拖拽状态
  rtPointerCancel();
  handleMouseLeave();
}

function handleScreenPointerLeave() {
  if (realtimeInput.value) {
    rtPointerLeave();
    return;
  }
  handleMouseLeave();
}

function handleScreenWheel(event: WheelEvent) {
  if (userDisconnected.value) return;
  rtWheel(event);
}

// 右键菜单处理：实时路径下右键 down/up 已由 pointer 事件流发出；
// legacy 路径 Windows/Mac/鸿蒙PC 透传右键（鸿蒙PC 用长按映射）
async function handleScreenContextMenu(event: MouseEvent) {
  // 用户主动断开后禁止一切屏幕操作，重连后才恢复
  if (userDisconnected.value) return;
  if (realtimeInput.value) {
    rtContextMenu();
    return;
  }
  if (isOperating.value || (!isHarmony.value && wsStatus.value !== 'connected'))
    return;

  // iOS/Android/鸿蒙手机 不支持右键，忽略（harmony_mobile 已包含在 isMobile 中）
  if (isMobile.value) return;

  // Windows/Mac 透传右键点击到设备
  if (isDesktop.value) {
    const eventTarget = event.currentTarget as HTMLElement | null;
    const wrapper = eventTarget?.classList.contains('screen-wrapper')
      ? eventTarget
      : (event.target as HTMLElement | null)?.closest('.screen-wrapper');
    const media = wrapper?.querySelector('.screen-img') as
      | HTMLImageElement
      | HTMLVideoElement
      | null;
    if (!wrapper || !media) return;

    const rect = wrapper.getBoundingClientRect();

    // 获取媒体源尺寸：img 用 naturalWidth，video 用 videoWidth
    const sourceW =
      'naturalWidth' in media ? media.naturalWidth : media.videoWidth;
    const sourceH =
      'naturalHeight' in media ? media.naturalHeight : media.videoHeight;

    // 防止媒体尚未加载完成
    if (sourceW === 0 || sourceH === 0) {
      return;
    }

    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // 计算 object-fit: contain 的实际渲染区域
    const renderInfo = calculateContainRenderArea(
      rect.width,
      rect.height,
      sourceW,
      sourceH,
      mouseX,
      mouseY,
    );

    // 如果点击不在屏幕区域内，不发送操作
    if (!renderInfo.isValidClick) {
      return;
    }

    // 转换为设备坐标（使用实际渲染尺寸）
    const deviceW = screenSize.value.width || sourceW;
    const deviceH = screenSize.value.height || sourceH;
    const coords = convertToDeviceCoords(
      renderInfo.adjustedX,
      renderInfo.adjustedY,
      renderInfo.renderedWidth,
      renderInfo.renderedHeight,
      deviceW,
      deviceH,
    );

    // 发送右键点击（桌面端传递 monitor 参数）
    resetActivityTime();
    const monitor = currentScreenIndex.value + 1;
    await rightClick(coords.x, coords.y, monitor);
    clickCount.value++;
  }
}

// 按键操作
function handleKeyPress(key: string) {
  // 用户主动断开后禁止操作，重连后才恢复
  if (userDisconnected.value) return;
  resetActivityTime();
  pressKey(key);
}

function enqueueKeyboardAction(action: () => Promise<boolean>) {
  keyboardActionQueue = keyboardActionQueue
    .then(async () => {
      if (remotePageDisposed || userDisconnected.value) return;
      await action();
    })
    .catch((error) => {
      console.warn('[remote-keyboard] 发送键盘输入失败:', error);
    });
}

function flushKeyboardText() {
  if (keyboardFlushTimer) {
    clearTimeout(keyboardFlushTimer);
    keyboardFlushTimer = null;
  }
  const text = keyboardTextBuffer;
  keyboardTextBuffer = '';
  if (text) {
    const sendText = isWindowsDevice.value ? pasteText : inputText;
    enqueueKeyboardAction(() => sendText(text));
  }
}

function appendKeyboardText(text: string) {
  if (!text) return;
  keyboardTextBuffer += text;
  if (keyboardFlushTimer) clearTimeout(keyboardFlushTimer);
  keyboardFlushTimer = setTimeout(flushKeyboardText, KEYBOARD_TEXT_FLUSH_DELAY_MS);
}

function normalizeRemoteKey(key: string): string {
  const harmony = isHarmonyPc.value;
  const keyMap: Record<string, string> = harmony
    ? {
        ArrowDown: 'DOWN',
        ArrowLeft: 'LEFT',
        ArrowRight: 'RIGHT',
        ArrowUp: 'UP',
        Backspace: 'BACKSPACE',
        CapsLock: 'CAPS_LOCK',
        Delete: 'DELETE',
        End: 'MOVE_END',
        Enter: 'ENTER',
        Escape: 'ESCAPE',
        Home: 'MOVE_HOME',
        PageDown: 'PAGE_DOWN',
        PageUp: 'PAGE_UP',
        Tab: 'TAB',
        ' ': 'SPACE',
      }
    : {
        ArrowDown: 'down',
        ArrowLeft: 'left',
        ArrowRight: 'right',
        ArrowUp: 'up',
        Backspace: 'backspace',
        CapsLock: 'capslock',
        Delete: 'delete',
        End: 'end',
        Enter: 'enter',
        Escape: 'esc',
        Home: 'home',
        PageDown: 'pagedown',
        PageUp: 'pageup',
        Tab: 'tab',
        ' ': 'space',
      };
  if (keyMap[key]) return keyMap[key];
  if (/^F(?:[1-9]|1[0-2])$/i.test(key)) return key.toLowerCase();
  if (/^[a-z0-9]$/i.test(key)) return key.toLowerCase();
  return '';
}

function handleNativeKeyDown(event: KeyboardEvent) {
  if (
    !isNativeKeyboardDevice.value ||
    !keyboardCaptureActive.value ||
    userDisconnected.value
  ) {
    return;
  }
  const modifierKey = modifierKeyMap[event.key];
  if (modifierKey) {
    pressedKeyboardModifiers.add(modifierKey);
    event.stopPropagation();
    return;
  }
  if (event.isComposing || event.key === 'Process' || event.key === 'Dead') {
    return;
  }
  const ctrlPressed = event.ctrlKey || pressedKeyboardModifiers.has('ctrl');
  const altPressed = event.altKey || pressedKeyboardModifiers.has('alt');
  const shiftPressed = event.shiftKey || pressedKeyboardModifiers.has('shift');
  const metaPressed = event.metaKey || pressedKeyboardModifiers.has('meta');

  // Ctrl+V 由浏览器 paste 事件读取本机剪贴板，再发送文本到 Worker。
  if (
    ctrlPressed &&
    event.key.toLowerCase() === 'v' &&
    !altPressed &&
    !metaPressed
  ) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  resetActivityTime();

  if (
    isWindowsDevice.value &&
    !ctrlPressed &&
    !altPressed &&
    !metaPressed &&
    /^(?:Key[A-Z]|Digit[0-9]|Numpad[0-9])$/.test(event.code)
  ) {
    // 连续字符先合并为文本发送；数字键按物理码取值，避免字符映射错位。
    const digitKey = /^(?:Digit|Numpad)([0-9])$/.exec(event.code);
    const text = !shiftPressed ? (digitKey?.[1] ?? event.key) : event.key;
    appendKeyboardText(text);
    return;
  }

  if (
    event.key.length === 1 &&
    !ctrlPressed &&
    !altPressed &&
    !metaPressed
  ) {
    appendKeyboardText(event.key);
    return;
  }

  const key = normalizeRemoteKey(event.key);
  if (!key) return;
  const modifiers: string[] = [];
  if (ctrlPressed) modifiers.push('ctrl');
  if (altPressed) modifiers.push('alt');
  if (shiftPressed) modifiers.push('shift');
  if (metaPressed) modifiers.push(isHarmonyPc.value ? 'meta' : 'win');
  flushKeyboardText();
  enqueueKeyboardAction(() => pressKey([...modifiers, key].join('+')));
}

function handleNativeKeyUp(event: KeyboardEvent) {
  const modifierKey = modifierKeyMap[event.key];
  if (!modifierKey) return;
  pressedKeyboardModifiers.delete(modifierKey);
  event.stopPropagation();
}

function handleNativeCompositionEnd(event: CompositionEvent) {
  if (!keyboardCaptureActive.value || !event.data) return;
  resetActivityTime();
  appendKeyboardText(event.data);
  (event.currentTarget as HTMLTextAreaElement).value = '';
}

function handleNativePaste(event: ClipboardEvent) {
  if (!keyboardCaptureActive.value) return;
  event.preventDefault();
  event.stopPropagation();
  const text = event.clipboardData?.getData('text/plain') || '';
  (event.currentTarget as HTMLTextAreaElement).value = '';
  if (!text) return;
  resetActivityTime();
  flushKeyboardText();
  const sendText = isWindowsDevice.value ? pasteText : inputText;
  enqueueKeyboardAction(() => sendText(text));
}

function handleKeyboardCaptureBlur() {
  flushKeyboardText();
  keyboardCaptureActive.value = false;
  pressedKeyboardModifiers.clear();
}

// 输入文本
function handleInputText(text: string) {
  // 用户主动断开后禁止操作，重连后才恢复
  if (userDisconnected.value) return;
  resetActivityTime();
  const sendText = isWindowsDevice.value ? pasteText : inputText;
  sendText(text).then((success) => {
    if (success && isHarmony.value && wsStatus.value !== 'connected')
      refreshHarmonyScreenshot();
  });
}

// 解锁屏幕
async function handleUnlock(password?: string) {
  // 用户主动断开后禁止操作，重连后才恢复
  if (userDisconnected.value) return;
  resetActivityTime();
  const isPcUnlock = isHarmonyPc.value;
  const reconnectH264 = isPcUnlock && waitingUnlock.value;
  unlockDialogVisible.value = false;
  if (isPcUnlock) isUnlocking.value = true;
  try {
    const success = await unlockScreen(password);
    if (!success) return;
    if (isPcUnlock) {
      waitingUnlock.value = false;
      unlockCompletedWaitingFrame.value = true;
      if (reconnectH264 && deviceDetail.value) {
        connect(
          deviceDetail.value.ip,
          Number.parseInt(deviceDetail.value.port, 10),
          deviceDetail.value.device_sn || '',
          deviceDetail.value.device_type,
          currentScreenIndex.value,
          'h264',
        );
      }
      ElMessage.success('解锁成功，正在等待设备画面恢复');
    }
    if (isHarmony.value && wsStatus.value !== 'connected' && !reconnectH264) {
      await refreshHarmonyScreenshot();
    }
  } finally {
    if (isPcUnlock) isUnlocking.value = false;
  }
}

// 鸿蒙手动截图兜底（WS 推流失败后由操作触发刷新画面）
async function refreshHarmonyScreenshot() {
  if (!isHarmony.value) return;
  const screenshotData = await screenshot();
  if (!screenshotData) return;
  unlockCompletedWaitingFrame.value = false;
  harmonyScreenshotUrl.value = `data:image/jpeg;base64,${screenshotData}`;
  const image = new Image();
  image.addEventListener('load', () => {
    screenSize.value = { width: image.width, height: image.height };
  });
  image.src = harmonyScreenshotUrl.value;
}

// 从 H.264 视频元素的当前解码帧生成可下载的图片。
// H.264 推流不会更新 screenshotBase64，保存按钮不能只检查图片流变量。
function captureVideoFrame(video: HTMLVideoElement | null): null | string {
  if (
    !video ||
    video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
    video.videoWidth <= 0 ||
    video.videoHeight <= 0
  ) {
    return null;
  }

  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  try {
    const context = canvas.getContext('2d');
    if (!context) return null;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/png');
  } catch (error) {
    console.warn('[screenshot] 无法读取 H.264 当前视频帧:', error);
    return null;
  }
}

// 截图保存：优先保存当前显示画面，视频尚未出帧时调用截图接口兜底。
async function handleScreenshot() {
  resetActivityTime();
  let screenshotUrl = videoMode.value
    ? captureVideoFrame(
        (desktopScreenRef.value || mobileScreenRef.value)?.videoRef ?? null,
      )
    : displayedScreenshotUrl.value;

  if (!screenshotUrl) {
    const monitor = isDesktop.value ? currentScreenIndex.value + 1 : undefined;
    const screenshotData = await screenshot(monitor);
    if (screenshotData) {
      screenshotUrl = `data:image/png;base64,${screenshotData}`;
    }
  }

  if (screenshotUrl) {
    const link = document.createElement('a');
    link.href = screenshotUrl;
    link.download = `screenshot_${Date.now()}.png`;
    link.click();
  } else {
    ElMessage.warning('暂无截图可保存');
  }
}

// 打开按键弹窗
function handleOpenKeyPressDialog() {
  if (isHarmony.value) {
    ElMessage.info('鸿蒙当前仅支持单键操作');
  }
  keyPressDialogVisible.value = true;
}

// 打开输入文本弹窗
function handleOpenInputDialog() {
  inputTextDialogVisible.value = true;
}

// 打开鸿蒙 PC 解锁弹窗
function handleOpenUnlockDialog() {
  unlockDialogVisible.value = true;
}

// 监听页面滚动
function handlePageScroll() {
  navbarFixed.value = window.scrollY > 56;
}

onMounted(() => {
  loadDeviceDetail();
  window.addEventListener('scroll', handlePageScroll, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener('scroll', handlePageScroll);
  remotePageDisposed = true;
  if (keyboardFlushTimer) clearTimeout(keyboardFlushTimer);
  keyboardTextBuffer = '';
  pressedKeyboardModifiers.clear();
  disconnect();
});
</script>

<template>
  <div class="device-debug-page">
    <!-- 顶部导航栏 -->
    <TopNavbar
      v-if="deviceDetail"
      :device-type="deviceDetail.device_type"
      :asset-number="deviceDetail.asset_number || ''"
      :device-ip="deviceDetail.ip"
      :device-sn="deviceDetail.device_sn"
      :resolution="deviceResolution"
      :ws-status="displayedWsStatus"
      :fps="fps"
      :screen-count="screenCount"
      :current-screen="currentScreenIndex"
      :mouse-coord="mouseCoord"
      :navbar-fixed="navbarFixed"
      :device-model="deviceModel"
      :os-version="osVersion"
      :show-keypress="!isNativeKeyboardDevice"
      :show-input="!isNativeKeyboardDevice"
      @back="handleBack"
      @disconnect="handleDisconnect"
      @reconnect="handleReconnect"
      @keypress="handleOpenKeyPressDialog"
      @input="handleOpenInputDialog"
      @unlock="handleOpenUnlockDialog"
      @screenshot="handleScreenshot"
      @screen-change="handleScreenChange"
    />

    <!-- 主内容区 -->
    <div class="debug-content" :class="{ 'content-padded': navbarFixed }">
      <!-- 桌面端布局：单屏幕展示 -->
      <template v-if="isDesktop">
        <ScreenDisplay
          ref="desktopScreen"
          :screenshot-url="displayedScreenshotUrl"
          :screen-size="screenSize"
          :ws-status="displayedWsStatus"
          :mouse-coord="mouseCoord"
          :is-in-screen="isInScreen"
          :click-indicator="clickIndicator"
          :is-dragging="isDragging"
          :drag-start="dragStart"
          :drag-end="dragEnd"
          :video-mode="videoMode"
          :stream-hint="isDesktop ? streamHint : ''"
          :stream-busy="isDesktop && streamBusy"
          @pointerdown="handleScreenPointerDown"
          @pointermove="handleScreenPointerMove"
          @pointerup="handleScreenPointerUp"
          @pointercancel="handleScreenPointerCancel"
          @pointerleave="handleScreenPointerLeave"
          @wheel="handleScreenWheel"
          @contextmenu="handleScreenContextMenu"
        />
      </template>

      <!-- 移动端布局：左侧屏幕 + 右侧面板 -->
      <template v-if="isMobile">
        <div class="mobile-layout">
          <div class="mobile-screen">
            <ScreenDisplay
              ref="mobileScreen"
              :screenshot-url="displayedScreenshotUrl"
              :screen-size="screenSize"
              :ws-status="displayedWsStatus"
              :mouse-coord="mouseCoord"
              :is-in-screen="isInScreen"
              :click-indicator="clickIndicator"
              :is-dragging="isDragging"
              :drag-start="dragStart"
              :drag-end="dragEnd"
              :video-mode="videoMode"
              @pointerdown="handleScreenPointerDown"
              @pointermove="handleScreenPointerMove"
              @pointerup="handleScreenPointerUp"
              @pointercancel="handleScreenPointerCancel"
              @pointerleave="handleScreenPointerLeave"
              @wheel="handleScreenWheel"
              @contextmenu="handleScreenContextMenu"
            />
          </div>
          <div class="mobile-right">
            <MobilePanel
              :operation-history="operationHistory"
              :udid="deviceDetail?.device_sn"
              @keypress="handleKeyPress"
              @input="handleInputText"
              @unlock="handleUnlock"
              @screenshot="handleScreenshot"
            />
          </div>
        </div>
      </template>
    </div>

    <!-- 隐藏输入框接收键盘和中文输入法事件，不遮挡远程画面。 -->
    <textarea
      v-if="isNativeKeyboardDevice"
      ref="keyboardCaptureRef"
      class="remote-keyboard-capture"
      aria-label="远程键盘输入"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      @blur="handleKeyboardCaptureBlur"
      @compositionend="handleNativeCompositionEnd"
      @keydown="handleNativeKeyDown"
      @keyup="handleNativeKeyUp"
      @paste="handleNativePaste"
    ></textarea>

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
  </div>
</template>

<style scoped>
.device-debug-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow-y: auto;
  background: #f0f2f5;
}


.remote-keyboard-capture {
  position: fixed;
  top: 50%;
  left: 50%;
  width: 1px;
  height: 1px;
  padding: 0;
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, -50%);
}

.debug-content {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: 0;
  overflow: visible;
  background: #f0f2f5;
}

.debug-content.content-padded {
  padding-top: 56px;
}

/* 桌面端布局 - ScreenDisplay直接在debug-content内，已居中 */
.debug-content > :not(.mobile-layout) {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 移动端布局 - 屏幕+面板靠上对齐 */
.mobile-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding-top: 16px;
}

.mobile-screen {
  position: relative;
  flex-shrink: 0;
  width: 380px;
  height: 100%;
  max-height: 720px;
  overflow: hidden;
}

/* 移动端屏幕内部样式覆盖 - 直角无边框 */
.mobile-screen :deep(.screen-display) {
  padding: 0;
  background: #fff;
  border-radius: 0;
  box-shadow: none;
}

.mobile-screen :deep(.screen-card) {
  width: 100%;
  height: 100%;
  border-radius: 0;
  box-shadow: none;
}

.mobile-screen :deep(.screen-wrapper) {
  border-radius: 0;
}

.mobile-screen :deep(.coord-display) {
  inset: 12px auto auto 12px;
  padding: 4px 10px;
  font-size: 11px;
  background: rgb(0 0 0 / 60%);
}

.mobile-right {
  flex: 1;
  max-width: 400px;
  height: 100%;
  max-height: 720px;
}
</style>
