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