import { ref, onUnmounted } from 'vue';

/**
 * WebCodecs H264 解码器 Hook
 * 使用原生 WebCodecs VideoDecoder API 解码 H264 流，替代 broadway-player
 *
 * 数据格式：
 * - 帧类型前缀：1 字节 (0x01=SPS/PPS, 0x02=IDR, 0x03=P帧)
 * - 数据格式：Annex-B（带起始码 0x00 0x00 0x00 0x01）
 * - WebCodecs 需要 AVCC 格式（4 字节长度前缀）
 */

// 帧类型前缀常量
const FRAME_TYPE_SPS_PPS = 0x01;
const FRAME_TYPE_IDR = 0x02;
const FRAME_TYPE_P = 0x03;

// NAL 单元类型
const NAL_TYPE_SPS = 7;
const NAL_TYPE_PPS = 8;
const NAL_TYPE_IDR = 5;

// Annex-B 起始码
const START_CODE_3 = [0x00, 0x00, 0x01];
const START_CODE_4 = [0x00, 0x00, 0x00, 0x01];

export interface WebCodecsDecoderOptions {
  width: number;
  height: number;
  onReady?: () => void;
  onError?: (error: Error) => void;
  onFallback?: () => void;
}

export function useWebCodecsDecoder(options: WebCodecsDecoderOptions) {
  const canvasRef = ref<HTMLCanvasElement | null>(null);
  const isReady = ref(false);

  let decoder: VideoDecoder | null = null;
  let spsData: Uint8Array | null = null;
  let ppsData: Uint8Array | null = null;
  let configWidth = 0;
  let configHeight = 0;
  let fallbackTriggered = false;

  /**
   * 检测浏览器是否支持 WebCodecs VideoDecoder
   */
  function isSupported(): boolean {
    return typeof VideoDecoder !== 'undefined' && typeof VideoDecoder.isConfigSupported === 'function';
  }

  /**
   * 从 Annex-B 数据中提取所有 NAL 单元
   * 识别 4 字节起始码 (0x00 0x00 0x00 0x01) 和 3 字节起始码 (0x00 0x00 0x01)
   */
  function extractNalUnits(data: Uint8Array): Uint8Array[] {
    const nalUnits: Uint8Array[] = [];
    const starts: number[] = [];

    // 找出所有起始码位置
    for (let i = 0; i < data.length - 3; i++) {
      // 检测 4 字节起始码
      if (data[i] === 0x00 && data[i + 1] === 0x00 && data[i + 2] === 0x00 && data[i + 3] === 0x01) {
        starts.push(i + 4); // NAL 单元数据起始位置
        i += 3; // 跳过起始码
      }
      // 检测 3 字节起始码
      else if (data[i] === 0x00 && data[i + 1] === 0x00 && data[i + 2] === 0x01) {
        starts.push(i + 3); // NAL 单元数据起始位置
        i += 2; // 跳过起始码
      }
    }

    // 根据 NAL 单元起始位置切片
    for (let i = 0; i < starts.length; i++) {
      const start = starts[i];
      // 下一个起始码之前的位置就是当前 NAL 单元的结束位置
      const end = i + 1 < starts.length ? starts[i + 1] - (data[starts[i + 1] - 4] === 0x00 ? 4 : 3) : data.length;
      nalUnits.push(data.slice(start, end));
    }

    return nalUnits;
  }

  /**
   * 将 Annex-B 格式转换为 AVCC 格式
   * Annex-B: 起始码(3/4字节) + NAL 数据
   * AVCC: 长度(4字节, 大端) + NAL 数据
   */
  function annexbToAvcc(data: Uint8Array): Uint8Array {
    const nalUnits = extractNalUnits(data);
    // 计算总长度：每个 NAL 单元 + 4 字节长度前缀
    let totalLength = 0;
    for (const unit of nalUnits) {
      totalLength += 4 + unit.length;
    }

    const result = new Uint8Array(totalLength);
    let offset = 0;

    for (const unit of nalUnits) {
      // 写入 4 字节大端长度
      const len = unit.length;
      result[offset] = (len >> 24) & 0xff;
      result[offset + 1] = (len >> 16) & 0xff;
      result[offset + 2] = (len >> 8) & 0xff;
      result[offset + 3] = len & 0xff;
      offset += 4;
      // 写入 NAL 单元数据
      result.set(unit, offset);
      offset += unit.length;
    }

    return result;
  }

  /**
   * 从 SPS 数据中提取 codec 字符串参数
   * 返回格式：avc1.PPCCLL (PP=profile_idc, CC=profile_compat, LL=level_idc)
   */
  function buildCodecString(sps: Uint8Array): string {
    if (sps.length < 4) {
      return 'avc1.42001e'; // 默认 Baseline Profile
    }
    // SPS NAL 单元：第 1 字节是 NAL header, 第 2-4 字节是 profile_idc, profile_compat, level_idc
    const profileIdc = sps[1];
    const profileCompat = sps[2];
    const levelIdc = sps[3];

    const toHex = (n: number) => n.toString(16).padStart(2, '0');
    return `avc1.${toHex(profileIdc)}${toHex(profileCompat)}${toHex(levelIdc)}`;
  }

  /**
   * 构建 AVCC 格式的 description（解码器配置描述）
   * 格式：[1字节 version] + [SPS] + [1字节 SPS 数量] + [2字节 SPS 长度] + [SPS 数据]
   *       + [1字节 PPS 数量] + [2字节 PPS 长度] + [PPS 数据]
   */
  function buildDescription(sps: Uint8Array, pps: Uint8Array): Uint8Array {
    // configurationVersion(1) + profile_idc(1) + profile_compat(1) + level_idc(1)
    // + lengthSizeMinusOne(1) + numOfSPS(1) + SPS_length(2) + SPS_data + numOfPPS(1) + PPS_length(2) + PPS_data
    const totalLen = 1 + 3 + 1 + 1 + 1 + 2 + sps.length + 1 + 2 + pps.length;
    const result = new Uint8Array(totalLen);
    let offset = 0;

    // configurationVersion = 1
    result[offset++] = 0x01;
    // profile_idc
    result[offset++] = sps[1];
    // profile_compatibility
    result[offset++] = sps[2];
    // level_idc
    result[offset++] = sps[3];
    // lengthSizeMinusOne = 3 (表示 4 字节长度前缀) | reserved bits
    result[offset++] = 0xff; // 111111 | 11 (reserved | lengthSizeMinusOne=3)
    // numOfSequenceParameterSets = 1 | reserved bits
    result[offset++] = 0xe1; // 111 | 00001 (reserved | numSPS=1)
    // SPS 长度（2 字节大端）
    result[offset++] = (sps.length >> 8) & 0xff;
    result[offset++] = sps.length & 0xff;
    // SPS 数据（包含 NAL header）
    result.set(sps, offset);
    offset += sps.length;
    // numOfPictureParameterSets = 1
    result[offset++] = 0x01;
    // PPS 长度（2 字节大端）
    result[offset++] = (pps.length >> 8) & 0xff;
    result[offset++] = pps.length & 0xff;
    // PPS 数据（包含 NAL header）
    result.set(pps, offset);

    return result;
  }

  /**
   * 初始化 VideoDecoder
   * 必须在收到 SPS/PPS 和 IDR 帧后调用
   */
  async function initDecoder(): Promise<void> {
    if (!spsData || !ppsData) {
      console.warn('[WebCodecsDecoder] 缺少 SPS 或 PPS 数据，无法初始化解码器');
      return;
    }

    if (decoder) {
      decoder.close();
      decoder = null;
    }

    const codec = buildCodecString(spsData);
    const description = buildDescription(spsData, ppsData);
    const width = configWidth || options.width;
    const height = configHeight || options.height;

    const config: VideoDecoderConfig = {
      codec,
      codedWidth: width,
      codedHeight: height,
      description,
    };

    // 检查配置是否支持
    try {
      const supportResult = await VideoDecoder.isConfigSupported(config);
      if (!supportResult.supported) {
        console.error('[WebCodecsDecoder] 浏览器不支持此解码配置:', config);
        triggerFallback();
        return;
      }
    } catch (e) {
      console.error('[WebCodecsDecoder] 检测配置支持时出错:', e);
      triggerFallback();
      return;
    }

    const canvas = canvasRef.value;
    if (!canvas) {
      console.warn('[WebCodecsDecoder] Canvas 未挂载，无法初始化解码器');
      return;
    }

    const ctx = canvas.getContext('2d');

    decoder = new VideoDecoder({
      output: (frame: VideoFrame) => {
        if (ctx && canvas) {
          // 确保 canvas 尺寸与帧匹配
          if (canvas.width !== frame.displayWidth || canvas.height !== frame.displayHeight) {
            canvas.width = frame.displayWidth;
            canvas.height = frame.displayHeight;
          }
          ctx.drawImage(frame, 0, 0, frame.displayWidth, frame.displayHeight);
        }
        // 每帧渲染后立即释放内存
        frame.close();
      },
      error: (error: Error) => {
        console.error('[WebCodecsDecoder] 解码错误:', error);
        options.onError?.(error);

        // 严重错误时触发降级
        if (error.name === 'NotSupportedError') {
          triggerFallback();
        }
      },
    });

    try {
      decoder.configure(config);
      isReady.value = true;
      console.log('[WebCodecsDecoder] VideoDecoder 初始化成功, codec:', codec);
      options.onReady?.();
    } catch (e) {
      console.error('[WebCodecsDecoder] VideoDecoder 配置失败:', e);
      triggerFallback();
    }
  }

  /**
   * 触发降级回调，切换到 JPEG 模式
   */
  function triggerFallback(): void {
    if (fallbackTriggered) return;
    fallbackTriggered = true;
    console.warn('[WebCodecsDecoder] 触发降级，切换到 JPEG 模式');
    options.onFallback?.();
  }

  /**
   * 解码一帧 H264 数据
   * @param data 包含帧类型前缀的原始数据 (ArrayBuffer)
   *
   * 帧类型前缀：
   * - 0x01: SPS/PPS 参数集
   * - 0x02: IDR 关键帧
   * - 0x03: P 预测帧
   */
  function decodeFrame(data: ArrayBuffer): void {
    if (!data || data.byteLength < 2) return;

    const view = new DataView(data);
    const frameType = view.getUint8(0);
    const payload = new Uint8Array(data, 1);

    switch (frameType) {
      case FRAME_TYPE_SPS_PPS: {
        // 解析 SPS/PPS 参数集
        handleSpsPps(payload);
        break;
      }

      case FRAME_TYPE_IDR: {
        // IDR 关键帧
        if (!decoder || decoder.state === 'closed') {
          // 解码器未初始化，尝试初始化
          if (spsData && ppsData) {
            initDecoder().then(() => {
              if (decoder && decoder.state === 'configured') {
                enqueueFrame(payload, 'key');
              }
            }).catch(() => {
              triggerFallback();
            });
          }
          return;
        }

        if (decoder.state === 'configured') {
          enqueueFrame(payload, 'key');
        }
        break;
      }

      case FRAME_TYPE_P: {
        // P 预测帧
        if (!decoder || decoder.state !== 'configured') {
          // 解码器未就绪，丢弃 P 帧
          return;
        }
        enqueueFrame(payload, 'delta');
        break;
      }

      default:
        console.warn('[WebCodecsDecoder] 未知帧类型:', frameType);
    }
  }

  /**
   * 处理 SPS/PPS 参数集
   * 从 Annex-B 数据中提取并缓存 SPS 和 PPS
   */
  function handleSpsPps(data: Uint8Array): void {
    const nalUnits = extractNalUnits(data);

    for (const nal of nalUnits) {
      if (nal.length === 0) continue;

      const nalType = nal[0] & 0x1f; // NAL 单元类型（低 5 位）

      if (nalType === NAL_TYPE_SPS) {
        spsData = nal;
        console.log('[WebCodecsDecoder] 缓存 SPS, 长度:', nal.length);
      } else if (nalType === NAL_TYPE_PPS) {
        ppsData = nal;
        console.log('[WebCodecsDecoder] 缓存 PPS, 长度:', nal.length);
      }
    }
  }

  /**
   * 将帧数据送入解码器队列
   */
  function enqueueFrame(data: Uint8Array, type: EncodedVideoChunkType): void {
    if (!decoder || decoder.state !== 'configured') return;

    // Annex-B 转 AVCC 格式
    const avccData = annexbToAvcc(data);

    try {
      const chunk = new EncodedVideoChunk({
        type,
        timestamp: performance.now() * 1000, // 微秒单位
        data: avccData,
      });

      decoder.decode(chunk);
    } catch (e) {
      console.error('[WebCodecsDecoder] 入队帧失败:', e);
      options.onError?.(e as Error);
    }
  }

  /**
   * 释放解码器资源
   */
  function dispose(): void {
    if (decoder) {
      try {
        if (decoder.state === 'configured') {
          decoder.flush();
        }
        decoder.close();
      } catch {
        // 忽略关闭时的错误
      }
      decoder = null;
    }
    spsData = null;
    ppsData = null;
    isReady.value = false;
    fallbackTriggered = false;
    console.log('[WebCodecsDecoder] 解码器已释放');
  }

  onUnmounted(dispose);

  return {
    canvasRef,
    isReady,
    isSupported,
    decodeFrame,
    dispose,
  };
}