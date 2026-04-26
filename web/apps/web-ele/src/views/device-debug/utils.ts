/**
 * 将屏幕展示区的鼠标坐标转换为设备实际坐标
 *
 * 注意：由于 CSS object-fit: contain，图片可能不填满容器，
 * 需要结合 useScreenInteraction 中的实际渲染区域计算
 */
export function convertToDeviceCoords(
  mouseX: number,
  mouseY: number,
  displayWidth: number,
  displayHeight: number,
  deviceWidth: number,
  deviceHeight: number
): { x: number; y: number } {
  // 边界保护：确保 displayWidth/displayHeight 有效
  if (displayWidth <= 0 || displayHeight <= 0 || deviceWidth <= 0 || deviceHeight <= 0) {
    return { x: 0, y: 0 };
  }

  const scaleX = deviceWidth / displayWidth;
  const scaleY = deviceHeight / displayHeight;

  // 计算坐标并限制在设备屏幕范围内
  const rawX = Math.round(mouseX * scaleX);
  const rawY = Math.round(mouseY * scaleY);

  return {
    x: clamp(rawX, 0, deviceWidth - 1),
    y: clamp(rawY, 0, deviceHeight - 1)
  };
}

/**
 * 边界限制函数（clamp）
 * 将值限制在 [min, max] 范围内
 */
function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * 计算 object-fit: contain 下图片的实际渲染区域
 *
 * 返回值：
 * - renderedWidth/Height: 图片实际渲染尺寸
 * - offsetX/Y: 图片相对于元素的偏移（居中）
 * - isValidClick: 点击是否在图片渲染区域内
 */
export function calculateContainRenderArea(
  elementWidth: number,
  elementHeight: number,
  imageNaturalWidth: number,
  imageNaturalHeight: number,
  mouseX: number,
  mouseY: number
): {
  renderedWidth: number;
  renderedHeight: number;
  offsetX: number;
  offsetY: number;
  isValidClick: boolean;
  adjustedX: number;
  adjustedY: number;
} {
  // 边界保护
  if (elementWidth <= 0 || elementHeight <= 0 || imageNaturalWidth <= 0 || imageNaturalHeight <= 0) {
    return {
      renderedWidth: elementWidth,
      renderedHeight: elementHeight,
      offsetX: 0,
      offsetY: 0,
      isValidClick: false,
      adjustedX: 0,
      adjustedY: 0
    };
  }

  // object-fit: contain 的缩放逻辑：使用较小的缩放比例
  const scaleX = elementWidth / imageNaturalWidth;
  const scaleY = elementHeight / imageNaturalHeight;
  const scale = Math.min(scaleX, scaleY);

  // 实际渲染尺寸
  const renderedWidth = imageNaturalWidth * scale;
  const renderedHeight = imageNaturalHeight * scale;

  // 偏移量（图片居中显示）
  const offsetX = (elementWidth - renderedWidth) / 2;
  const offsetY = (elementHeight - renderedHeight) / 2;

  // 调整后的鼠标坐标（相对于渲染图片）
  const adjustedX = mouseX - offsetX;
  const adjustedY = mouseY - offsetY;

  // 检查点击是否在渲染区域内
  const isValidClick =
    adjustedX >= 0 &&
    adjustedX <= renderedWidth &&
    adjustedY >= 0 &&
    adjustedY <= renderedHeight;

  return {
    renderedWidth,
    renderedHeight,
    offsetX,
    offsetY,
    isValidClick,
    adjustedX,
    adjustedY
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