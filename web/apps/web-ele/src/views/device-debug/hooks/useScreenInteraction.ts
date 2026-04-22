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
    params: { x: number; y: number } | { from_x: number; from_y: number; to_x: number; to_y: number; duration: number };
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