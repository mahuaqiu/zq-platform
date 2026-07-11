import { onUnmounted, ref, shallowRef } from 'vue';

import { ElMessage } from 'element-plus';

import type { WebSocketCloseInfo, WebSocketStatus, ScreenSize } from '../types';
import { buildWebSocketUrl } from '../utils';
import { detectFrameType, FrameType } from '../utils/stream';
import { useMseDecoder } from './useMseDecoder';
import { useMJPEGRenderer } from './useMJPEGRenderer';

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
  let streamSummaryLast = 0;
  let fpsTimer: ReturnType<typeof setInterval> | null = null;
  let idleTimer: ReturnType<typeof setInterval> | null = null;
  let lastActivityTime = Date.now();
  let streamConnectStarted = 0;
  let streamOpenedAt = 0;
  let streamPacketCount = 0;
  let streamTotalPacketCount = 0;
  let streamBytes = 0;

  // H264 视频元素（由 ScreenDisplay 挂载后通过 attachVideoEl 传入）。
  // MSE/jmuxer 需要绑定 <video> 元素，生命周期归 ScreenDisplay，
  // 解码逻辑归本 hook，故用 shallowRef 持有引用并在就绪时 init decoder。
  const videoEl = shallowRef<HTMLVideoElement | null>(null);

  // 是否处于 H264(MSE) 渲染模式（true 时 ScreenDisplay 渲染 <video>，否则 <img>）
  const videoMode = ref(false);

  // H.264 解码器 (MSE + jmuxer)。
  // 替代原 WebCodecs 方案：WebCodecs VideoDecoder 是 Secure Context-only API，
  // HTTP 内网（非 localhost）下不可用；MSE 无此限制。
  const mseDecoder = useMseDecoder({
    videoEl,
    fps: 10,
    onReady: () => console.log('[WebSocket] H264 decoder ready (MSE/jmuxer)'),
    onError: (e) => console.error('[WebSocket] H264 MSE error:', e),
    onFallback: () => {
      console.warn('[WebSocket] H264 MSE failed, falling back to JPEG');
      // 退出 video 模式，重新连接使用 JPEG
      videoMode.value = false;
      reconnect(savedHost, savedPort, savedUdid, savedDeviceType, savedScreenIndex, 'jpeg');
    },
  });

  // 由 ScreenDisplay 在 <video> 挂载后调用，绑定元素并初始化 MSE 解码器
  // 保存当前绑定的 video 元素和监听器，用于 disconnect 时清理
  let currentVideoEl: HTMLVideoElement | null = null;
  let loadedMetaHandler: (() => void) | null = null;

  function attachVideoEl(el: HTMLVideoElement | null): void {
    // 先清理之前的监听器
    if (currentVideoEl && loadedMetaHandler) {
      currentVideoEl.removeEventListener('loadedmetadata', loadedMetaHandler);
      currentVideoEl = null;
      loadedMetaHandler = null;
    }

    videoEl.value = el;
    if (!el) return;

    // H264 模式下没有 JPEG，无法通过 Image 获取 screenSize。
    // 从 video 的 loadedmetadata 读取视频源尺寸（jmuxer 从 SPS 解析后写入 video）。
    const onLoadedMeta = () => {
      if (el.videoWidth > 0 && el.videoHeight > 0) {
        screenSize.value = { width: el.videoWidth, height: el.videoHeight };
      }
    };
    el.addEventListener('loadedmetadata', onLoadedMeta);
    currentVideoEl = el;
    loadedMetaHandler = onLoadedMeta;

    if (videoMode.value) {
      mseDecoder.init();
    }
  }

  // MJPEG 渲染器
  const mjpegRenderer = useMJPEGRenderer();

  // 保存连接参数用于重连
  let savedHost = '';
  let savedPort = 0;
  let savedUdid = '';
  let savedDeviceType = '';
  let savedScreenIndex: number | undefined = undefined;
  let savedCodec = 'jpeg';

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
  function connect(host: string, port: number, udid: string, deviceType: string, screenIndex?: number, codec: string = 'jpeg'): void {
    // 保存参数用于重连
    savedHost = host;
    savedPort = port;
    savedUdid = udid;
    savedDeviceType = deviceType;
    savedScreenIndex = screenIndex;
    savedCodec = codec;

    console.log(`[WebSocket] Connecting to ${host}:${port}, deviceType=${deviceType}, codec=${codec}`);
    streamConnectStarted = performance.now();
    streamOpenedAt = 0;
    streamPacketCount = 0;
    streamTotalPacketCount = 0;
    streamBytes = 0;

    // 关闭旧连接（使用 code=1000 表示正常关闭，不触发自动重连）
    if (ws) {
      retryCount = MAX_RETRIES; // 阻止旧连接的 onclose 触发重连
      ws.close(1000);
      ws = null;
    }

    // 根据 codec 决定渲染模式：H264 → <video>(MSE)，JPEG/MJPEG → <img>
    const isH264 = codec === 'h264';
    if (isH264) {
      // 进入 MSE 模式前先销毁旧的 jmuxer 实例，避免重复初始化
      mseDecoder.dispose();
    }
    videoMode.value = isH264;

    status.value = 'connecting';
    errorMessage.value = '';
    closeInfo.value = null;

    const url = buildWebSocketUrl(host, port, udid, deviceType, screenIndex, codec);
    ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      status.value = 'connected';
      streamOpenedAt = performance.now();
      console.info('[stream-diag] websocket open', { connectMs: streamOpenedAt - streamConnectStarted, codec });
      retryCount = 0;
      fpsFrameCount = 0;
      fpsLastSecond = Date.now();
      streamSummaryLast = Date.now();
      startFpsTimer();
      startIdleTimer(); // 启动超时检测

      // H264 模式：连接建立后初始化 MSE 解码器（此时 video 元素应已通过 attachVideoEl 绑定）
      if (isH264) {
        mseDecoder.init();
      }
    };

    ws.onmessage = (event) => {
      // event.data 是 ArrayBuffer
      const arrayBuffer = event.data as ArrayBuffer;
      streamPacketCount += 1;
      streamTotalPacketCount += 1;
      streamBytes += arrayBuffer.byteLength;

      // 检测帧类型（不再每帧打日志，避免控制台对象累积导致内存泄漏）
      switch (detectFrameType(arrayBuffer)) {
        case FrameType.H264:
          // H.264: 喂入 MSE 解码器（jmuxer 自动处理 SPS/PPS/IDR/P）
          mseDecoder.feedFrame(arrayBuffer);
          break;

        case FrameType.MJPEG:
          // MJPEG: 渲染到 canvas
          mjpegRenderer.render(arrayBuffer);
          break;

        case FrameType.JPEG:
        default:
          // JPEG: 使用 Blob URL
          const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
          const url = URL.createObjectURL(blob);

          // 释放之前的 URL
          if (screenshotBase64.value && screenshotBase64.value.startsWith('blob:')) {
            URL.revokeObjectURL(screenshotBase64.value);
          }

          screenshotBase64.value = url;

          // 解析图片尺寸
          const img = new Image();
          img.onload = () => {
            screenSize.value = { width: img.width, height: img.height };
          };
          img.src = url;
          break;
      }

      // 更新帧率计数
      fpsFrameCount++;
    };

    ws.onclose = (event) => {
      stopFpsTimer();
      stopIdleTimer(); // 停止超时检测
      status.value = 'disconnected';
      closeInfo.value = { code: event.code, reason: event.reason };

      console.log(`[WebSocket] Connection closed: code=${event.code}, reason=${event.reason}, retryCount=${retryCount}`);

      // 非正常关闭时尝试重连
      if (event.code !== 1000 && retryCount < MAX_RETRIES) {
        retryCount++;
        setTimeout(() => {
          if (retryCount <= MAX_RETRIES) {
            console.log(`[WebSocket] Attempting reconnect #${retryCount} with codec=${savedCodec}`);
            connect(savedHost, savedPort, savedUdid, savedDeviceType, savedScreenIndex, savedCodec);
          }
        }, RETRY_INTERVAL);
      } else if (event.code !== 1000 && retryCount >= MAX_RETRIES) {
        // 达到最大重试次数后显示错误
        ElMessage.error('WebSocket 连接失败，已尝试重连 3 次，请检查设备状态');
      }
    };

    ws.onerror = (event) => {
      status.value = 'error';
      errorMessage.value = 'WebSocket 连接失败';
      console.error(`[WebSocket] Error:`, event);
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
    // 释放 MSE 解码器资源
    mseDecoder.dispose();
    videoMode.value = false;

    // 清理 video 元素的事件监听器，防止内存泄漏
    if (currentVideoEl && loadedMetaHandler) {
      currentVideoEl.removeEventListener('loadedmetadata', loadedMetaHandler);
      currentVideoEl = null;
      loadedMetaHandler = null;
    }
    videoEl.value = null;

    status.value = 'disconnected';
  }

  /**
   * 重新连接
   */
  function reconnect(host: string, port: number, udid: string, deviceType: string, screenIndex?: number, codec: string = 'jpeg'): void {
    console.log(`[WebSocket] Reconnecting with codec=${codec}`);
    retryCount = 0;
    connect(host, port, udid, deviceType, screenIndex, codec);
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
        if (videoMode.value && now - streamSummaryLast >= 5000) {
          console.debug('[stream-diag] browser summary', {
            elapsedMs: performance.now() - streamConnectStarted,
            packets: streamPacketCount,
            bytes: streamBytes,
            fps: fps.value,
            mse: mseDecoder.getDiagnostics(),
          });
          streamPacketCount = 0;
          streamBytes = 0;
          streamSummaryLast = now;
        }
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
    videoMode,
    connect,
    disconnect,
    reconnect,
    resetActivityTime,
    attachVideoEl,
  };
}
