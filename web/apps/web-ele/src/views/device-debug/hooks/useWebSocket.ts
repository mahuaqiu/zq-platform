import { onUnmounted, ref, shallowRef } from 'vue';

import { ElMessage } from 'element-plus';

import type { WebSocketCloseInfo, WebSocketStatus, ScreenSize } from '../types';
import { buildWebSocketUrl } from '../utils';
import { detectFrameType, FrameType } from '../utils/stream';
import { useMseDecoder } from './useMseDecoder';
import { useMJPEGRenderer } from './useMJPEGRenderer';

const MAX_RETRIES = 3;
const RETRY_INTERVAL = 2000; // 2秒
const IDLE_TIMEOUT = 900000; // 15分钟 = 900秒

export function useWebSocket() {
  const status = ref<WebSocketStatus>('disconnected');
  const screenshotBase64 = ref('');
  const screenSize = ref<ScreenSize>({ width: 0, height: 0 });
  const fps = ref(0);
  const closeInfo = ref<WebSocketCloseInfo | null>(null);
  const errorMessage = ref('');

  let ws: WebSocket | null = null;
  let websocketGeneration = 0;
  let retryCount = 0;
  let fpsFrameCount = 0;
  let fpsLastSecond = 0;
  let fpsTimer: ReturnType<typeof setInterval> | null = null;
  let idleTimer: ReturnType<typeof setTimeout> | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let lastActivityTime = Date.now();
  let activityPending = false;
  let binaryMessageQueue: Promise<void> = Promise.resolve();

  // 是否已从 worker 的 meta 文本帧拿到真机原生分辨率作为坐标基准。
  // 鸿蒙推流会降采样（推流尺寸≠真机尺寸），此时坐标基准必须用 meta 里的
  // 真机分辨率，而不能用推流图像尺寸；置 true 后不再让图像/视频尺寸覆盖 screenSize。
  let hasMeta = false;

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
    onFallback: () => {
      fallbackToJpeg('MSE/JMuxer 不支持或初始化失败');
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
      if (!hasMeta && el.videoWidth > 0 && el.videoHeight > 0) {
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
  let fallbackRequestInProgress = false;

  function fallbackToJpeg(reason: string): void {
    if (fallbackRequestInProgress || savedCodec === 'jpeg') return;
    fallbackRequestInProgress = true;
    console.warn(`[WebSocket] H264 fallback to JPEG: ${reason}`);
    videoMode.value = false;
    mseDecoder.dispose();
    reconnect(
      savedHost,
      savedPort,
      savedUdid,
      savedDeviceType,
      savedScreenIndex,
      'jpeg',
    );
  }

  /**
   * 重置活动时间（用户操作时调用）
   */
  function resetActivityTime(): void {
    lastActivityTime = Date.now();
    activityPending = true;
    sendActivitySignal();
    if (ws && status.value === 'connected') {
      scheduleIdleDisconnect();
    }
  }

  /**
   * 向 Worker 报告用户活动。推流只负责发送画面，不会自动续期空闲时间。
   */
  function sendActivitySignal(): void {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    try {
      ws.send(JSON.stringify({ type: 'activity' }));
      activityPending = false;
    } catch {
      // 连接切换期间发送失败，等下一次 onopen 再补发。
    }
  }

  /**
   * 开始空闲超时检测。使用一次性定时器，避免每分钟轮询带来的延迟。
   */
  function startIdleTimer(): void {
    stopIdleTimer();
    lastActivityTime = Date.now();
    scheduleIdleDisconnect();
  }

  function scheduleIdleDisconnect(): void {
    stopIdleTimer();
    const remaining = Math.max(
      1000,
      IDLE_TIMEOUT - (Date.now() - lastActivityTime),
    );
    idleTimer = setTimeout(() => {
      const elapsed = Date.now() - lastActivityTime;
      if (elapsed >= IDLE_TIMEOUT && ws && status.value === 'connected') {
        console.log('WebSocket 因 15 分钟无操作已自动断开');
        disconnect();
        return;
      }
      if (ws && status.value === 'connected') {
        scheduleIdleDisconnect();
      }
    }, remaining);
  }

  /**
   * 停止超时检测
   */
  function stopIdleTimer(): void {
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  }

  function stopRetryTimer(): void {
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  }

  /**
   * 连接 WebSocket
   */
  function connect(
    host: string,
    port: number,
    udid: string,
    deviceType: string,
    screenIndex?: number,
    codec: string = 'jpeg',
    preserveRetryCount = false,
  ): void {
    const generation = ++websocketGeneration;
    // 保存参数用于重连
    savedHost = host;
    savedPort = port;
    savedUdid = udid;
    savedDeviceType = deviceType;
    savedScreenIndex = screenIndex;
    savedCodec = codec;
    if (!preserveRetryCount) {
      retryCount = 0;
      stopRetryTimer();
    }
    if (codec === 'h264') {
      fallbackRequestInProgress = false;
    }

    // 新连接重置坐标基准来源：未收到 meta 前回退用推流尺寸（兼容非鸿蒙平台）。
    hasMeta = false;

    console.log(
      `[WebSocket] Connecting to ${host}:${port}, deviceType=${deviceType}, codec=${codec}`,
    );
    binaryMessageQueue = Promise.resolve();

    // 关闭旧连接（使用 code=1000 表示正常关闭，不触发自动重连）
    if (ws) {
      const oldWs = ws;
      ws = null;
      oldWs.close(1000);
    }

    // 根据 codec 决定渲染模式：H264 → <video>(MSE)，JPEG/MJPEG → <img>
    const isH264 = codec === 'h264';
    if (isH264) {
      // 进入 MSE 模式前先销毁旧的 jmuxer 实例，避免重复初始化
      // 10fps 只作为没有可靠时间信息时的兜底帧率；鸿蒙分支会按消息到达
      // 间隔生成媒体时长，Windows 仍沿用原有固定时长逻辑。
      mseDecoder.setFrameRate(10);
      mseDecoder.setPlaybackProfile(
        deviceType === 'harmony_mobile' || deviceType === 'harmony_pc'
          ? 'harmony'
          : 'default',
      );
      mseDecoder.dispose();
    }
    videoMode.value = isH264;

    status.value = 'connecting';
    errorMessage.value = '';
    closeInfo.value = null;

    const url = buildWebSocketUrl(
      host,
      port,
      udid,
      deviceType,
      screenIndex,
      codec,
    );
    const socket = new WebSocket(url);
    ws = socket;
    socket.binaryType = 'arraybuffer';

    socket.onopen = () => {
      if (generation !== websocketGeneration) return;
      status.value = 'connected';
      retryCount = 0;
      fpsFrameCount = 0;
      fpsLastSecond = Date.now();
      startFpsTimer();
      startIdleTimer(); // 启动超时检测
      if (activityPending) {
        sendActivitySignal();
      }

      // H264 模式：连接建立后初始化 MSE 解码器（此时 video 元素应已通过 attachVideoEl 绑定）
      if (isH264) {
        mseDecoder.init();
      }
    };

    const processBinaryFrame = (
      arrayBuffer: ArrayBuffer,
      receivedAt = performance.now(),
    ): void => {
      if (
        !arrayBuffer ||
        arrayBuffer.byteLength === 0 ||
        generation !== websocketGeneration
      ) {
        return;
      }

      const frameType = detectFrameType(arrayBuffer);
      switch (frameType) {
        case FrameType.H264:
          mseDecoder.feedFrame(arrayBuffer, receivedAt);
          break;

        case FrameType.MJPEG:
          mjpegRenderer.render(arrayBuffer);
          break;

        case FrameType.JPEG:
        default: {
          const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
          const url = URL.createObjectURL(blob);

          if (
            screenshotBase64.value &&
            screenshotBase64.value.startsWith('blob:')
          ) {
            URL.revokeObjectURL(screenshotBase64.value);
          }

          screenshotBase64.value = url;

          if (!hasMeta) {
            const img = new Image();
            img.onload = () => {
              if (!hasMeta) {
                screenSize.value = { width: img.width, height: img.height };
              }
            };
            img.src = url;
          }
          break;
        }
      }

      fpsFrameCount++;
    };

    socket.onmessage = (event) => {
      if (generation !== websocketGeneration) return;
      // 文本帧：worker 在流开头下发的 JSON 元数据，用于携带真机原生分辨率、
      // 编解码回退通知与锁屏等待状态。
      if (typeof event.data === 'string') {
        try {
          const meta = JSON.parse(event.data);
          if (meta && meta.type === 'codec_fallback' && meta.codec === 'jpeg') {
            fallbackToJpeg(meta.reason || 'Worker H264 链路不可用');
            return;
          }
          if (meta && meta.type === 'waiting_unlock') {
            // 鸿蒙设备锁屏时 worker 会等待解锁（最长 300s）后才推流，
            // 必须显式提示，否则页面表现为无任何反馈的静默黑屏。
            ElMessage.warning(meta.message || '设备已锁屏，解锁后自动开始推流');
            return;
          }
          if (
            meta &&
            meta.type === 'meta' &&
            meta.width > 0 &&
            meta.height > 0
          ) {
            screenSize.value = { width: meta.width, height: meta.height };
            hasMeta = true;
          }
        } catch (e) {
          console.warn('[WebSocket] 解析 meta 文本帧失败:', e);
        }
        return;
      }
      // 少数浏览器或旧 WebView 即使设置了 binaryType，也会把二进制帧交付为 Blob。
      // 先转换后重新走同一个处理分支，避免把 H.264 误判为 JPEG/Unknown。
      if (typeof Blob !== 'undefined' && event.data instanceof Blob) {
        const blob = event.data;
        const receivedAt = performance.now();
        binaryMessageQueue = binaryMessageQueue
          .then(async () => {
            const arrayBuffer = await blob.arrayBuffer();
            if (generation !== websocketGeneration) return;
            processBinaryFrame(arrayBuffer, receivedAt);
          })
          .catch((error) => {
            if (generation === websocketGeneration) {
              console.error('[WebSocket] 二进制 Blob 转换失败:', error);
            }
          });
        return;
      }

      if (event.data instanceof ArrayBuffer) {
        const arrayBuffer = event.data;
        const receivedAt = performance.now();
        binaryMessageQueue = binaryMessageQueue
          .then(() => {
            processBinaryFrame(arrayBuffer, receivedAt);
          })
          .catch((error) => {
            if (generation === websocketGeneration) {
              console.error('[WebSocket] 二进制帧处理失败:', error);
            }
          });
      }
    };

    socket.onclose = (event) => {
      if (generation !== websocketGeneration) return;
      if (ws === socket) {
        ws = null;
      }
      stopFpsTimer();
      stopIdleTimer(); // 停止超时检测
      status.value = 'disconnected';
      closeInfo.value = { code: event.code, reason: event.reason };

      console.log(
        `[WebSocket] Connection closed: code=${event.code}, reason=${event.reason}, retryCount=${retryCount}`,
      );
      // 非正常关闭时尝试重连
      if (event.code !== 1000 && retryCount < MAX_RETRIES) {
        retryCount++;
        const retryGeneration = generation;
        retryTimer = setTimeout(() => {
          retryTimer = null;
          if (
            retryGeneration === websocketGeneration &&
            retryCount <= MAX_RETRIES
          ) {
            console.log(
              `[WebSocket] Attempting reconnect #${retryCount} with codec=${savedCodec}`,
            );
            connect(
              savedHost,
              savedPort,
              savedUdid,
              savedDeviceType,
              savedScreenIndex,
              savedCodec,
              true,
            );
          }
        }, RETRY_INTERVAL);
      } else if (event.code !== 1000 && retryCount >= MAX_RETRIES) {
        // 达到最大重试次数后显示错误
        ElMessage.error('WebSocket 连接失败，已尝试重连 3 次，请检查设备状态');
      }
    };

    socket.onerror = (event) => {
      if (generation !== websocketGeneration) return;
      status.value = 'error';
      errorMessage.value = 'WebSocket 连接失败';
      console.error(`[WebSocket] Error:`, event);
    };
  }

  /**
   * 断开连接
   */
  function disconnect(): void {
    websocketGeneration++;
    stopRetryTimer();
    if (ws) {
      retryCount = MAX_RETRIES; // 阻止自动重连
      const socket = ws;
      ws = null;
      socket.close(1000);
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
  function reconnect(
    host: string,
    port: number,
    udid: string,
    deviceType: string,
    screenIndex?: number,
    codec: string = 'jpeg',
  ): void {
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
