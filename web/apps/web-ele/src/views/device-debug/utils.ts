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
 * 构建 WebSocket URL
 */
export function buildWebSocketUrl(host: string, port: number, udid: string): string {
  return `ws://${host}:${port}/ws/screen/${udid}`;
}