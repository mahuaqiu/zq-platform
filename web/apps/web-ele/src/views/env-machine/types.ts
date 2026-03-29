/**
 * 设备类型
 */
export type DeviceType = 'windows' | 'mac' | 'ios' | 'android';

/**
 * 设备状态
 */
export type DeviceStatus = 'online' | 'using' | 'offline';

/**
 * 标签允许的前缀列表
 */
export const ALLOWED_TAG_PREFIXES = ['windows', 'web', 'android', 'ios', 'mac'] as const;

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

/**
 * 校验单个标签格式
 * 规则：
 * - 必须小写
 * - 前缀必须是允许列表之一
 * - 下划线后必须有内容
 */
export function validateSingleTag(tag: string): { valid: boolean; error: string } {
  if (!tag) {
    return { valid: false, error: '标签不能为空' };
  }

  if (tag !== tag.toLowerCase()) {
    return { valid: false, error: '标签必须小写' };
  }

  const prefix = tag.split('_')[0];
  if (!ALLOWED_TAG_PREFIXES.includes(prefix as any)) {
    return { valid: false, error: `标签前缀必须是 ${ALLOWED_TAG_PREFIXES.join('/')} 之一` };
  }

  // 检查下划线后是否有内容
  if (tag.includes('_')) {
    const suffix = tag.split('_')[1];
    if (!suffix) {
      return { valid: false, error: '标签下划线后必须有内容' };
    }
  }

  return { valid: true, error: '' };
}

/**
 * 校验 mark 字段（多个标签用逗号分隔）
 * 支持英文逗号、中文逗号、顿号作为分隔符
 */
export function validateMarkField(mark: string): { valid: boolean; error: string } {
  if (!mark) {
    return { valid: true, error: '' }; // 空 mark 是允许的
  }

  // 支持多种分隔符：英文逗号、中文逗号、顿号
  const tags = mark.split(/[,,、]/).map((t) => t.trim());
  for (const tag of tags) {
    if (!tag) continue;
    const result = validateSingleTag(tag);
    if (!result.valid) {
      return { valid: false, error: `标签 "${tag}" 不合法：${result.error}` };
    }
  }

  return { valid: true, error: '' };
}