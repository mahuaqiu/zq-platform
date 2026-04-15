import { requestClient } from '#/api/request';

/**
 * 配置模板
 */
export interface ConfigTemplate {
  id: string;
  name: string;
  content: string;
  note?: string;
  sort?: number;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 配置预览机器
 */
export interface ConfigPreviewMachine {
  id: string;
  ip: string;
  device_type: string;
  namespace: string;
  status: string;
  current_config?: string;
}

/**
 * 配置预览响应
 */
export interface ConfigPreviewResponse {
  total_count: number;
  online_count: number;
  offline_count: number;
  machines: ConfigPreviewMachine[];
}

/**
 * 下发请求参数
 */
export interface DeployRequest {
  template_id: string;
  machine_ids?: string[];
  namespace?: string;
  device_type?: string;
}

/**
 * 下发详情
 */
export interface DeployDetail {
  machine_id: string;
  ip: string;
  status: string;
  message: string;
}

/**
 * 下发响应
 */
export interface DeployResponse {
  success_count: number;
  failed_count: number;
  skipped_count: number;
  details: DeployDetail[];
}

/**
 * 获取配置模板列表
 */
export async function getConfigTemplateListApi() {
  return requestClient.get<ConfigTemplate[]>('/api/core/env-machine-config/template');
}

/**
 * 创建配置模板
 */
export async function createConfigTemplateApi(data: Partial<ConfigTemplate>) {
  return requestClient.post<ConfigTemplate>('/api/core/env-machine-config/template', data);
}

/**
 * 更新配置模板
 */
export async function updateConfigTemplateApi(id: string, data: Partial<ConfigTemplate>) {
  return requestClient.put<ConfigTemplate>(`/api/core/env-machine-config/template/${id}`, data);
}

/**
 * 删除配置模板
 */
export async function deleteConfigTemplateApi(id: string) {
  return requestClient.delete(`/api/core/env-machine-config/template/${id}`);
}

/**
 * 获取配置预览
 */
export async function getConfigPreviewApi(namespace?: string, deviceType?: string, ip?: string) {
  return requestClient.get<ConfigPreviewResponse>('/api/core/env-machine-config/preview', {
    params: { namespace, device_type: deviceType, ip },
  });
}

/**
 * 下发配置
 */
export async function deployConfigApi(data: DeployRequest) {
  return requestClient.post<DeployResponse>('/api/core/env-machine-config/deploy', data);
}