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
  if (!data || data.byteLength < 2) {
    return FrameType.Unknown;
  }

  const bytes = new Uint8Array(data);

  // 优先检测 H.264 (带帧类型前缀: 0x01=SPS/PPS, 0x02=IDR, 0x03=P)
  const firstByte = bytes[0] ?? 0;
  if (firstByte >= 0x01 && firstByte <= 0x03) {
    return FrameType.H264;
  }

  // 检测 JPEG/MJPEG 魔数: FFD8
  const magic = ((bytes[0] ?? 0) << 8) | (bytes[1] ?? 0);
  if (magic === 0xFFD8) {
    // 检测是否为 MJPEG：需要检测到多个连续的 FFD8
    // JPEG: FFD8 FF... (只有一个 FFD8)
    // MJPEG: FFD8 FF... FFD8 FF... (多个 FFD8)
    let jpegCount = 0;
    for (let i = 0; i < data.byteLength - 1; i += 2) {
      if ((((bytes[i] ?? 0) << 8) | (bytes[i + 1] ?? 0)) === 0xFFD8) {
        jpegCount++;
        if (jpegCount >= 2) {
          return FrameType.MJPEG;
        }
      }
    }
    return FrameType.JPEG;
  }

  // 兼容未带 Worker 帧类型前缀的裸 Annex-B H.264。
  let nalOffset = -1;
  if (bytes.length >= 4 && bytes[0] === 0 && bytes[1] === 0) {
    if (bytes[2] === 1) {
      nalOffset = 3;
    } else if (bytes[2] === 0 && bytes[3] === 1) {
      nalOffset = 4;
    }
  }
  if (nalOffset >= 0 && nalOffset < bytes.length) {
    const nalType = (bytes[nalOffset] ?? 0) & 0x1f;
    if (nalType >= 1 && nalType <= 23) {
      return FrameType.H264;
    }
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
