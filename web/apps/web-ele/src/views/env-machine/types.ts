/**
 * 设备类型
 */
export type DeviceType = 'windows' | 'mac' | 'ios' | 'android';

/**
 * 设备状态
 */
export type DeviceStatus = 'online' | 'using' | 'offline';

/**
 * Namespace 映射
 */
export const NAMESPACE_MAP: Record<string, string> = {
  gamma: 'meeting_gamma',
  app: 'meeting_app',
  av: 'meeting_av',
  public: 'meeting_public',
  manual: 'meeting_manual',
};

/**
 * 设备类型选项
 */
export const DEVICE_TYPE_OPTIONS = [
  { label: 'Windows', value: 'windows' },
  { label: 'Mac', value: 'mac' },
  { label: 'iOS', value: 'ios' },
  { label: 'Android', value: 'android' },
];

/**
 * 状态选项
 */
export const STATUS_OPTIONS = [
  { label: '在线', value: 'online', type: 'success' },
  { label: '使用中', value: 'using', type: 'warning' },
  { label: '离线', value: 'offline', type: 'info' },
];

/**
 * 是否启用选项
 */
export const AVAILABLE_OPTIONS = [
  { label: '是', value: true },
  { label: '否', value: false },
];

/**
 * 判断是否为移动端设备
 */
export function isMobileDevice(deviceType: DeviceType): boolean {
  return deviceType === 'ios' || deviceType === 'android';
}