import { requestClient } from '#/api/request';

/**
 * 配置模板
 */
export interface ConfigTemplate {
  id: string;
  name: string;
  type: 'config' | 'script' | 'command';
  script_name?: string;
  command?: string;
  namespace?: string;
  note?: string;
  config_content: string;
  version: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 配置预览机器
 */
export interface ConfigPreviewMachine {
  id: string;
  ip: string;
  namespace: string;
  device_type: string;
  status: string;
  config_status: string;
  config_version?: string;
  scripts?: Record<string, string>;
}

/**
 * 配置预览响应
 */
export interface ConfigPreviewResponse {
  template_version: string;
  deployable_count: number;
  updating_count: number;
  offline_count: number;
  machines: ConfigPreviewMachine[];
}

/**
 * 下发请求参数
 */
export interface DeployRequest {
  template_id: string;
  machine_ids: string[];
  command?: string;
}

/**
 * 下发详情
 */
export interface DeployDetail {
  machine_id: string;
  ip: string;
  status: string;
  error_message?: string;
  skip_reason?: string;
}

/**
 * 下发响应
 */
export interface DeployResponse {
  task_id?: string;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  details: DeployDetail[];
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

/**
 * 获取配置模板列表
 */
export async function getConfigTemplateListApi(params?: { page?: number; page_size?: number; template_type?: string }) {
  return requestClient.get<PaginatedResponse<ConfigTemplate>>('/api/core/config-template', { params });
}

/**
 * 创建配置模板
 */
export async function createConfigTemplateApi(data: Partial<ConfigTemplate>) {
  return requestClient.post<ConfigTemplate>('/api/core/config-template', data);
}

/**
 * 更新配置模板
 */
export async function updateConfigTemplateApi(id: string, data: Partial<ConfigTemplate>) {
  return requestClient.put<ConfigTemplate>(`/api/core/config-template/${id}`, data);
}

/**
 * 删除配置模板
 */
export async function deleteConfigTemplateApi(id: string) {
  return requestClient.delete(`/api/core/config-template/${id}`);
}

/**
 * 获取配置预览
 */
export async function getConfigPreviewApi(
  templateId: string,
  options?: {
    namespace?: string;
    device_type?: string;
    ip?: string;
    machine_ids?: string[];
  }
) {
  const params: Record<string, string> = { template_id: templateId };
  if (options?.namespace) params.namespace = options.namespace;
  if (options?.device_type) params.device_type = options.device_type;
  if (options?.ip) params.ip = options.ip;
  if (options?.machine_ids?.length) params.machine_ids = options.machine_ids.join(',');
  
  return requestClient.get<ConfigPreviewResponse>('/api/core/config-template/preview', { params });
}

/**
 * 下发配置/脚本/命令
 */
export async function deployConfigApi(data: DeployRequest) {
  return requestClient.post<DeployResponse>('/api/core/config-template/deploy', data);
}

// ========== IP 模板 API ==========

/**
 * IP 模板
 */
export interface MachineSelectionTemplate {
  id: string;
  name: string;
  namespace?: string;
  device_type?: string;
  ip_pattern?: string;
  machine_ids?: string[];
  note?: string;
  version: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 获取 IP 模板列表
 */
export async function getMachineSelectionTemplateListApi(params?: { page?: number; page_size?: number }) {
  return requestClient.get<PaginatedResponse<MachineSelectionTemplate>>('/api/core/machine-selection-template', { params });
}

/**
 * 创建 IP 模板
 */
export async function createMachineSelectionTemplateApi(data: Partial<MachineSelectionTemplate>) {
  return requestClient.post<MachineSelectionTemplate>('/api/core/machine-selection-template', data);
}

/**
 * 更新 IP 模板
 */
export async function updateMachineSelectionTemplateApi(id: string, data: Partial<MachineSelectionTemplate>) {
  return requestClient.put<MachineSelectionTemplate>(`/api/core/machine-selection-template/${id}`, data);
}

/**
 * 删除 IP 模板
 */
export async function deleteMachineSelectionTemplateApi(id: string) {
  return requestClient.delete(`/api/core/machine-selection-template/${id}`);
}

// ========== 命令任务历史 API ==========

/**
 * 命令任务
 */
export interface CommandTask {
  id: string;
  template_id?: string;
  template_type: string;
  template_name: string;
  command?: string;
  machine_count: number;
  status: string;
  success_count: number;
  failed_count: number;
  result_detail?: Array<{
    machine_id: string;
    ip: string;
    device_type: string;
    success: boolean;
    stdout: string;
    stderr: string;
    duration_seconds: number;
  }>;
  sys_create_datetime?: string;
  finished_datetime?: string;
}

/**
 * 获取任务历史列表
 */
export async function getCommandTaskListApi(params?: { page?: number; page_size?: number; template_type?: string }) {
  return requestClient.get<PaginatedResponse<CommandTask>>('/api/core/command-task', { params });
}

/**
 * 获取任务详情
 */
export async function getCommandTaskDetailApi(taskId: string) {
  return requestClient.get<CommandTask>(`/api/core/command-task/${taskId}`);
}

/**
 * 删除任务记录
 */
export async function deleteCommandTaskApi(taskId: string) {
  return requestClient.delete(`/api/core/command-task/${taskId}`);
}
