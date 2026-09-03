/**
 * env-machine 页面共享逻辑（index.vue / list.vue 共用，勿在单页内复制这些实现）
 *
 * 两条约定：
 * 1. 扩展信息（extra_message）按标签存储设备账号配置；标签支持英文逗号、中文逗号、
 *    顿号分隔（与 types.ts 的 validateMarkField 一致），启用校验要求每个标签都有对应配置。
 * 2. API 请求失败由请求层全局拦截器统一弹一次错误提示（优先展示后端 detail），
 *    页面 catch 只做状态恢复与 console 记录，不再弹第二个提示。
 */
import { DEVICE_TYPE_OPTIONS, STATUS_OPTIONS } from '../types';

/**
 * 扩展信息示例文案（"标签名" 会被替换为实际标签），用于启用校验失败的提示弹窗
 */
export const EXTRA_MESSAGE_EXAMPLE = `{
  "标签名": {
    "username": "账号",
    "password": "密码"
  }
}`;

/**
 * 拆分标签：支持英文逗号、中文逗号、顿号分隔
 */
export function splitMarks(mark: null | string | undefined): string[] {
  return (mark || '')
    .split(/[,，、]/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

/**
 * 递归清理 JSON 中的 key/value 首尾空格
 */
export function trimJsonKeysAndValues(
  obj: Record<string, any>,
): Record<string, any> {
  const result: Record<string, any> = {};
  for (const key of Object.keys(obj)) {
    const trimmedKey = key.trim();
    const value = obj[key];
    if (typeof value === 'string') {
      result[trimmedKey] = value.trim();
    } else if (typeof value === 'object' && value !== null) {
      result[trimmedKey] = trimJsonKeysAndValues(value);
    } else {
      result[trimmedKey] = value;
    }
  }
  return result;
}

/**
 * 解析扩展信息 JSON 字符串，返回清理空格后的对象；
 * 空字符串返回空对象，格式非法返回 null
 */
export function parseExtraMessage(raw: string): null | Record<string, any> {
  const content = (raw || '').trim();
  if (!content) {
    return {};
  }
  try {
    return trimJsonKeysAndValues(JSON.parse(content));
  } catch {
    return null;
  }
}

/**
 * 校验扩展信息是否包含每个标签对应的账号配置，返回缺失的标签列表（空数组表示通过）。
 * JSON 非法时视为全部缺失（调用方一般已先做过格式校验）。
 */
export function getMissingExtraMessageTags(
  raw: string,
  mark: string,
): string[] {
  const tags = splitMarks(mark);
  if (tags.length === 0) {
    return [];
  }
  const parsed = parseExtraMessage(raw);
  if (parsed === null) {
    return tags;
  }
  return tags.filter(
    (tag) =>
      !Object.prototype.hasOwnProperty.call(parsed, tag) ||
      typeof parsed[tag] !== 'object',
  );
}

/**
 * 生成"无法启用"提示文案
 */
export function buildEnableBlockMessage(
  mark: string,
  missingTags: string[],
): string {
  const missingText =
    missingTags.length > 0 ? `，当前缺失：${missingTags.join('、')}` : '';
  const exampleKey = missingTags[0] || splitMarks(mark)[0] || '标签名';
  return [
    '需要填入扩展信息（机器使用的账号信息）才能启用设备。',
    '',
    `扩展信息需要包含标签 "${mark}" 对应的账号配置${missingText}。`,
    '',
    '示例格式：',
    EXTRA_MESSAGE_EXAMPLE.replace('标签名', exampleKey),
  ].join('\n');
}

/**
 * 获取状态文本
 */
export function getStatusText(status: string): string {
  const opt = STATUS_OPTIONS.find((o) => o.value === status);
  return opt?.label || status;
}

/**
 * 获取状态样式类（类名定义在各页面的 scoped style 中）
 */
export function getStatusClass(status: string): string {
  const statusMap: Record<string, string> = {
    online: 'env-status-success',
    using: 'env-status-orange',
    offline: 'env-status-warning',
    upgrading: 'env-status-upgrading',
  };
  return statusMap[status] || '';
}

/**
 * 格式化扩展信息（表格列展示用）
 */
export function formatExtraMessage(extra: Record<string, any>): string {
  const parts: string[] = [];
  if (extra.CPU) parts.push(`CPU: ${extra.CPU}`);
  if (extra.RAM) parts.push(`RAM: ${extra.RAM}`);
  if (extra.device_model) parts.push(extra.device_model);
  return parts.join(', ') || JSON.stringify(extra);
}

/**
 * 获取设备类型文本
 */
export function getDeviceTypeText(type: string): string {
  const opt = DEVICE_TYPE_OPTIONS.find((o) => o.value === type);
  return opt?.label || type;
}
