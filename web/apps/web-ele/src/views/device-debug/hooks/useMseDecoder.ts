import JMuxer from 'jmuxer';
import { onUnmounted } from 'vue';
import type { Ref } from 'vue';

/**
 * MSE H264 解码器 Hook（基于 jmuxer）
 *
 * 用途：替代 WebCodecs VideoDecoder。WebCodecs 的 VideoDecoder 是 Secure Context-only API，
 * 在 HTTP 内网（非 localhost）部署下 `window.VideoDecoder` 运行时为 undefined，必然失败。
 * MSE（MediaSource + SourceBuffer）不是 Secure Context-only API，HTTP 下可用。
 *
 * 数据格式（与 win-recorder / worker 完全契合，无需改协议）：
 * - 帧类型前缀：1 字节 (0x01=SPS/PPS, 0x02=IDR, 0x03=P帧)
 * - 数据格式：Annex-B（带起始码 0x00 0x00 0x00 0x01）
 *
 * jmuxer 原生接收 Annex-B，内部完成 NAL 分片、avcC 封装、fMP4 打包、SPS 尺寸解析，
 * 因此前端无需再做 Annex-B→AVCC 转换、buildDescription、SPPS 解析等易错逻辑。
 */

export interface MseDecoderOptions {
  /** 由 ScreenDisplay 暴露的 <video> 元素引用 */
  videoEl: Ref<HTMLVideoElement | null>;
  /** 推流帧率，需与编码器一致（默认 10） */
  fps?: number;
  /** 解码器就绪回调 */
  onReady?: () => void;
  /** jmuxer 内部错误回调（非致命，仅告警） */
  onError?: (e: unknown) => void;
  /** 不可恢复错误回调，触发降级到 JPEG 模式 */
  onFallback?: () => void;
}

export function useMseDecoder(options: MseDecoderOptions) {
  // 关键：经 window. 缓存全局 API，避免 esbuild/Vite 打包时把全局标识符当模块绑定，
  // 导致运行时 ReferenceError（WebCodecs 方案的同类教训）。
  // typeof window.MediaSource 在不支持的浏览器下返回 undefined，可用于降级判断。
  const _MediaSource =
    (window as any).MediaSource as typeof MediaSource | undefined;

  let jmuxer: JMuxer | null = null;
  let fallback = false;
  let feedCount = 0;
  let fedBytes = 0;
  let presentedFrameCount = 0;
  let firstPresentedAtMs: number | null = null;
  let lastPresentedMediaTime: number | null = null;
  let videoFrameDiagnosticsStarted = false;

  // buffer 主动清理定时器。
  // 背景：jmuxer 自带的 clearBuffer 依赖 <video>.currentTime 推进来计算清理边界，
  // 但实时推流下 <video> 可能停滞（autoplay 受限、卡帧），导致 currentTime 不增长，
  // jmuxer 内部清理失效，MSE SourceBuffer 单调增长 → 浏览器内存暴涨。
  // 这里不依赖 jmuxer 内部清理，直接监控 SourceBuffer.buffered 主动 remove 旧数据。
  let bufferCleanupTimer: ReturnType<typeof setInterval> | null = null;
  // buffer 最大保留时长（秒）：超过此长度的已播放数据将被回收
  const MAX_BUFFER_SECONDS = 8;
  const LIVE_EDGE_TARGET_SECONDS = 0.1;
  const LIVE_EDGE_INITIAL_BUFFER_SECONDS = 0.25;
  const LIVE_EDGE_HARD_LAG_SECONDS = 0.35;
  const LIVE_EDGE_RATE_LAG_SECONDS = 0.2;
  const LIVE_EDGE_RATE_RECOVER_SECONDS = 0.12;
  const LIVE_EDGE_MAX_PLAYBACK_RATE = 1.2;
  const LIVE_EDGE_SYNC_INTERVAL_MS = 250;
  const LIVE_EDGE_SEEK_INTERVAL_MS = 1000;
  let liveEdgeTimer: ReturnType<typeof setInterval> | null = null;
  let liveEdgeInitialized = false;
  let lastLiveEdgeSeekAt = 0;
  /**
   * 初始化 jmuxer。必须在 <video> 元素已挂载后调用。
   * 不支持 MediaSource 或 onUnsupportedCodec 时触发降级。
   */
  function init(): void {
    if (fallback) return;
    if (typeof _MediaSource === 'undefined') {
      console.warn('[MSEDecoder] 浏览器不支持 MediaSource，触发降级');
      fallback = true;
      options.onFallback?.();
      return;
    }

    const el = options.videoEl.value;
    if (!el) {
      console.warn('[MSEDecoder] video 元素尚未挂载，跳过初始化');
      return;
    }

    // jmuxer 的类型定义未声明 onUnsupportedCodec，构造时用 as 断言补齐。
    // onUnsupportedCodec 在 SourceBuffer 无法处理 codec 时触发，是降级的关键信号。
    const jmuxerOptions = {
      node: el,
      mode: 'video' as const,
      // 实时推流：收到帧立即 flush，延迟最低
      flushingTime: 0,
      // JMuxer 默认 maxDelay 为 500ms，会抵消外部 live-edge 追帧。
      maxDelay: 200,
      // 自动清理已播放 buffer，防止长时间推流内存暴涨
      clearBuffer: true,
      fps: options.fps ?? 10,
      debug: false,
      onReady: () => {
        options.onReady?.();
      },
      onError: (data: unknown) => {
        console.error('[MSEDecoder] jmuxer error:', data);
        options.onError?.(data);
      },
      onUnsupportedCodec: () => {
        console.error('[MSEDecoder] 不支持的 codec，触发降级');
        fallback = true;
        options.onFallback?.();
      },
    };

    try {
      jmuxer = new JMuxer(jmuxerOptions as ConstructorParameters<typeof JMuxer>[0]);
      // 启动 buffer 主动清理（防内存泄漏，见字段声明处说明）
      startBufferCleanup();
      startLiveEdgeSync();
      startVideoFrameDiagnostics();
    } catch (e) {
      console.error('[MSEDecoder] jmuxer 创建失败，触发降级:', e);
      fallback = true;
      options.onFallback?.();
    }
  }

  /**
   * 喂入一帧 H264 数据
   * @param data WebSocket 原始 ArrayBuffer，含帧类型前缀
   *
   * 帧类型前缀（与 win-recorder encode_frame 输出一致）：
   * - 0x01: SPS/PPS 参数集
   * - 0x02: IDR 关键帧
   * - 0x03: P 预测帧
   *
   * jmuxer 会按 NAL 起始码自动识别参数集/关键帧/预测帧，无需手动区分。
   */
  function feedFrame(data: ArrayBuffer): void {
    if (!data || data.byteLength < 2) return;
    if (!jmuxer) return;

    // 去掉 1 字节帧类型前缀，剩余即为 Annex-B（带 00 00 00 01 起始码）
    const payload = new Uint8Array(data, 1);
    feedCount += 1;
    fedBytes += payload.byteLength;
    jmuxer.feed({ video: payload });
  }

  /**
   * 从 jmuxer 内部取出 video 的 SourceBuffer 引用。
   * jmuxer 把 SourceBuffer 存在 bufferControllers.video.sourceBuffer，
   * 类型定义未暴露，用 as 断言访问。
   */
  function getSourceBuffer(): SourceBuffer | null {
    const anyJmuxer = jmuxer as unknown as {
      bufferControllers?: Record<string, { sourceBuffer?: SourceBuffer }>;
    };
    return anyJmuxer.bufferControllers?.video?.sourceBuffer ?? null;
  }

  function getDiagnostics() {
    const el = options.videoEl.value;
    const sb = getSourceBuffer();
    const ranges: Array<{ start: number; end: number }> = [];
    if (sb) {
      for (let index = 0; index < sb.buffered.length; index++) {
        ranges.push({ start: sb.buffered.start(index), end: sb.buffered.end(index) });
      }
    }
    const bufferedEnd = ranges.length > 0 ? ranges[ranges.length - 1]!.end : null;
    return {
      initialized: Boolean(jmuxer),
      feedCount,
      fedBytes,
      presentedFrameCount,
      firstPresentedAtMs,
      lastPresentedMediaTime,
      videoFrameCallbackSupported: Boolean(
        el && 'requestVideoFrameCallback' in el,
      ),
      videoCurrentTime: el?.currentTime ?? null,
      videoReadyState: el?.readyState ?? null,
      videoPaused: el?.paused ?? null,
      playbackRate: el?.playbackRate ?? null,
      bufferedRanges: ranges,
      bufferedEnd,
      liveEdgeLagSeconds: bufferedEnd !== null && el ? bufferedEnd - el.currentTime : null,
      sourceBufferUpdating: sb?.updating ?? null,
    };
  }

  function startVideoFrameDiagnostics(): void {
    const el = options.videoEl.value as
      | (HTMLVideoElement & {
          requestVideoFrameCallback?: (
            callback: (now: number, metadata: VideoFrameCallbackMetadata) => void,
          ) => number;
        })
      | null;
    if (!el || videoFrameDiagnosticsStarted || !el.requestVideoFrameCallback) return;

    videoFrameDiagnosticsStarted = true;
    const callback = (_now: number, metadata: VideoFrameCallbackMetadata) => {
      if (!jmuxer || options.videoEl.value !== el) return;
      presentedFrameCount += 1;
      firstPresentedAtMs ??= performance.now();
      lastPresentedMediaTime = metadata.mediaTime;
      if (presentedFrameCount === 1 || presentedFrameCount % 30 === 0) {
        console.info('[MSEDecoder] video frame presented', {
          presentedFrameCount,
          mediaTime: metadata.mediaTime,
          presentedFrames: metadata.presentedFrames,
          expectedDisplayTime: metadata.expectedDisplayTime,
          currentTime: el.currentTime,
          bufferedEnd: getBufferedEnd(),
        });
      }
      el.requestVideoFrameCallback?.(callback);
    };
    el.requestVideoFrameCallback(callback);
  }
  function getBufferedEnd(): number | null {
    const sourceBuffer = getSourceBuffer();
    if (!sourceBuffer || sourceBuffer.buffered.length === 0) return null;
    return sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);
  }

  function syncToLiveEdge(): void {
    const el = options.videoEl.value;
    const bufferedEnd = getBufferedEnd();
    if (!el || bufferedEnd === null) return;

    const now = performance.now();
    const lag = bufferedEnd - el.currentTime;
    const targetTime = Math.max(0, bufferedEnd - LIVE_EDGE_TARGET_SECONDS);
    const shouldInitialSeek =
      !liveEdgeInitialized &&
      el.readyState >= HTMLMediaElement.HAVE_METADATA &&
      bufferedEnd >= LIVE_EDGE_INITIAL_BUFFER_SECONDS;
    const shouldHardSeek =
      liveEdgeInitialized &&
      lag > LIVE_EDGE_HARD_LAG_SECONDS &&
      now - lastLiveEdgeSeekAt >= LIVE_EDGE_SEEK_INTERVAL_MS;

    if (shouldInitialSeek || shouldHardSeek) {
      try {
        el.currentTime = targetTime;
        lastLiveEdgeSeekAt = now;
        liveEdgeInitialized = true;
        el.playbackRate = 1;
        console.info('[MSEDecoder] live edge seek', {
          reason: shouldInitialSeek ? 'initial' : 'lag',
          lagSeconds: lag,
          bufferedEnd,
          targetTime,
        });
      } catch (error) {
        console.warn('[MSEDecoder] live edge seek failed:', error);
      }
    }

    if (lag > LIVE_EDGE_RATE_LAG_SECONDS && lag <= LIVE_EDGE_HARD_LAG_SECONDS) {
      const catchUpRate = Math.min(
        LIVE_EDGE_MAX_PLAYBACK_RATE,
        1 + Math.max(0.05, Math.min(0.2, (lag - LIVE_EDGE_RATE_RECOVER_SECONDS) * 0.35)),
      );
      if (Math.abs(el.playbackRate - catchUpRate) > 0.01) {
        el.playbackRate = catchUpRate;
        console.info('[MSEDecoder] live edge catch-up rate', {
          lagSeconds: lag,
          playbackRate: catchUpRate,
        });
      }
    } else if (lag < LIVE_EDGE_RATE_RECOVER_SECONDS && el.playbackRate !== 1) {
      el.playbackRate = 1;
    }

    if (el.paused && el.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      void el.play().catch(() => {
        // 自动播放策略拒绝时，下一次同步继续尝试。
      });
    }
  }

  function startLiveEdgeSync(): void {
    if (liveEdgeTimer) return;
    liveEdgeTimer = setInterval(syncToLiveEdge, LIVE_EDGE_SYNC_INTERVAL_MS);
  }

  function stopLiveEdgeSync(): void {
    if (liveEdgeTimer) {
      clearInterval(liveEdgeTimer);
      liveEdgeTimer = null;
    }
  }
  /**
   * 启动 buffer 主动清理定时器
   *
   * 每 2 秒检查一次 SourceBuffer：
   * - 找到当前播放位置（currentTime），保留 [currentTime, currentTime + MAX_BUFFER_SECONDS]
   * - 把 currentTime 之前、且距今超过 cleanOffset 的旧数据 remove 掉
   * - 若 currentTime 停滞（<video> 未真正播放），改用 buffered.end 作为兜底清理点，
   *   避免清理逻辑跟着停滞导致内存只增不减
   *
   * 清理时检查 sourceBuffer.updating，避免与 jmuxer 自身 append 冲突。
   */
  function startBufferCleanup(): void {
    if (bufferCleanupTimer) return;
    bufferCleanupTimer = setInterval(() => {
      const sb = getSourceBuffer();
      const el = options.videoEl.value;
      if (!sb || !el || sb.updating) return;

      const buffered = sb.buffered;
      if (!buffered || buffered.length === 0) return;

      // 播放游标：优先 currentTime，停滞时用 buffered 末尾兜底
      const playHead = el.currentTime > 0 ? el.currentTime : buffered.end(buffered.length - 1);

      for (let i = 0; i < buffered.length; i++) {
        const start = buffered.start(i);
        const end = buffered.end(i);
        // 清理 playHead 之前超过 MAX_BUFFER_SECONDS 的旧数据，保留近 MAX_BUFFER_SECONDS 秒
        const cleanEnd = playHead - MAX_BUFFER_SECONDS;
        if (cleanEnd > start) {
          const removeEnd = Math.min(cleanEnd, end);
          if (removeEnd > start && !sb.updating) {
            try {
              sb.remove(start, removeEnd);
            } catch {
              // 清理失败忽略，下个周期重试
            }
            return; // 一次只 remove 一段，等 updateend 后下周期继续
          }
        }
      }
    }, 2000);
  }

  /**
   * 停止 buffer 主动清理定时器
   */
  function stopBufferCleanup(): void {
    if (bufferCleanupTimer) {
      clearInterval(bufferCleanupTimer);
      bufferCleanupTimer = null;
    }
  }

  /**
   * 释放 jmuxer 资源
   */
  function dispose(): void {
    stopBufferCleanup();
    stopLiveEdgeSync();
    liveEdgeInitialized = false;
    lastLiveEdgeSeekAt = 0;
    if (jmuxer) {
      try {
        jmuxer.destroy();
      } catch {
        // 忽略销毁时的错误
      }
      jmuxer = null;
    }
    fallback = false;
    feedCount = 0;
    fedBytes = 0;
    presentedFrameCount = 0;
    firstPresentedAtMs = null;
    lastPresentedMediaTime = null;
    videoFrameDiagnosticsStarted = false;
  }

  onUnmounted(dispose);

  return {
    init,
    feedFrame,
    getDiagnostics,
    dispose,
  };
}
