// 帧类型检测工具

export enum FrameType {
  Unknown = 'unknown',
  JPEG = 'jpeg',
  MJPEG = 'mjpeg',
  H264 = 'h264',
}

/**
 * 检测帧数据类型
 * @param data WebSocket 接收的二进制数据
 */
export function detectFrameType(data: ArrayBuffer): FrameType {
  if (!data || data.byteLength < 4) {
    return FrameType.Unknown;
  }

  const view = new DataView(data);

  // 优先检测 H.264 (带帧类型前缀: 0x01=SPS/PPS, 0x02=IDR, 0x03=P)
  const firstByte = view.getUint8(0);
  if (firstByte >= 0x01 && firstByte <= 0x03) {
    return FrameType.H264;
  }

  // 检测 JPEG/MJPEG 魔数: FFD8
  const magic = view.getUint16(0);
  if (magic === 0xFFD8) {
    // 检测是否为 MJPEG (多个 FFD8 连在一起)
    if (data.byteLength >= 6 && view.getUint8(2) === 0xFF) {
      return FrameType.MJPEG;
    }
    return FrameType.JPEG;
  }

  // H.264 SPS (NAL unit type = 7)
  if (magic === 0x0001 && view.getUint8(4) === 0x07) {
    return FrameType.H264;
  }

  return FrameType.Unknown;
}

/**
 * 从 H.264 数据中提取 NAL 单元
 */
export function extractNalUnit(data: ArrayBuffer): { type: number; data: Uint8Array } | null {
  const view = new DataView(data);
  if (data.byteLength < 5) return null;

  const frameType = view.getUint8(0);
  const nalData = new Uint8Array(data, 1);

  return { type: frameType, data: nalData };
}

/**
 * 构建 WebSocket URL
 */
export function buildScreenWsUrl(
  host: string,
  port: number,
  platform: string,
  deviceId: string,
  monitor: number = 1,
  codec: string = 'jpeg'
): string {
  const isDesktop = platform === 'windows' || platform === 'mac';
  const path = isDesktop
    ? `/ws/screen/${platform}/${platform}_screen?monitor=${monitor}&codec=${codec}`
    : `/ws/screen/${platform}/${deviceId}?codec=${codec}`;

  return `ws://${host}:${port}${path}`;
}