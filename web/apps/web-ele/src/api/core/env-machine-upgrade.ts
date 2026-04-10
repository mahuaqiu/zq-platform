import { requestClient } from '#/api/request';

/**
 * 升级配置
 */
export interface UpgradeConfig {
  id: string;
  device_type: string;
  version: string;
  download_url: string;
  note?: string;
}

/**
 * Worker 升级信息
 */
export interface WorkerUpgradeInfo {
  version: string;
  download_url: string;
}

/**
 * 批量升级请求参数
 */
export interface BatchUpgradeParams {
  machine_ids?: string[];
  namespace?: string;
  device_type?: string;
}

/**
 * 升级详情
 */
export interface UpgradeDetail {
  machine_id: string;
  ip: string;
  status: string;
  message: string;
}

/**
 * 批量升级响应
 */
export interface BatchUpgradeResponse {
  upgraded_count: number;
  waiting_count: number;
  skipped_count: number;
  failed_count: number;
  details: UpgradeDetail[];
}

/**
 * 升级预览响应
 */
export interface UpgradePreviewResponse {
  upgradable_count: number;
  waiting_count: number;
  latest_count: number;
  offline_count: number;
  machines: UpgradePreviewMachine[];
}

/**
 * 升级预览机器
 */
export interface UpgradePreviewMachine {
  id: string;
  ip: string;
  device_type: string;
  version: string;
  status: string;
  upgrade_status: string;
}

/**
 * 升级队列项
 */
export interface UpgradeQueueItem {
  id: string;
  machine_id: string;
  ip: string;
  device_type: string;
  target_version: string;
  status: string;
  created_at?: string;
}

/**
 * 获取升级配置列表
 */
export async function getUpgradeConfigListApi() {
  return requestClient.get<UpgradeConfig[]>('/api/core/env/upgrade/config');
}

/**
 * 更新升级配置
 */
export async function updateUpgradeConfigApi(id: string, data: Partial<UpgradeConfig>) {
  return requestClient.put<UpgradeConfig>(`/api/core/env/upgrade/config/${id}`, data);
}

/**
 * Worker 获取升级信息
 */
export async function getWorkerUpgradeInfoApi(deviceType: string) {
  return requestClient.get<WorkerUpgradeInfo>('/api/core/env/upgrade/worker/info', {
    params: { device_type: deviceType },
  });
}

/**
 * Worker 手动触发升级
 */
export async function workerStartUpgradeApi(machineId: string, version: string) {
  return requestClient.post('/api/core/env/upgrade/worker/start', {
    machine_id: machineId,
    version,
  });
}

/**
 * 批量升级
 */
export async function batchUpgradeApi(data: BatchUpgradeParams) {
  return requestClient.post<BatchUpgradeResponse>('/api/core/env/upgrade/batch', data);
}

/**
 * 升级预览
 */
export async function getUpgradePreviewApi(namespace?: string, deviceType?: string) {
  return requestClient.get<UpgradePreviewResponse>('/api/core/env/upgrade/preview', {
    params: { namespace, device_type: deviceType },
  });
}

/**
 * 升级队列查询
 */
export async function getUpgradeQueueApi(namespace?: string, status?: string) {
  return requestClient.get<{ items: UpgradeQueueItem[]; total: number }>('/api/core/env/upgrade/queue', {
    params: { namespace, status },
  });
}

/**
 * 移除升级队列
 */
export async function removeUpgradeQueueApi(queueId: string) {
  return requestClient.delete(`/api/core/env/upgrade/queue/${queueId}`);
}