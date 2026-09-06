import { onUnmounted, ref } from 'vue';
import type { Ref } from 'vue';

import type { InputEventPayload, ScreenSize } from '../types';
import { convertToDeviceCoords, calculateContainRenderArea } from '../utils';

// 滑动判断阈值配置（legacy 回退路径使用）
const SWIPE_THRESHOLD_NORMAL = 50;  // 普通区域的滑动阈值（像素）
const SWIPE_THRESHOLD_EDGE = 30;    // 边缘区域的滑动阈值（像素）
const EDGE_ZONE_RATIO = 0.15;       // 边缘区域比例（屏幕底部 15%）

// 实时指针流参数
const HOVER_MOVE_INTERVAL_MS = 1500; // hover 移动节流（光标跟随低频同步即可）
const WHEEL_SEND_INTERVAL_MS = 50; // 滚轮节流
const WHEEL_STOP_DELAY_MS = 120; // 滚轮停顿后补发 stop 的延迟

/**
 * 实时指针输入上下文（由 index.vue 注入）。
 * sendInput/realtimeInput 来自 useWebSocket；isPcDevice 决定是否发送 hover 移动
 * （鸿蒙手机没有鼠标光标，hover 无意义）。
 */
export interface RealtimeInputContext {
  sendInput: (payload: InputEventPayload) => boolean;
  realtimeInput: Ref<boolean>;
  isPcDevice: Ref<boolean>;
}

// 滑动方向类型
type SwipeDirection = 'vertical' | 'horizontal' | 'diagonal';

export function useScreenInteraction(
  screenSize: Ref<ScreenSize>,
  input?: RealtimeInputContext,
) {
  const mouseCoord = ref<{ x: number; y: number } | null>(null);
  const isInScreen = ref(false); // 鼠标是否在屏幕渲染区域内
  const clickIndicator = ref<{ x: number; y: number; show: boolean }>({ x: 0, y: 0, show: false });
  const isDragging = ref(false);
  const dragStart = ref<{ x: number; y: number } | null>(null);
  const dragEnd = ref<{ x: number; y: number } | null>(null);

  /**
   * 从事件源元素提取"源内容尺寸"。
   *
   * 兼容两种渲染元素：
   * - <img>：用 naturalWidth/naturalHeight（图片原始尺寸）
   * - <video>：用 videoWidth/videoHeight（视频源尺寸）
   *
   * MSE 方案渲染 <video>，JPEG 方案渲染 <img>，两者都走 object-fit: contain，
   * 因此坐标换算逻辑完全一致，仅需统一尺寸来源。
   */
  function getMediaSourceSize(
    target: EventTarget | null
  ): { el: HTMLElement; naturalW: number; naturalH: number } | null {
    if (!(target instanceof HTMLImageElement) && !(target instanceof HTMLVideoElement)) {
      return null;
    }
    const el = target;

    if ('naturalWidth' in el) {
      // HTMLImageElement
      return { el, naturalW: el.naturalWidth, naturalH: el.naturalHeight };
    }
    // HTMLVideoElement
    return { el, naturalW: el.videoWidth, naturalH: el.videoHeight };
  }

  /**
   * 获取媒体元素所在的屏幕容器。
   *
   * 媒体元素本身可能只是 contain 后的实际绘制尺寸，不能作为留白区域的
   * 计算基准；真正的鼠标命中区域是外层 screen-wrapper。
   */
  function getScreenWrapper(el: HTMLElement): HTMLElement {
    return el.closest('.screen-wrapper') ?? el.parentElement ?? el;
  }

  /**
   * 从鼠标事件中获取媒体元素。
   *
   * 触摸事件转换出的 MouseEvent 不会经过 DOM 分发，currentTarget/target
   * 为空，因此 ScreenDisplay 会额外附带 screenElement 供这里使用。
   */
  function getEventMediaElement(event: MouseEvent): HTMLElement | null {
    const eventWithElement = event as MouseEvent & { screenElement?: EventTarget | null };
    return (
      getMediaSourceSize(event.currentTarget)?.el ??
      getMediaSourceSize(event.target)?.el ??
      getMediaSourceSize(eventWithElement.screenElement ?? null)?.el ??
      null
    );
  }

  function getRenderInfo(event: MouseEvent) {
    const media = getEventMediaElement(event);
    if (!media) return null;

    const wrapper = getScreenWrapper(media);
    const rect = wrapper.getBoundingClientRect();
    const naturalW = 'naturalWidth' in media
      ? (media as HTMLImageElement).naturalWidth
      : (media as HTMLVideoElement).videoWidth;
    const naturalH = 'naturalHeight' in media
      ? (media as HTMLImageElement).naturalHeight
      : (media as HTMLVideoElement).videoHeight;

    if (naturalW <= 0 || naturalH <= 0 || rect.width <= 0 || rect.height <= 0) {
      return null;
    }

    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const renderInfo = calculateContainRenderArea(
      rect.width,
      rect.height,
      naturalW,
      naturalH,
      mouseX,
      mouseY,
    );

    return { media, wrapper, rect, naturalW, naturalH, mouseX, mouseY, renderInfo };
  }

  /**
   * 获取设备实际坐标
   * 返回 null 表示点击在屏幕之外
   */
  function getDeviceCoords(event: MouseEvent): { x: number; y: number } | null {
    const renderInfo = getRenderInfo(event)?.renderInfo;
    if (!renderInfo || !renderInfo.isValidClick) {
      return null; // 点击在屏幕之外
    }

    return convertToDeviceCoords(
      renderInfo.adjustedX,
      renderInfo.adjustedY,
      renderInfo.renderedWidth,
      renderInfo.renderedHeight,
      screenSize.value.width,
      screenSize.value.height
    );
  }

  /**
   * 拖拽开始
   * 返回 null 表示点击在屏幕之外，不开始拖拽
   */
  function handleDragStart(event: MouseEvent): { x: number; y: number } | null {
    event.preventDefault();
    const coords = getDeviceCoords(event);

    // 如果点击在屏幕之外，不开始拖拽
    if (coords === null) {
      isInScreen.value = false;
      return null;
    }

    isInScreen.value = true;
    isDragging.value = true;
    dragStart.value = coords;
    dragEnd.value = null;
    return coords;
  }

  /**
   * 拖拽移动
   * 返回 null 表示鼠标在屏幕之外
   */
  function handleDragMove(event: MouseEvent): { x: number; y: number } | null {
    const coords = getDeviceCoords(event);
    isInScreen.value = coords !== null;

    if (isDragging.value) {
      // 拖拽过程中，如果移出屏幕，保留最后有效坐标
      if (coords !== null) {
        dragEnd.value = coords;
        mouseCoord.value = coords;
      }
      // 如果 coords 是 null，保留当前状态不变（最后有效坐标）
    } else {
      mouseCoord.value = coords; // 非拖拽时，坐标可能为 null
    }
    return coords;
  }

  /**
   * 判断滑动方向
   */
  function detectSwipeDirection(dx: number, dy: number): SwipeDirection {
    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);

    // 垂直滑动：Y 方向位移显著大于 X 方向
    if (absDy > absDx * 1.5) {
      return 'vertical';
    }
    // 水平滑动：X 方向位移显著大于 Y 方向
    if (absDx > absDy * 1.5) {
      return 'horizontal';
    }
    // 斜向滑动
    return 'diagonal';
  }

  /**
   * 检查是否在边缘区域（屏幕底部）
   */
  function isInEdgeZone(y: number): boolean {
    const screenHeight = screenSize.value.height;
    if (screenHeight === 0) return false;
    // 底部边缘区域：y 坐标在屏幕底部 15% 范围内
    return y >= screenHeight * (1 - EDGE_ZONE_RATIO);
  }

  /**
   * 获取适合的滑动阈值
   * 边缘区域使用较小的阈值，让向上滑动更容易触发
   */
  function getSwipeThreshold(startY: number, direction: SwipeDirection): number {
    // 如果在底部边缘区域且是向上滑动，使用更小的阈值
    if (isInEdgeZone(startY) && direction === 'vertical') {
      return SWIPE_THRESHOLD_EDGE;
    }
    // 其他情况使用标准阈值
    return SWIPE_THRESHOLD_NORMAL;
  }

  /**
   * 拖拽结束，判断是点击还是滑动
   * 如果拖拽结束点在屏幕之外，使用最后一个有效坐标
   */
  function handleDragEnd(event: MouseEvent): {
    type: 'click' | 'swipe';
    params: { x: number; y: number } | { from_x: number; from_y: number; to_x: number; to_y: number; duration: number };
  } | null {
    if (!isDragging.value || !dragStart.value) return null;

    isDragging.value = false;

    // 优先使用事件坐标，如果不在屏幕内则使用最后一个有效坐标
    const eventCoords = getDeviceCoords(event);
    const endCoords = eventCoords ?? dragEnd.value ?? dragStart.value;

    // 如果结束点也没有有效坐标，取消操作
    if (endCoords === null) {
      dragStart.value = null;
      dragEnd.value = null;
      return null;
    }

    // 计算滑动距离
    const dx = endCoords.x - dragStart.value.x;
    const dy = endCoords.y - dragStart.value.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    // 检测滑动方向
    const direction = detectSwipeDirection(dx, dy);

    // 获取适合的阈值（边缘区域使用更小的阈值）
    const threshold = getSwipeThreshold(dragStart.value.y, direction);

    // 距离小于阈值视为点击
    if (distance < threshold) {
      // 点击操作
      clickIndicator.value = { x: dragStart.value.x, y: dragStart.value.y, show: true };
      setTimeout(() => {
        clickIndicator.value.show = false;
      }, 500);

      const result: {
        type: 'click';
        params: { x: number; y: number };
      } = {
        type: 'click',
        params: { x: dragStart.value.x, y: dragStart.value.y }
      };
      dragStart.value = null;
      dragEnd.value = null;
      return result;
    } else {
      // 滑动操作 - 根据方向调整持续时间
      // 垂直滑动（如解锁）使用较长的持续时间，让滑动更流畅
      const duration = direction === 'vertical' ? 600 : 500;

      const result: {
        type: 'swipe';
        params: { from_x: number; from_y: number; to_x: number; to_y: number; duration: number };
      } = {
        type: 'swipe',
        params: {
          from_x: dragStart.value.x,
          from_y: dragStart.value.y,
          to_x: endCoords.x,
          to_y: endCoords.y,
          duration
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
    const coords = getDeviceCoords(event);
    mouseCoord.value = coords;
    isInScreen.value = coords !== null;
  }

  /**
   * 鼠标离开
   */
  function handleMouseLeave(): void {
    mouseCoord.value = null;
    isInScreen.value = false;
    if (isDragging.value) {
      isDragging.value = false;
      dragStart.value = null;
      dragEnd.value = null;
    }
  }

  // ===== 实时指针流（P1）：down 立即发、move rAF 抵尾合并、up 兜底 =====
  // 仅当 worker 声明 realtime_input 能力时由 index.vue 调用；否则走上方
  // 保留的 legacy click/swipe 路径（mouseup 合成一条 REST 手势）。
  let pressing = false;
  let pressButton: 'left' | 'right' = 'left';
  let pendingMove: { x: number; y: number } | null = null;
  let moveRafId: number | null = null;
  let firstMoveSent = false;
  let hoverLastSentAt = 0;
  let wheelLastSentAt = 0;
  let wheelStopTimer: ReturnType<typeof setTimeout> | null = null;
  let wheelLastCoord: { x: number; y: number } | null = null;
  let inputSeq = 0;
  // hover 移动开关：用户点击过远程屏幕（进入"操控"状态）才发送；
  // 鼠标离开画面或浏览器失焦即复位，避免指针掠过页面产生无意义的设备侧移动。
  let screenActivated = false;

  if (typeof window !== 'undefined') {
    const handleWindowBlur = () => {
      screenActivated = false;
    };
    window.addEventListener('blur', handleWindowBlur);
    onUnmounted(() => window.removeEventListener('blur', handleWindowBlur));
  }

  function rtSend(payload: InputEventPayload): void {
    input?.sendInput({ seq: ++inputSeq, ts: Date.now(), ...payload });
  }

  function rtCancelScheduledMove(): void {
    if (moveRafId !== null) {
      cancelAnimationFrame(moveRafId);
      moveRafId = null;
    }
  }

  function rtFlushMove(): void {
    moveRafId = null;
    if (!pressing || !pendingMove) return;
    rtSend({
      action: 'move',
      button: pressButton,
      x: pendingMove.x,
      y: pendingMove.y,
    });
    dragEnd.value = pendingMove;
    pendingMove = null;
  }

  /** 按下：立即发送 down（不等帧）。返回 false 表示未走实时路径（legacy 处理）。 */
  function rtPointerDown(event: PointerEvent): boolean {
    if (!input?.realtimeInput.value) return false;
    if (event.button !== 0 && event.button !== 2) return false; // 中键暂不处理
    const coords = getDeviceCoords(event);
    if (coords === null) return false;
    pressing = true;
    pressButton = event.button === 2 ? 'right' : 'left';
    firstMoveSent = false;
    pendingMove = null;
    screenActivated = true; // 点击远程屏幕即进入操控状态，hover 开始同步
    rtSend({ action: 'down', button: pressButton, x: coords.x, y: coords.y });
    // 复用 legacy 拖拽轨迹 UI 实时回显
    dragStart.value = coords;
    dragEnd.value = null;
    isDragging.value = true;
    return true;
  }

  /** 移动：按下时 rAF 抵尾合并发送（首个 move 立即发）；悬停时 PC 节流发 hover。 */
  function rtPointerMove(event: PointerEvent): void {
    if (!input?.realtimeInput.value) return;
    const coords = getDeviceCoords(event);
    mouseCoord.value = coords;
    isInScreen.value = coords !== null;
    if (coords === null) return;
    if (pressing) {
      pendingMove = coords;
      // down 后第一个 move 立即发送，降低起手延迟；其余合并到下一帧
      if (!firstMoveSent) {
        firstMoveSent = true;
        rtCancelScheduledMove();
        rtSend({
          action: 'move',
          button: pressButton,
          x: coords.x,
          y: coords.y,
        });
        dragEnd.value = coords;
        pendingMove = null;
      } else if (moveRafId === null) {
        moveRafId = requestAnimationFrame(rtFlushMove);
      }
    } else if (input.isPcDevice.value && screenActivated) {
      const now = performance.now();
      if (now - hoverLastSentAt >= HOVER_MOVE_INTERVAL_MS) {
        hoverLastSentAt = now;
        rtSend({ action: 'move', button: null, x: coords.x, y: coords.y });
      }
    }
  }

  /** 抬起：冲刷最后一个 move 后发送 up。返回是否由实时路径处理。 */
  function rtPointerUp(event: PointerEvent): boolean {
    if (!pressing) return false;
    pressing = false;
    rtCancelScheduledMove();
    const coords = getDeviceCoords(event) ?? dragEnd.value ?? dragStart.value;
    if (coords) {
      rtSend({ action: 'up', button: pressButton, x: coords.x, y: coords.y });
    }
    isDragging.value = false;
    dragStart.value = null;
    dragEnd.value = null;
    pendingMove = null;
    return true;
  }

  /** 系统打断（pointercancel）：按抬起处理，坐标用最后有效值，防按键卡死。 */
  function rtPointerCancel(): void {
    if (!pressing) return;
    pressing = false;
    rtCancelScheduledMove();
    const coords = dragEnd.value ?? dragStart.value;
    if (coords) {
      rtSend({ action: 'up', button: pressButton, x: coords.x, y: coords.y });
    }
    isDragging.value = false;
    dragStart.value = null;
    dragEnd.value = null;
    pendingMove = null;
  }

  /** 滚轮：节流发送 wheel 事件并阻止页面滚动。
   *
   * 鸿蒙官方 SDK 要求 onMouseWheelStop 跟在 Up/Down 之后滚动才生效，
   * 因此每次滚轮停顿 WHEEL_STOP_DELAY_MS 后补发一条 stop。
   */
  function rtWheel(event: WheelEvent): void {
    if (!input?.realtimeInput.value) return;
    const coords = getDeviceCoords(event);
    if (coords === null) return;
    event.preventDefault();
    const now = performance.now();
    if (now - wheelLastSentAt < WHEEL_SEND_INTERVAL_MS) return;
    wheelLastSentAt = now;
    const amount = Math.max(
      1,
      Math.min(10, Math.round(Math.abs(event.deltaY) / 100)),
    );
    rtSend({
      action: 'wheel',
      direction: event.deltaY < 0 ? 'up' : 'down',
      amount,
      x: coords.x,
      y: coords.y,
    });
    // 滚轮停顿后补发 stop（worker 端 Windows 分发器对 stop 自动忽略）
    wheelLastCoord = coords;
    if (wheelStopTimer !== null) clearTimeout(wheelStopTimer);
    wheelStopTimer = setTimeout(() => {
      wheelStopTimer = null;
      if (wheelLastCoord) {
        rtSend({
          action: 'wheel',
          direction: 'stop',
          x: wheelLastCoord.x,
          y: wheelLastCoord.y,
        });
      }
    }, WHEEL_STOP_DELAY_MS);
  }

  /** 右键菜单：实时路径下 down/up 已由 pointer 事件流发出，这里仅屏蔽 legacy。 */
  function rtContextMenu(): boolean {
    return Boolean(input?.realtimeInput.value);
  }

  /** 移出画面：清坐标显示并退出操控状态（重新点击后才恢复 hover 同步）。 */
  function rtPointerLeave(): void {
    mouseCoord.value = null;
    isInScreen.value = false;
    screenActivated = false;
    if (pressing) {
      rtPointerCancel();
    }
  }

  return {
    mouseCoord,
    isInScreen,
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
    detectSwipeDirection,
    isInEdgeZone,
    rtPointerDown,
    rtPointerMove,
    rtPointerUp,
    rtPointerCancel,
    rtWheel,
    rtContextMenu,
    rtPointerLeave,
  };
}
