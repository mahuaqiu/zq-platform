/**
 * 将屏幕展示区的鼠标坐标转换为设备实际坐标
 */
export function convertToDeviceCoords(
  mouseX: number,
  mouseY: number,
  displayWidth: number,
  displayHeight: number,
  deviceWidth: number,
  deviceHeight: number
): { x: number; y: number } {
  const scaleX = deviceWidth / displayWidth;
  const scaleY = deviceHeight / displayHeight;
  return {
    x: Math.round(mouseX * scaleX),
    y: Math.round(mouseY * scaleY)
  };
}

/**
 * 判断是否为移动端设备
 */
export function isMobileDevice(deviceType: string): boolean {
  return ['ios', 'android'].includes(deviceType);
}

/**
 * 判断是否为桌面端设备
 */
export function isDesktopDevice(deviceType: string): boolean {
  return ['windows', 'mac'].includes(deviceType);
}

/**
 * 格式化时间（HH:MM:SS）
 */
export function formatTime(): string {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

/**
 * 格式化操作历史显示文本
 */
export function formatHistoryDisplay(type: string, params: Record<string, any>): string {
  switch (type) {
    case 'screenshot':
      return ''; // 截图操作不显示在历史中
    case 'click':
      return `点击(${params.x}, ${params.y})`;
    case 'swipe':
      return '滑动';
    case 'input':
      const text = params.text || '';
      return `输入"${text.length > 10 ? text.slice(0, 10) + '...' : text}"`;
    case 'press':
      return `${params.key}`;
    case 'unlock_screen':
      return `解锁屏幕`;
    default:
      return type;
  }
}

/**
 * 格式化设备调试页 Tab 标题
 * - Windows/Mac: 显示完整 IP（如 192.168.0.102）
 * - iOS/Android: 显示 IP 后两位 + SN 后 4 位（如 0.102-5554）
 */
export function formatDeviceDebugTitle(ip: string, deviceSn: string, deviceType: string): string {
  if (!ip) return '设备调试';

  if (isDesktopDevice(deviceType)) {
    // Windows/Mac 显示完整 IP
    return ip;
  }

  // iOS/Android: IP 后两位 + SN 后 4 位
  const ipParts = ip.split('.');
  const ipSuffix = ipParts.length >= 2
    ? `${ipParts[ipParts.length - 2]}.${ipParts[ipParts.length - 1]}`
    : ip;
  const snSuffix = deviceSn ? deviceSn.slice(-4) : '----';
  return `${ipSuffix}-${snSuffix}`;
}

/**
 * 构建 WebSocket URL
 * Worker 平台格式：
 * - iOS: /ws/screen/ios/{udid}
 * - Android: /ws/screen/android/{udid}
 * - Windows: /ws/screen/windows/windows_screen?monitor={screenIndex+1}
 * - Mac: /ws/screen/mac/mac_screen?monitor={screenIndex+1}
 */
export function buildWebSocketUrl(
  host: string,
  port: number,
  udid: string,
  deviceType: string,
  screenIndex?: number
): string {
  const platform = deviceType.toLowerCase();

  // 桌面端传递 monitor 参数（mss索引：1=主屏，2=副屏）
  if (platform === 'windows' || platform === 'mac') {
    const monitor = screenIndex !== undefined ? screenIndex + 1 : 1;
    return `ws://${host}:${port}/ws/screen/${platform}/${platform}_screen?monitor=${monitor}`;
  }

  // 移动端使用 UDID
  return `ws://${host}:${port}/ws/screen/${platform}/${udid}`;
}