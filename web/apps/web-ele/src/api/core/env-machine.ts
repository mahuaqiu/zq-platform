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
 * 日志查询参数（三选一，互斥）
 */
export interface MachineLogQueryParams {
  /** lines 模式：返回最后 N 行（范围 1-2000，默认 400） */
  lines?: number;
  /** request_id 模式：grep 搜索指定 request_id 的日志 */
  request_id?: string;
  /** time_range 模式：开始时间 ISO 8601 格式 */
  start_time?: string;
  /** time_range 模式：结束时间 ISO 8601 格式（需与 start_time 同时提供） */
  end_time?: string;
}

/**
 * 日志响应
 */
export interface MachineLogResponse {
  content: string;
  /** 返回的日志行数（从响应头 X-Log-Count 获取） */
  log_count: number;
  /** 扫描的日志文件数（从响应头 X-Files-Scanned 获取） */
  files_scanned: number;
}

/**
 * 获取设备日志
 * 支持三种查询模式（互斥）：
 * - lines: 返回最后 N 行
 * - request_id: grep 搜索指定 request_id
 * - time_range: 按时间区间过滤（最多 5 分钟）
 */
export async function getMachineLogsApi(
  machineId: string,
  params: MachineLogQueryParams | number = { lines: 400 },
) {
  // 支持旧调用方式：直接传 lines 数值
  const queryParams: MachineLogQueryParams =
    typeof params === 'number' ? { lines: params } : params;

  return requestClient.get<MachineLogResponse>(
    `/api/core/env/machine/${machineId}/logs`,
    { params: queryParams },
  );
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
  timeout?: number,
) {
  return requestClient.post<DebugActionResult>(
    `/api/core/env/${deviceId}/debug-action`,
    params,
    timeout ? { timeout } : undefined,
  );
}

/**
 * 获取单个设备详情
 */
export async function getEnvMachineDetailApi(id: string) {
  return requestClient.get<EnvMachine>(`/api/core/env/${id}`);
}