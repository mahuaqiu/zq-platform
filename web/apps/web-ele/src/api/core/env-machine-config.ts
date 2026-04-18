import { requestClient } from '#/api/request';

/**
 * 配置模板
 */
export interface ConfigTemplate {
  id: string;
  name: string;
  type: 'config' | 'script';
  script_name?: string;
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
  config_status: string;  // synced/pending/updating/offline
  config_version?: string;
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
}

/**
 * 下发详情
 */
export interface DeployDetail {
  machine_id: string;
  ip: string;
  status: string;  // success/failed
  error_message?: string;
}

/**
 * 下发响应
 */
export interface DeployResponse {
  success_count: number;
  failed_count: number;
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
export async function getConfigTemplateListApi() {
  return requestClient.get<PaginatedResponse<ConfigTemplate>>('/api/core/config-template');
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
  namespace?: string,
  deviceType?: string,
  ip?: string
) {
  return requestClient.get<ConfigPreviewResponse>('/api/core/config-template/preview', {
    params: { template_id: templateId, namespace, device_type: deviceType, ip },
  });
}

/**
 * 下发配置
 */
export async function deployConfigApi(data: DeployRequest) {
  return requestClient.post<DeployResponse>('/api/core/config-template/deploy', data);
}