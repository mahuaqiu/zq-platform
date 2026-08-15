import { ref } from 'vue';
import type { Ref } from 'vue';

import type { ScreenSize } from '../types';
import { convertToDeviceCoords, calculateContainRenderArea } from '../utils';

// 滑动判断阈值配置
const SWIPE_THRESHOLD_NORMAL = 50;  // 普通区域的滑动阈值（像素）
const SWIPE_THRESHOLD_EDGE = 30;    // 边缘区域的滑动阈值（像素）
const EDGE_ZONE_RATIO = 0.15;       // 边缘区域比例（屏幕底部 15%）

// 滑动方向类型
type SwipeDirection = 'vertical' | 'horizontal' | 'diagonal';

export function useScreenInteraction(screenSize: Ref<ScreenSize>) {
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
    const mediaRect = media.getBoundingClientRect();
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

    return { media, wrapper, rect, mediaRect, naturalW, naturalH, mouseX, mouseY, renderInfo };
  }

  /**
   * 临时诊断：对比 wrapper 手算 contain 与 media 真实矩形的映射结果。
   * 仅在点击起止时打印，避免 mousemove 刷屏。验证完可删除。
   */
  function logCoordDiag(
    event: MouseEvent,
    stage: string,
    coords: { x: number; y: number } | null,
  ): void {
    const info = getRenderInfo(event);
    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio : 1;
    if (!info) {
      console.info('[coord-diag]', {
        stage,
        reason: 'no-render-info',
        client: { x: event.clientX, y: event.clientY },
        screenSize: { ...screenSize.value },
        dpr,
        coords,
      });
      return;
    }

    const { rect, mediaRect, naturalW, naturalH, mouseX, mouseY, renderInfo } = info;

    // 路径 A：当前实现（wrapper + 手算 contain）
    const pathA = renderInfo.isValidClick
      ? convertToDeviceCoords(
          renderInfo.adjustedX,
          renderInfo.adjustedY,
          renderInfo.renderedWidth,
          renderInfo.renderedHeight,
          screenSize.value.width,
          screenSize.value.height,
        )
      : null;

    // 路径 B：直接用 media 真实矩形映射（假说验证对照）
    const mediaLocalX = event.clientX - mediaRect.left;
    const mediaLocalY = event.clientY - mediaRect.top;
    const inMedia =
      mediaLocalX >= 0 &&
      mediaLocalX <= mediaRect.width &&
      mediaLocalY >= 0 &&
      mediaLocalY <= mediaRect.height;
    const pathB =
      inMedia && mediaRect.width > 0 && mediaRect.height > 0 && screenSize.value.width > 0
        ? {
            x: Math.round((mediaLocalX / mediaRect.width) * screenSize.value.width),
            y: Math.round((mediaLocalY / mediaRect.height) * screenSize.value.height),
          }
        : null;

    console.info('[coord-diag]', {
      stage,
      dpr,
      client: { x: event.clientX, y: event.clientY },
      wrapper: {
        w: Number(rect.width.toFixed(2)),
        h: Number(rect.height.toFixed(2)),
      },
      mediaBox: {
        w: Number(mediaRect.width.toFixed(2)),
        h: Number(mediaRect.height.toFixed(2)),
        left: Number((mediaRect.left - rect.left).toFixed(2)),
        top: Number((mediaRect.top - rect.top).toFixed(2)),
      },
      calcContain: {
        renderedW: Number(renderInfo.renderedWidth.toFixed(2)),
        renderedH: Number(renderInfo.renderedHeight.toFixed(2)),
        offsetX: Number(renderInfo.offsetX.toFixed(2)),
        offsetY: Number(renderInfo.offsetY.toFixed(2)),
        isValidClick: renderInfo.isValidClick,
      },
      // 手算偏移 vs 真实 media 盒子偏移：差几 px 就说明主假说成立
      boxDelta: {
        w: Number((mediaRect.width - renderInfo.renderedWidth).toFixed(2)),
        h: Number((mediaRect.height - renderInfo.renderedHeight).toFixed(2)),
        left: Number((mediaRect.left - rect.left - renderInfo.offsetX).toFixed(2)),
        top: Number((mediaRect.top - rect.top - renderInfo.offsetY).toFixed(2)),
      },
      source: { naturalW, naturalH },
      screenSize: { ...screenSize.value },
      mouseInWrapper: {
        x: Number(mouseX.toFixed(2)),
        y: Number(mouseY.toFixed(2)),
      },
      mouseInMedia: {
        x: Number(mediaLocalX.toFixed(2)),
        y: Number(mediaLocalY.toFixed(2)),
        inMedia,
      },
      pathA_wrapperContain: pathA,
      pathB_mediaRect: pathB,
      sentCoords: coords,
      pathDiff:
        pathA && pathB
          ? { dx: pathA.x - pathB.x, dy: pathA.y - pathB.y }
          : null,
    });
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
    logCoordDiag(event, 'drag-start', coords);

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
    logCoordDiag(event, 'drag-end', endCoords);

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
  };
}
