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

type MsePlaybackProfile = 'default' | 'harmony';

interface PendingMseFrame {
  data: ArrayBuffer;
  receivedAtMs: number;
}

export function useMseDecoder(options: MseDecoderOptions) {
  // 关键：经 window. 缓存全局 API，避免 esbuild/Vite 打包时把全局标识符当模块绑定，
  // 导致运行时 ReferenceError（WebCodecs 方案的同类教训）。
  // typeof window.MediaSource 在不支持的浏览器下返回 undefined，可用于降级判断。
  const _MediaSource = (window as any).MediaSource as
    | typeof MediaSource
    | undefined;

  let jmuxer: JMuxer | null = null;
  let jmuxerNode: HTMLVideoElement | null = null;
  // Windows 保持原有播放参数；鸿蒙 H.264 使用独立的时间轴和清理策略。
  let playbackProfile: MsePlaybackProfile = 'default';
  // MediaSource 还未 sourceopen 时，JMuxer 可能已经创建但还不能建立
  // SourceBuffer；首批 config/IDR 必须等 sourceopen 后再喂入。
  let mseReady = false;
  let configuredFps = Math.max(1, options.fps ?? 10);
  // WebSocket 可能先收到缓存的 SPS/PPS、IDR，再完成 video/JMuxer 初始化。
  // 静止画面不会产生后续帧，因此初始化前不能直接丢弃这些首帧。
  let pendingFrames: PendingMseFrame[] = [];
  const MAX_PENDING_FRAMES = 16;
  let fallback = false;
  let feedCount = 0;
  let fedBytes = 0;
  let feedPacketCounts = { config: 0, idr: 0, p: 0, other: 0 };
  let firstFeedAtMs: number | null = null;
  let lastFeedAtMs: number | null = null;
  let presentedFrameCount = 0;
  let firstPresentedAtMs: number | null = null;
  let lastPresentedAtMs: number | null = null;
  let lastPresentedMediaTime: number | null = null;
  let missingVideoFrameCount = 0;
  let videoFrameDiagnosticsStarted = false;
  let sourceBufferNode: SourceBuffer | null = null;
  let sourceBufferEventHandlers: Array<[string, EventListener]> = [];
  let sourceBufferUpdateStartCount = 0;
  let sourceBufferUpdateEndCount = 0;
  let sourceBufferErrorCount = 0;
  let sourceBufferAbortCount = 0;
  let lastSourceBufferUpdateEndAtMs: number | null = null;
  let lastVideoReceivedAtMs: number | null = null;
  let lastHarmonyFrameDurationMs: number | null = null;
  let harmonyFrameDurationMs: number | null = null;
  let harmonyFrameDurationSamples: number[] = [];
  let harmonyMediaTimeSeconds = 0;
  let harmonyKeyframePositions: number[] = [];
  let harmonyCleanupPending = false;

  // Windows 使用额外的 buffer 清理定时器。鸿蒙使用自己的保守清理，避免
  // JMuxer 在没有设备时间戳时把当前可播放区间误判为旧数据。
  let bufferCleanupTimer: ReturnType<typeof setInterval> | null = null;
  // buffer 最大保留时长（秒）：超过此长度的已播放数据将被回收
  const MAX_BUFFER_SECONDS = 8;
  // 鸿蒙官方流没有媒体时间戳，按 WebSocket 消息到达间隔估算媒体时长。
  // 使用滚动中位数抑制网络突发，同时允许编码器帧率随设备状态变化。
  const HARMONY_MIN_FRAME_DURATION_MS = 20;
  const HARMONY_MAX_FRAME_DURATION_MS = 250;
  const HARMONY_DURATION_SAMPLE_COUNT = 8;
  const HARMONY_BUFFER_KEEP_SECONDS = 15;
  // H.264 直通只在画面变化时产生回调；缓冲目标需要足够小，
  // 否则设备刚恢复活动时，浏览器会先播放一段旧 P 帧。
  const LIVE_EDGE_TARGET_SECONDS = 0.05;
  // 静止画面可能只有一个 IDR，首段缓冲不足 250ms 时也要立即起播。
  const LIVE_EDGE_INITIAL_BUFFER_SECONDS = 0.01;
  const LIVE_EDGE_HARD_LAG_SECONDS = 0.25;
  const LIVE_EDGE_RATE_LAG_SECONDS = 0.1;
  const LIVE_EDGE_RATE_RECOVER_SECONDS = 0.06;
  const LIVE_EDGE_MAX_PLAYBACK_RATE = 1.35;
  const LIVE_EDGE_SYNC_INTERVAL_MS = 100;
  const LIVE_EDGE_SEEK_INTERVAL_MS = 500;
  let liveEdgeTimer: ReturnType<typeof setInterval> | null = null;
  let liveEdgeInitialized = false;
  let lastLiveEdgeSeekAt = 0;

  function tryStartPlayback(el: HTMLVideoElement): void {
    if (el.paused && el.readyState >= HTMLMediaElement.HAVE_METADATA) {
      void el.play().catch(() => {
        // 自动播放策略拒绝时，由后续媒体事件和同步定时器继续尝试。
      });
    }
  }

  function detachSourceBufferDiagnostics(): void {
    if (!sourceBufferNode) return;
    for (const [eventName, handler] of sourceBufferEventHandlers) {
      sourceBufferNode.removeEventListener(eventName, handler);
    }
    sourceBufferNode = null;
    sourceBufferEventHandlers = [];
  }

  function attachSourceBufferDiagnostics(): void {
    const sourceBuffer = getSourceBuffer();
    if (!sourceBuffer || sourceBuffer === sourceBufferNode) return;
    detachSourceBufferDiagnostics();
    sourceBufferNode = sourceBuffer;
    const handlers: Array<[string, EventListener]> = [
      [
        'updatestart',
        () => {
          sourceBufferUpdateStartCount += 1;
        },
      ],
      [
        'updateend',
        () => {
          sourceBufferUpdateEndCount += 1;
          lastSourceBufferUpdateEndAtMs = performance.now();
          harmonyCleanupPending = false;
        },
      ],
      [
        'error',
        () => {
          sourceBufferErrorCount += 1;
          harmonyCleanupPending = false;
        },
      ],
      [
        'abort',
        () => {
          sourceBufferAbortCount += 1;
          harmonyCleanupPending = false;
        },
      ],
    ];
    for (const [eventName, handler] of handlers) {
      sourceBuffer.addEventListener(eventName, handler);
    }
    sourceBufferEventHandlers = handlers;
  }
  /**
   * 初始化 jmuxer。必须在 <video> 元素已挂载后调用。
   * 不支持 MediaSource 或 onUnsupportedCodec 时触发降级。
   */
  function init(): void {
    if (fallback) return;
    if (typeof _MediaSource === 'undefined') {
      fallback = true;
      options.onFallback?.();
      return;
    }

    const el = options.videoEl.value;
    if (!el) {
      return;
    }

    // attachVideoEl 和 WebSocket onopen 可能在同一连接内各触发一次 init，
    // 同一个 video 元素不能重复绑定 JMuxer，否则会产生多个 SourceBuffer。
    if (jmuxer) {
      if (jmuxerNode === el) return;
      dispose();
    }

    // jmuxer 的类型定义未声明 onUnsupportedCodec，构造时用 as 断言补齐。
    // onUnsupportedCodec 在 SourceBuffer 无法处理 codec 时触发，是降级的关键信号。
    const jmuxerOptions = {
      node: el,
      mode: 'video' as const,
      // 鸿蒙的官方回调可能在一次更新期间连续到达，使用短周期统一冲刷，
      // 避免每个 access unit 触发一次播放状态切换；Windows 保持即时冲刷。
      flushingTime: playbackProfile === 'harmony' ? 50 : 0,
      // JMuxer 默认 maxDelay 为 500ms，会抵消外部 live-edge 追帧。
      maxDelay: 200,
      // 鸿蒙使用自己的保守清理；Windows 保持原有的 JMuxer 清理行为。
      clearBuffer: playbackProfile !== 'harmony',
      fps: configuredFps,
      debug: false,
      onReady: () => {
        mseReady = true;
        options.onReady?.();
        const initialFrames = pendingFrames;
        pendingFrames = [];
        for (const frame of initialFrames) {
          feedFrame(frame.data, frame.receivedAtMs);
        }
      },
      onError: (data: unknown) => {
        options.onError?.(data);
      },
      onMissingVideoFrames: () => {
        missingVideoFrameCount += 1;
      },
      onUnsupportedCodec: () => {
        fallback = true;
        options.onFallback?.();
      },
    };

    try {
      jmuxer = new JMuxer(
        jmuxerOptions as ConstructorParameters<typeof JMuxer>[0],
      );
      jmuxerNode = el;
      // 启动 buffer 主动清理（防内存泄漏，见字段声明处说明）
      startBufferCleanup();
      startLiveEdgeSync();
      startVideoFrameDiagnostics();
      tryStartPlayback(el);
    } catch {
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
  function feedFrame(
    data: ArrayBuffer,
    receivedAtMs = performance.now(),
  ): void {
    if (!data || data.byteLength < 2) return;
    if (!jmuxer || !mseReady) {
      if (pendingFrames.length >= MAX_PENDING_FRAMES) {
        pendingFrames.shift();
      }
      pendingFrames.push({
        data: data.slice(0),
        receivedAtMs,
      });
      return;
    }

    const bytes = new Uint8Array(data);
    const hasFramePrefix =
      bytes.length >= 5 &&
      bytes[0]! >= 0x01 &&
      bytes[0]! <= 0x03 &&
      ((bytes[1] === 0 && bytes[2] === 0 && bytes[3] === 1) ||
        (bytes[1] === 0 && bytes[2] === 0 && bytes[3] === 0 && bytes[4] === 1));

    // Worker 协议带 1 字节帧类型前缀；同时兼容裸 Annex-B 输入。
    const payload = hasFramePrefix ? bytes.subarray(1) : bytes;
    if (payload.byteLength < 2) return;

    // jmuxer 只有看到下一个起始码才会提交最后一个 NAL。官方链路的静止画面
    // 可能只发一组 SPS/PPS + IDR，补一个终止起始码让首个关键帧立即进入 MSE。
    const hasTrailingStartCode =
      (payload.length >= 3 &&
        payload[payload.length - 3] === 0 &&
        payload[payload.length - 2] === 0 &&
        payload[payload.length - 1] === 1) ||
      (payload.length >= 4 &&
        payload[payload.length - 4] === 0 &&
        payload[payload.length - 3] === 0 &&
        payload[payload.length - 2] === 0 &&
        payload[payload.length - 1] === 1);
    const muxPayload = hasTrailingStartCode
      ? payload
      : (() => {
          const terminated = new Uint8Array(payload.length + 4);
          terminated.set(payload);
          terminated.set([0, 0, 0, 1], payload.length);
          return terminated;
        })();
    // JMuxer 在未提供 duration 时会把当前 VCL 留在 pendingUnits，等待下一个
    // access unit 来判断边界。静止画面只有首个 IDR 时就永远不会 flush，表现为
    // MSE 已连接但白屏；参数集保持 0，视频包使用估算时长立即产出首帧。
    const packetType = hasFramePrefix ? bytes[0] : 0;
    let duration = 0;
    if (packetType === 0x01) {
      // 新参数集通常意味着一次新的 IDR 起播，不能让下一帧继承上一次
      // 画面变化到现在的长时间间隔。
      lastVideoReceivedAtMs = null;
      harmonyFrameDurationMs = null;
      harmonyFrameDurationSamples = [];
    } else {
      const nominalDuration = Math.max(1, Math.round(1000 / configuredFps));
      if (playbackProfile === 'harmony') {
        let observedDuration = nominalDuration;
        if (lastVideoReceivedAtMs !== null) {
          const interval = receivedAtMs - lastVideoReceivedAtMs;
          if (
            Number.isFinite(interval) &&
            interval >= HARMONY_MIN_FRAME_DURATION_MS &&
            interval <= HARMONY_MAX_FRAME_DURATION_MS
          ) {
            harmonyFrameDurationSamples.push(interval);
            if (
              harmonyFrameDurationSamples.length > HARMONY_DURATION_SAMPLE_COUNT
            ) {
              harmonyFrameDurationSamples.shift();
            }
            if (harmonyFrameDurationSamples.length >= 4) {
              const sortedSamples = [...harmonyFrameDurationSamples].sort(
                (left, right) => left - right,
              );
              harmonyFrameDurationMs = Math.round(
                sortedSamples[Math.floor(sortedSamples.length / 2)]!,
              );
            }
          }
          if (Number.isFinite(interval) && interval > 0) {
            observedDuration = Math.round(
              Math.min(
                HARMONY_MAX_FRAME_DURATION_MS,
                Math.max(HARMONY_MIN_FRAME_DURATION_MS, interval),
              ),
            );
          }
        }
        duration = harmonyFrameDurationMs ?? observedDuration;
        lastHarmonyFrameDurationMs = duration;
      } else {
        duration = nominalDuration;
      }
      lastVideoReceivedAtMs = receivedAtMs;
    }
    feedCount += 1;
    fedBytes += muxPayload.byteLength;
    const feedNow = performance.now();
    firstFeedAtMs ??= feedNow;
    lastFeedAtMs = feedNow;
    if (packetType === 0x01) {
      feedPacketCounts.config += 1;
    } else if (packetType === 0x02) {
      feedPacketCounts.idr += 1;
    } else if (packetType === 0x03) {
      feedPacketCounts.p += 1;
    } else {
      feedPacketCounts.other += 1;
    }
    if (playbackProfile === 'harmony' && packetType === 0x02) {
      // 旧数据只能清理到 IDR 起点，保留下来的首个视频样本才能独立解码。
      harmonyKeyframePositions.push(harmonyMediaTimeSeconds);
    }
    if (playbackProfile === 'harmony' && packetType !== 0x01) {
      harmonyMediaTimeSeconds += duration / 1000;
    }
    jmuxer.feed({ video: muxPayload, duration });
    attachSourceBufferDiagnostics();
    const el = options.videoEl.value;
    if (el) {
      tryStartPlayback(el);
    }
  }

  function setFrameRate(fps: number): void {
    if (Number.isFinite(fps) && fps > 0) {
      configuredFps = fps;
    }
  }

  function setPlaybackProfile(profile: MsePlaybackProfile): void {
    playbackProfile = profile;
  }

  /**
   * 从 jmuxer 内部取出 video 的 SourceBuffer 引用。
   * jmuxer 把 SourceBuffer 存在 bufferControllers.video.sourceBuffer，
   * 类型定义未暴露，用 as 断言访问。
   *
   * 注意：dispose() 后 jmuxer 为 null，此时返回 null 避免访问空对象报错。
   */
  function getSourceBuffer(): SourceBuffer | null {
    if (!jmuxer) return null;
    try {
      const anyJmuxer = jmuxer as unknown as {
        bufferControllers?: Record<string, { sourceBuffer?: SourceBuffer }>;
      };
      return anyJmuxer.bufferControllers?.video?.sourceBuffer ?? null;
    } catch {
      // jmuxer 已销毁或状态异常，返回 null
      return null;
    }
  }

  function getDiagnostics() {
    const el = options.videoEl.value;
    const sb = getSourceBuffer();
    const anyJmuxer = jmuxer as unknown as {
      remuxController?: {
        tracks?: Record<
          string,
          {
            pendingUnits?: { units?: unknown[] };
            dts?: number;
            nextDts?: number;
            mp4track?: { fps?: number };
          }
        >;
      };
      bufferControllers?: Record<
        string,
        {
          queue?: Uint8Array;
          cleaning?: boolean;
        }
      >;
    } | null;
    const videoTrack = anyJmuxer?.remuxController?.tracks?.video;
    const videoBufferController = anyJmuxer?.bufferControllers?.video;
    const ranges: Array<{ start: number; end: number }> = [];
    if (sb) {
      for (let index = 0; index < sb.buffered.length; index++) {
        ranges.push({
          start: sb.buffered.start(index),
          end: sb.buffered.end(index),
        });
      }
    }
    const bufferedEnd =
      ranges.length > 0 ? ranges[ranges.length - 1]!.end : null;
    const now = performance.now();
    return {
      initialized: Boolean(jmuxer),
      feedCount,
      fedBytes,
      feedPacketCounts: { ...feedPacketCounts },
      firstFeedAtMs,
      lastFeedAtMs,
      feedAgeMs: lastFeedAtMs !== null ? now - lastFeedAtMs : null,
      presentedFrameCount,
      firstPresentedAtMs,
      firstPresentedDelayMs:
        firstPresentedAtMs !== null && firstFeedAtMs !== null
          ? firstPresentedAtMs - firstFeedAtMs
          : null,
      lastPresentedAtMs,
      presentedAgeMs:
        lastPresentedAtMs !== null ? now - lastPresentedAtMs : null,
      lastPresentedMediaTime,
      missingVideoFrameCount,
      jmuxerInternal: {
        pendingVideoUnits: videoTrack?.pendingUnits?.units?.length ?? 0,
        videoDts: videoTrack?.dts ?? null,
        videoNextDts: videoTrack?.nextDts ?? null,
        streamFps: videoTrack?.mp4track?.fps ?? null,
        lastHarmonyFrameDurationMs,
        harmonyFrameDurationMs,
        harmonyFrameDurationSampleCount: harmonyFrameDurationSamples.length,
        harmonyMediaTimeSeconds,
        harmonyKeyframeCount: harmonyKeyframePositions.length,
        sourceBufferQueueBytes: videoBufferController?.queue?.byteLength ?? 0,
        sourceBufferCleaning: videoBufferController?.cleaning ?? false,
        sourceBufferUpdateStartCount,
        sourceBufferUpdateEndCount,
        sourceBufferErrorCount,
        sourceBufferAbortCount,
        sourceBufferUpdateEndAgeMs:
          lastSourceBufferUpdateEndAtMs !== null
            ? now - lastSourceBufferUpdateEndAtMs
            : null,
      },
      videoFrameCallbackSupported: Boolean(
        el && 'requestVideoFrameCallback' in el,
      ),
      playbackProfile,
      bufferCleanupMode:
        playbackProfile === 'harmony'
          ? 'harmony-safe-old-buffer'
          : 'direct-source-buffer-remove',
      videoWidth: el?.videoWidth ?? 0,
      videoHeight: el?.videoHeight ?? 0,
      videoCurrentTime: el?.currentTime ?? null,
      videoReadyState: el?.readyState ?? null,
      videoPaused: el?.paused ?? null,
      playbackRate: el?.playbackRate ?? null,
      bufferedRanges: ranges,
      bufferedEnd,
      liveEdgeLagSeconds:
        bufferedEnd !== null && el ? bufferedEnd - el.currentTime : null,
      sourceBufferUpdating: sb?.updating ?? null,
    };
  }

  function startVideoFrameDiagnostics(): void {
    const el = options.videoEl.value as
      | (HTMLVideoElement & {
          requestVideoFrameCallback?: (
            callback: (
              now: number,
              metadata: VideoFrameCallbackMetadata,
            ) => void,
          ) => number;
        })
      | null;
    if (!el || videoFrameDiagnosticsStarted || !el.requestVideoFrameCallback)
      return;

    videoFrameDiagnosticsStarted = true;
    const callback = (_now: number, metadata: VideoFrameCallbackMetadata) => {
      if (!jmuxer || options.videoEl.value !== el) return;
      const presentedAt = performance.now();
      presentedFrameCount += 1;
      firstPresentedAtMs ??= presentedAt;
      lastPresentedAtMs = presentedAt;
      lastPresentedMediaTime = metadata.mediaTime;
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
      } catch {
        // 追帧失败不影响后续数据接收，下个同步周期继续尝试。
      }
    }

    if (lag > LIVE_EDGE_RATE_LAG_SECONDS && lag <= LIVE_EDGE_HARD_LAG_SECONDS) {
      const catchUpRate = Math.min(
        LIVE_EDGE_MAX_PLAYBACK_RATE,
        1 +
          Math.max(
            0.05,
            Math.min(0.2, (lag - LIVE_EDGE_RATE_RECOVER_SECONDS) * 0.35),
          ),
      );
      if (Math.abs(el.playbackRate - catchUpRate) > 0.01) {
        el.playbackRate = catchUpRate;
      }
    } else if (lag < LIVE_EDGE_RATE_RECOVER_SECONDS && el.playbackRate !== 1) {
      el.playbackRate = 1;
    }

    tryStartPlayback(el);
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
   * 启动 buffer 主动清理定时器。
   *
   * 鸿蒙 H.264 只清理远离当前播放位置的旧数据，保留当前播放位置前的
   * 安全窗口；Windows 保持原有的 SourceBuffer 清理逻辑。
   */
  function startBufferCleanup(): void {
    if (bufferCleanupTimer) return;
    bufferCleanupTimer = setInterval(() => {
      const sb = getSourceBuffer();
      const el = options.videoEl.value;
      if (!sb || !el || sb.updating) return;

      if (playbackProfile === 'harmony') {
        cleanupHarmonyBuffer(sb, el);
        return;
      }

      const buffered = sb.buffered;
      if (!buffered || buffered.length === 0) return;

      const playHead =
        el.currentTime > 0 ? el.currentTime : buffered.end(buffered.length - 1);

      for (let i = 0; i < buffered.length; i++) {
        const start = buffered.start(i);
        const end = buffered.end(i);
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

  function cleanupHarmonyBuffer(sb: SourceBuffer, el: HTMLVideoElement): void {
    if (harmonyCleanupPending) return;

    const videoBufferController = (
      jmuxer as unknown as {
        bufferControllers?: Record<
          string,
          {
            cleaning?: boolean;
            queue?: Uint8Array;
          }
        >;
      } | null
    )?.bufferControllers?.video;
    if (
      videoBufferController?.cleaning ||
      (videoBufferController?.queue?.byteLength ?? 0) > 0
    ) {
      return;
    }

    const playHead = el.currentTime;
    if (!Number.isFinite(playHead) || playHead <= HARMONY_BUFFER_KEEP_SECONDS) {
      return;
    }

    const buffered = sb.buffered;
    if (!buffered || buffered.length === 0) return;

    const cutoff = playHead - HARMONY_BUFFER_KEEP_SECONDS;
    const firstStart = buffered.start(0);
    const firstEnd = buffered.end(0);
    harmonyKeyframePositions = harmonyKeyframePositions.filter(
      (keyframePosition) => keyframePosition >= firstStart,
    );

    let safeEnd: number | null = null;
    for (const keyframePosition of harmonyKeyframePositions) {
      if (keyframePosition > cutoff) break;
      if (keyframePosition > firstStart) {
        safeEnd = keyframePosition;
      }
    }
    if (safeEnd === null) return;

    const removeEnd = Math.min(safeEnd, firstEnd);
    if (removeEnd <= firstStart) return;

    try {
      harmonyCleanupPending = true;
      sb.remove(firstStart, removeEnd);
    } catch {
      harmonyCleanupPending = false;
    }
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
    detachSourceBufferDiagnostics();
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
    jmuxerNode = null;
    mseReady = false;
    pendingFrames = [];
    fallback = false;
    feedCount = 0;
    fedBytes = 0;
    feedPacketCounts = { config: 0, idr: 0, p: 0, other: 0 };
    firstFeedAtMs = null;
    lastFeedAtMs = null;
    presentedFrameCount = 0;
    firstPresentedAtMs = null;
    lastPresentedAtMs = null;
    lastPresentedMediaTime = null;
    missingVideoFrameCount = 0;
    lastVideoReceivedAtMs = null;
    lastHarmonyFrameDurationMs = null;
    harmonyFrameDurationMs = null;
    harmonyFrameDurationSamples = [];
    harmonyMediaTimeSeconds = 0;
    harmonyKeyframePositions = [];
    videoFrameDiagnosticsStarted = false;
    sourceBufferUpdateStartCount = 0;
    sourceBufferUpdateEndCount = 0;
    sourceBufferErrorCount = 0;
    sourceBufferAbortCount = 0;
    lastSourceBufferUpdateEndAtMs = null;
    harmonyCleanupPending = false;
  }

  onUnmounted(dispose);

  return {
    init,
    feedFrame,
    setFrameRate,
    setPlaybackProfile,
    getDiagnostics,
    dispose,
  };
}
