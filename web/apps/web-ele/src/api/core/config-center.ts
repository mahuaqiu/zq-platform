import { requestClient } from '#/api/request';

/**
 * 配置中心相关类型定义
 */
export interface ConfigCenterItem {
  id: string;
  key: string;
  /** JSON 对象字符串，如 {"充许":"允许"} */
  value: string;
  remark?: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

export interface ConfigCenterItemCreateInput {
  key: string;
  value: string;
  remark?: string;
}

export interface ConfigCenterItemUpdateInput {
  value: string;
  remark?: string;
}

export interface ConfigCenterItemListParams {
  page?: number;
  pageSize?: number;
  key?: string;
  remark?: string;
}

export interface ConfigCenterBatchDeleteInput {
  ids: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface KeyValuePair {
  key: string;
  value: string;
}

/**
 * 获取配置项列表（分页）
 */
export async function getConfigItemListApi(params?: ConfigCenterItemListParams) {
  return requestClient.get<PaginatedResponse<ConfigCenterItem>>(
    '/api/core/config-center',
    { params },
  );
}

/**
 * 创建配置项
 */
export async function createConfigItemApi(data: ConfigCenterItemCreateInput) {
  return requestClient.post<ConfigCenterItem>('/api/core/config-center', data);
}

/**
 * 更新配置项（key 不可修改）
 */
export async function updateConfigItemApi(
  itemId: string,
  data: ConfigCenterItemUpdateInput,
) {
  return requestClient.put<ConfigCenterItem>(
    `/api/core/config-center/${itemId}`,
    data,
  );
}

/**
 * 删除配置项（软删除）
 */
export async function deleteConfigItemApi(itemId: string) {
  return requestClient.delete<{ status: string; message: string }>(
    `/api/core/config-center/${itemId}`,
  );
}

/**
 * 批量删除配置项
 */
export async function batchDeleteConfigItemApi(
  data: ConfigCenterBatchDeleteInput,
) {
  return requestClient.post<{
    status: string;
    success_count: number;
    fail_count: number;
  }>('/api/core/config-center/batch/delete', data);
}

/**
 * 校验配置键是否已存在
 */
export async function checkConfigKeyApi(key: string, excludeId?: string) {
  return requestClient.get<{ exists: boolean }>(
    '/api/core/config-center/check/key',
    { params: excludeId ? { key, exclude_id: excludeId } : { key } },
  );
}

/**
 * 把 value JSON 字符串解析为键值对数组；解析失败返回空数组
 */
export function parseConfigValue(value: string): KeyValuePair[] {
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return [];
    }
    return Object.entries(parsed).map(([k, v]) => ({
      key: k,
      value: typeof v === 'string' ? v : String(v),
    }));
  } catch {
    return [];
  }
}

/**
 * 把键值对数组序列化为 value JSON 字符串（保持编辑顺序）
 */
export function buildConfigValue(pairs: KeyValuePair[]): string {
  const obj: Record<string, string> = {};
  for (const pair of pairs) {
    obj[pair.key] = pair.value;
  }
  return JSON.stringify(obj, null, 2);
}
