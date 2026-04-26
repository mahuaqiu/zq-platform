import { ref } from 'vue';
import type { Ref } from 'vue';

import type { ScreenSize } from '../types';
import { convertToDeviceCoords, calculateContainRenderArea } from '../utils';

export function useScreenInteraction(screenSize: Ref<ScreenSize>) {
  const mouseCoord = ref<{ x: number; y: number } | null>(null);
  const isInScreen = ref(false); // 鼠标是否在屏幕渲染区域内
  const clickIndicator = ref<{ x: number; y: number; show: boolean }>({ x: 0, y: 0, show: false });
  const isDragging = ref(false);
  const dragStart = ref<{ x: number; y: number } | null>(null);
  const dragEnd = ref<{ x: number; y: number } | null>(null);

  /**
   * 获取图片上的坐标（相对于展示区域）
   * 考虑 object-fit: contain 的实际渲染区域
   */
  function getDisplayCoords(event: MouseEvent): { x: number; y: number } | null {
    const img = event.currentTarget as HTMLImageElement;
    const rect = img.getBoundingClientRect();

    // 防止图片尚未加载完成
    if (img.naturalWidth === 0 || img.naturalHeight === 0) {
      return null;
    }

    const mouseX = Math.round(event.clientX - rect.left);
    const mouseY = Math.round(event.clientY - rect.top);

    // 计算 object-fit: contain 的实际渲染区域
    const renderInfo = calculateContainRenderArea(
      rect.width,
      rect.height,
      img.naturalWidth,
      img.naturalHeight,
      mouseX,
      mouseY
    );

    // 如果点击不在渲染区域内，返回 null
    if (!renderInfo.isValidClick) {
      return null;
    }

    // 返回相对于实际渲染图片的坐标
    return {
      x: Math.round(renderInfo.adjustedX),
      y: Math.round(renderInfo.adjustedY)
    };
  }

  /**
   * 获取设备实际坐标
   * 返回 null 表示点击在屏幕之外
   */
  function getDeviceCoords(event: MouseEvent): { x: number; y: number } | null {
    const display = getDisplayCoords(event);
    if (display === null) {
      return null; // 点击在屏幕之外
    }

    const img = event.currentTarget as HTMLImageElement;
    const rect = img.getBoundingClientRect();

    // 计算 object-fit: contain 下的实际渲染尺寸
    const renderInfo = calculateContainRenderArea(
      rect.width,
      rect.height,
      img.naturalWidth,
      img.naturalHeight,
      0, // mouseX 不重要，只需要渲染尺寸
      0
    );

    return convertToDeviceCoords(
      display.x,
      display.y,
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
    const dx = Math.abs(endCoords.x - dragStart.value.x);
    const dy = Math.abs(endCoords.y - dragStart.value.y);

    // 距离小于 20 像素视为点击
    if (dx < 20 && dy < 20) {
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
      // 滑动操作
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
  };
}