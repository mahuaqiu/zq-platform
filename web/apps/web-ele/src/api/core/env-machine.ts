import { requestClient } from '#/api/request';

/**
 * 执行机类型定义
 */
export interface EnvMachine {
  id: string;
  namespace: string;
  ip: string;
  port: string;
  mark?: string;
  device_type: string;
  device_sn?: string;
  asset_number?: string;
  available: boolean;
  status: string;
  status_display?: string;
  note?: string;
  extra_message?: Record<string, any>;
  version?: string;
  sync_time?: string;
  last_keepusing_time?: string;
  sort: number;
  is_deleted: boolean;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 查询参数
 */
export interface EnvMachineQueryParams {
  namespace: string;
  device_type?: string;
  ip?: string;
  asset_number?: string;
  mark?: string;
  available?: boolean;
  note?: string;
  page: number;
  page_size: number;
}

/**
 * 创建参数
 */
export interface EnvMachineCreateParams {
  namespace: string;
  device_type: string;
  asset_number: string;
  ip?: string;
  device_sn?: string;
  note?: string;
}

/**
 * 更新参数
 */
export interface EnvMachineUpdateParams {
  asset_number?: string;
  ip?: string;
  device_sn?: string;
  mark?: string;
  available?: boolean;
  note?: string;
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

/**
 * 获取执行机列表
 */
export async function getEnvMachineListApi(params: EnvMachineQueryParams) {
  return requestClient.get<PaginatedResponse<EnvMachine>>('/api/core/env', {
    params,
  });
}

/**
 * 新增执行机
 */
export async function createEnvMachineApi(data: EnvMachineCreateParams) {
  return requestClient.post<EnvMachine>('/api/core/env', data);
}

/**
 * 更新执行机
 */
export async function updateEnvMachineApi(
  id: string,
  data: EnvMachineUpdateParams,
) {
  return requestClient.put<EnvMachine>(`/api/core/env/${id}`, data);
}

/**
 * 删除执行机
 */
export async function deleteEnvMachineApi(id: string) {
  return requestClient.delete(`/api/core/env/${id}`);
}