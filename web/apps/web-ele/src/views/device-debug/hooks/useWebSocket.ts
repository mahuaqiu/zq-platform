import { onUnmounted, ref } from 'vue';

import { ElMessage } from 'element-plus';

import type { WebSocketCloseInfo, WebSocketStatus, ScreenSize } from '../types';
import { buildWebSocketUrl } from '../utils';

const MAX_RETRIES = 3;
const RETRY_INTERVAL = 2000; // 2秒
const IDLE_TIMEOUT = 300000; // 5分钟 = 300秒

export function useWebSocket() {
  const status = ref<WebSocketStatus>('disconnected');
  const screenshotBase64 = ref('');
  const screenSize = ref<ScreenSize>({ width: 0, height: 0 });
  const fps = ref(0);
  const closeInfo = ref<WebSocketCloseInfo | null>(null);
  const errorMessage = ref('');

  let ws: WebSocket | null = null;
  let retryCount = 0;
  let fpsFrameCount = 0;
  let fpsLastSecond = 0;
  let fpsTimer: ReturnType<typeof setInterval> | null = null;
  let idleTimer: ReturnType<typeof setInterval> | null = null;
  let lastActivityTime = Date.now();

  // 保存连接参数用于重连
  let savedHost = '';
  let savedPort = 0;
  let savedUdid = '';
  let savedDeviceType = '';
  let savedScreenIndex: number | undefined = undefined;

  /**
   * 重置活动时间（用户操作时调用）
   */
  function resetActivityTime(): void {
    lastActivityTime = Date.now();
  }

  /**
   * 开始超时检测（每分钟检查一次）
   */
  function startIdleTimer(): void {
    if (idleTimer) {
      clearInterval(idleTimer);
    }
    lastActivityTime = Date.now();
    idleTimer = setInterval(() => {
      const elapsed = Date.now() - lastActivityTime;
      if (elapsed >= IDLE_TIMEOUT && ws && status.value === 'connected') {
        // 超时断开
        disconnect();
        console.log('WebSocket 因 5 分钟无操作已自动断开');
      }
    }, 60000); // 每分钟检查一次
  }

  /**
   * 停止超时检测
   */
  function stopIdleTimer(): void {
    if (idleTimer) {
      clearInterval(idleTimer);
      idleTimer = null;
    }
  }

  /**
   * 连接 WebSocket
   */
  function connect(host: string, port: number, udid: string, deviceType: string, screenIndex?: number): void {
    // 保存参数用于重连
    savedHost = host;
    savedPort = port;
    savedUdid = udid;
    savedDeviceType = deviceType;
    savedScreenIndex = screenIndex;

    // 关闭旧连接（使用 code=1000 表示正常关闭，不触发自动重连）
    if (ws) {
      retryCount = MAX_RETRIES; // 阻止旧连接的 onclose 触发重连
      ws.close(1000);
      ws = null;
    }

    status.value = 'connecting';
    errorMessage.value = '';
    closeInfo.value = null;

    const url = buildWebSocketUrl(host, port, udid, deviceType, screenIndex);
    ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      status.value = 'connected';
      retryCount = 0;
      fpsFrameCount = 0;
      fpsLastSecond = Date.now();
      startFpsTimer();
      startIdleTimer(); // 启动超时检测
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
      fpsFrameCount++;

      // 解析图片尺寸
      const img = new Image();
      img.onload = () => {
        screenSize.value = { width: img.width, height: img.height };
      };
      img.src = url;
    };

    ws.onclose = (event) => {
      stopFpsTimer();
      stopIdleTimer(); // 停止超时检测
      status.value = 'disconnected';
      closeInfo.value = { code: event.code, reason: event.reason };

      // 非正常关闭时尝试重连
      if (event.code !== 1000 && retryCount < MAX_RETRIES) {
        retryCount++;
        setTimeout(() => {
          if (retryCount <= MAX_RETRIES) {
            connect(savedHost, savedPort, savedUdid, savedDeviceType, savedScreenIndex);
          }
        }, RETRY_INTERVAL);
      } else if (event.code !== 1000 && retryCount >= MAX_RETRIES) {
        // 达到最大重试次数后显示错误
        ElMessage.error('WebSocket 连接失败，已尝试重连 3 次，请检查设备状态');
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
    stopIdleTimer();
    status.value = 'disconnected';
  }

  /**
   * 重新连接
   */
  function reconnect(host: string, port: number, udid: string, deviceType: string, screenIndex?: number): void {
    retryCount = 0;
    connect(host, port, udid, deviceType, screenIndex);
  }

  /**
   * 开始帧率计算
   */
  function startFpsTimer(): void {
    fpsTimer = setInterval(() => {
      const now = Date.now();
      const elapsedSeconds = (now - fpsLastSecond) / 1000;
      if (elapsedSeconds >= 1) {
        fps.value = Math.round(fpsFrameCount / elapsedSeconds);
        fpsFrameCount = 0;
        fpsLastSecond = now;
      }
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
    resetActivityTime,
  };
}