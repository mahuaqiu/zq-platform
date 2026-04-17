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
  namespace?: string;  // 改为可选，空表示查询全部
  device_type?: string;
  ip?: string;
  asset_number?: string;
  mark?: string;
  available?: boolean;
  status?: string;
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
  extra_message?: Record<string, any>;
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

/**
 * 日志响应
 */
export interface MachineLogResponse {
  content: string;
  lines: number;
  truncated: boolean;
}

/**
 * 获取设备日志
 */
export async function getMachineLogsApi(machineId: string, lines: number = 400) {
  return requestClient.get<MachineLogResponse>(`/api/core/env/machine/${machineId}/logs`, {
    params: { lines },
  });
}

/**
 * 调试操作参数
 */
export interface DebugActionParams {
  action_type: 'click' | 'swipe' | 'input' | 'press' | 'screenshot';
  params: Record<string, any>;
}

/**
 * 调试操作结果
 */
export interface DebugActionResult {
  success: boolean;
  result?: {
    screenshot_base64?: string;
    error?: string;
  };
}

/**
 * 设备调试操作
 */
export async function debugDeviceActionApi(
  deviceId: string,
  params: DebugActionParams,
) {
  return requestClient.post<DebugActionResult>(
    `/api/core/env/${deviceId}/debug-action`,
    params,
  );
}