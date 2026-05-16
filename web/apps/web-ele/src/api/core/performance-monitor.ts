import { requestClient } from '#/api/request';

// ===== 类型定义 =====

export interface ProcessInfo {
  name: string;
  pid: number;
  cpu_usage: number;
  memory_usage: number;
  gpu_usage: number;
}

export interface PerformanceCollect {
  id: string;
  device_id: string;
  name?: string;
  start_time: string;
  end_time?: string;
  interval: number;
  target_processes?: TargetProcessConfig[];
  status: string;
  status_display?: string;
  is_protected: boolean;
}

export interface TargetProcessConfig {
  name: string;
  pids?: number[];
}

export interface PerformanceData {
  id: string;
  collect_id: string;
  timestamp: string;
  relative_time: number;
  cpu_usage?: number;
  gpu_usage?: number;
  commit_memory?: number;
  memory_usage?: number;
  power?: number;
  cpu_speed?: number;
  cpu_temp?: number;
  process_handles?: number;
  upload_speed?: number;
  download_speed?: number;
  target_processes?: ProcessData[];
  top10_cpu?: Top10Process[];
  top10_gpu?: Top10Process[];
}

export interface ProcessData {
  name: string;
  total_cpu: number;
  total_memory: number;
  total_committed_memory?: number;
  total_gpu: number;
  instances: ProcessInstance[];
}

export interface ProcessInstance {
  pid: number;
  cpu: number;
  memory: number;
  committed_memory?: number;
  gpu: number;
}

export interface Top10Process {
  name: string;
  cpu?: number;
  memory?: number;
  gpu?: number;
}

export interface PerformanceTag {
  id: string;
  collect_id: string;
  name: string;
  start_relative_time: number;
  duration: number;
  type: 'peak' | 'mean';
  type_display?: string;
}

export interface PerformanceVersion {
  id: string;
  device_id: string;
  name: string;
  collect_ids: string[];
  is_protected: boolean;
}

export interface CollectStatus {
  is_collecting: boolean;
  collect_id?: string;
  interval?: number;
  target_processes?: TargetProcessConfig[];
  start_time?: string;
  elapsed_seconds?: number;
}

// 标记类型
export interface MarkerCreate {
  collect_id: string;
  name: string;
  start_time: number;
  end_time?: number;
  color: string;
  note?: string;
}

export interface MarkerUpdate {
  name?: string;
  start_time?: number;
  end_time?: number;
  color?: string;
  note?: string;
}

export interface MarkerResponse {
  id: string;
  collect_id: string;
  name: string;
  start_time: number;
  end_time?: number;
  color: string;
  note?: string;
}

// 指标映射类型
export interface MetricMappingCreate {
  hwinfo_key: string;
  display_name: string;
  category: string;
  is_primary: boolean;
  unit?: string;
}

export interface MetricMappingUpdate {
  hwinfo_key?: string;
  display_name?: string;
  category?: string;
  is_primary?: boolean;
  unit?: string;
}

export interface MetricMappingResponse {
  id: string;
  hwinfo_key: string;
  display_name: string;
  category: string;
  is_primary: boolean;
  unit?: string;
}

// 高级指标查询
export interface AdvancedMetricsQuery {
  collect_id: string;
  metric_keys: string[];
  start_time?: number;
  end_time?: number;
}

export interface MetricTimeSeries {
  hwinfo_key: string;
  display_name?: string;
  unit?: string;
  data: { relative_time: number; value: number }[];
}

export interface AdvancedMetricsResponse {
  metrics: Record<string, MetricTimeSeries>;
}

// ===== API 函数 =====

// 进程列表
export async function getProcesses(deviceId: string, search?: string) {
  return requestClient.get<{ processes: ProcessInfo[] }>(
    '/api/core/performance-monitor/processes',
    { params: { device_id: deviceId, search } },
  );
}

// 采集管理
export async function startCollect(params: {
  device_id: string;
  name?: string;
  interval: number;
  target_processes?: TargetProcessConfig[];
}) {
  return requestClient.post<{ collect_id: string; status: string }>(
    '/api/core/performance-monitor/collect/start',
    params,
  );
}

export async function stopCollect(params: {
  collect_id?: string;
  device_id: string;
}) {
  return requestClient.post<{ status: string }>(
    '/api/core/performance-monitor/collect/stop',
    params,
  );
}

export async function getCollectStatus(deviceId: string) {
  return requestClient.get<CollectStatus>(
    `/api/core/performance-monitor/collect/status?device_id=${deviceId}`,
  );
}

export async function getCollectList(params: {
  device_id?: string;
  page: number;
  page_size: number;
}) {
  return requestClient.get<{ total: number; items: PerformanceCollect[] }>(
    '/api/core/performance-monitor/collect/list',
    { params },
  );
}

export async function getCollectDetail(collectId: string) {
  return requestClient.get<PerformanceCollect>(
    `/api/core/performance-monitor/collect/${collectId}`,
  );
}

export async function getCollectData(
  collectId: string,
  params: { page: number; page_size: number },
) {
  return requestClient.get<{ total: number; items: PerformanceData[] }>(
    `/api/core/performance-monitor/collect/${collectId}/data`,
    { params },
  );
}

export async function getLatestData(collectId: string, limit: number = 10) {
  return requestClient.get<{ items: PerformanceData[] }>(
    `/api/core/performance-monitor/collect/${collectId}/latest?limit=${limit}`,
  );
}

// 删除采集记录
export async function deleteCollect(collectId: string) {
  return requestClient.delete<{ status: string }>(
    `/api/core/performance-monitor/collect/${collectId}`,
  );
}

// 设置采集记录保护状态
export async function setCollectProtected(collectId: string, isProtected: boolean) {
  return requestClient.put<{ status: string }>(
    `/api/core/performance-monitor/collect/${collectId}/protected`,
    { is_protected: isProtected },
  );
}

// 标签管理
export async function createTag(params: {
  collect_id: string;
  name: string;
  start_relative_time: number;
  duration: number;
  type: 'peak' | 'mean';
}) {
  return requestClient.post<{ tag_id: string; status: string }>(
    '/api/core/performance-monitor/tag/create',
    params,
  );
}

export async function getTags(collectId: string) {
  return requestClient.get<{ items: PerformanceTag[] }>(
    `/api/core/performance-monitor/tag/list?collect_id=${collectId}`,
  );
}

export async function updateTag(tagId: string, params: {
  name?: string;
  start_relative_time?: number;
  duration?: number;
  type?: 'peak' | 'mean';
}) {
  return requestClient.put<{ status: string }>(
    `/api/core/performance-monitor/tag/update?tag_id=${tagId}`,
    params,
  );
}

export async function deleteTag(tagId: string) {
  return requestClient.delete<{ status: string }>(
    `/api/core/performance-monitor/tag/delete?tag_id=${tagId}`,
  );
}

// 版本对比
export async function createVersion(params: {
  device_id: string;
  name: string;
  collect_ids: string[];
}) {
  return requestClient.post<{ version_id: string; status: string }>(
    '/api/core/performance-monitor/version/create',
    params,
  );
}

export async function getVersions(deviceId: string) {
  return requestClient.get<{ items: PerformanceVersion[] }>(
    `/api/core/performance-monitor/version/list?device_id=${deviceId}`,
  );
}

export async function getCompareData(versionIds: string[]) {
  return requestClient.get(
    `/api/core/performance-monitor/version/compare?version_ids=${versionIds.join(',')}`,
  );
}

// 标记 API
export function getMarkers(collectId: string) {
  return requestClient.get<{ items: MarkerResponse[] }>(`/api/core/performance-monitor/marker/list`, { params: { collect_id: collectId } });
}

export function createMarker(data: MarkerCreate) {
  return requestClient.post<{ id: string; status: string }>(`/api/core/performance-monitor/marker`, data);
}

export function updateMarker(markerId: string, data: MarkerUpdate) {
  return requestClient.put<{ status: string }>(`/api/core/performance-monitor/marker/${markerId}`, data);
}

export function deleteMarker(markerId: string) {
  return requestClient.delete<{ status: string }>(`/api/core/performance-monitor/marker/${markerId}`);
}

// 指标映射 API
export function getMetricMappings(keyword?: string, category?: string) {
  return requestClient.get<MetricMappingResponse[]>(`/api/core/performance-monitor/metric-mapping/list`, {
    params: { keyword, category }
  });
}

export function createMetricMapping(data: MetricMappingCreate) {
  return requestClient.post<{ id: string; status: string }>(`/api/core/performance-monitor/metric-mapping`, data);
}

export function updateMetricMapping(mappingId: string, data: MetricMappingUpdate) {
  return requestClient.put<{ status: string }>(`/api/core/performance-monitor/metric-mapping/${mappingId}`, data);
}

export function deleteMetricMapping(mappingId: string) {
  return requestClient.delete<{ status: string }>(`/api/core/performance-monitor/metric-mapping/${mappingId}`);
}

export function batchImportMappings(collectId: string) {
  return requestClient.post<{ imported_count: number; sensors: any[] }>(
    `/api/core/performance-monitor/metric-mapping/batch-import`,
    null,
    { params: { collect_id: collectId } }
  );
}

// 高级指标查询
export function getAvailableMetrics(collectId: string) {
  return requestClient.get<{ items: AvailableMetric[] }>(
    `/api/core/performance-monitor/metrics/list`,
    { params: { collect_id: collectId } }
  );
}

export function queryAdvancedMetrics(data: AdvancedMetricsQuery) {
  return requestClient.post<AdvancedMetricsResponse>(`/api/core/performance-monitor/metrics/query`, data);
}

// 可用指标类型
export interface AvailableMetric {
  key: string;
  label: string;
  source: 'system' | 'hwinfo';
}