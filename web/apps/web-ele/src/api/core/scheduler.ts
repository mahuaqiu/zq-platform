import { requestClient } from '#/api/request';

/**
 * 定时任务类型定义
 */
export interface SchedulerJob {
  id: string;
  name: string;
  code: string;
  description?: string;
  group: string;
  trigger_type: string;
  trigger_type_display?: string;
  cron_expression?: string;
  interval_seconds?: number;
  run_date?: string;
  task_func: string;
  task_kwargs?: string;
  execute_host_ip?: string;
  status: number;
  status_display?: string;
  priority: number;
  max_instances: number;
  max_retries: number;
  timeout: number;
  coalesce: boolean;
  allow_concurrent: boolean;
  total_run_count: number;
  success_count: number;
  failure_count: number;
  success_rate?: number;
  last_run_time?: string;
  next_run_time?: string;
  last_run_status?: string;
  last_run_result?: string;
  remark?: string;
  sort: number;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 定时任务简化类型（用于选择器）
 */
export interface SchedulerJobSimple {
  id: string;
  name: string;
  code: string;
  group: string;
  status: number;
}

/**
 * 执行日志类型定义
 */
export interface SchedulerLog {
  id: string;
  job_id: string;
  job_name: string;
  job_code: string;
  status: string;
  status_display?: string;
  start_time: string;
  end_time?: string;
  duration?: number;
  result?: string;
  exception?: string;
  traceback?: string;
  hostname?: string;
  process_id?: number;
  retry_count: number;
  sys_create_datetime?: string;
}

/**
 * 任务统计类型定义
 */
export interface SchedulerStatistics {
  total_jobs: number;
  enabled_jobs: number;
  disabled_jobs: number;
  paused_jobs: number;
  total_executions: number;
  success_executions: number;
  failed_executions: number;
  success_rate: number;
}

/**
 * 日志统计类型定义
 */
export interface SchedulerLogStatistics {
  total_executions: number;
  success_executions: number;
  failed_executions: number;
  success_rate: number;
}

/**
 * 调度器状态类型定义
 */
export interface SchedulerStatus {
  is_running: boolean;
  job_count: number;
  jobs: Record<string, any>[];
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

/**
 * 任务查询参数
 */
export interface SchedulerJobQueryParams {
  page: number;
  pageSize: number;
  name?: string;
  code?: string;
  group?: string;
  trigger_type?: string;
  status?: number;
}

/**
 * 任务创建参数
 */
export interface SchedulerJobCreateParams {
  name: string;
  code: string;
  trigger_type: string;
  task_func: string;
  description?: string;
  group?: string;
  cron_expression?: string;
  interval_seconds?: number;
  run_date?: string;
  task_kwargs?: string;
  execute_host_ip?: string;
  status?: number;
  sort?: number;
}

/**
 * 任务更新参数
 */
export interface SchedulerJobUpdateParams {
  name?: string;
  code?: string;
  description?: string;
  group?: string;
  trigger_type?: string;
  cron_expression?: string;
  interval_seconds?: number;
  run_date?: string;
  task_func?: string;
  task_kwargs?: string;
  execute_host_ip?: string;
  status?: number;
  sort?: number;
}

/**
 * 日志查询参数
 */
export interface SchedulerLogQueryParams {
  page: number;
  pageSize: number;
  job_id?: string;
  job_code?: string;
  job_name?: string;
  status?: string;
  startTimeGte?: string;
  startTimeLte?: string;
}

/**
 * 日志统计查询参数
 */
export interface SchedulerLogStatisticsParams {
  job_id?: string;
  job_code?: string;
  job_name?: string;
  status?: string;
  startTimeGte?: string;
  startTimeLte?: string;
}

/**
 * 批量删除参数
 */
export interface BatchDeleteParams {
  ids: string[];
}

/**
 * 批量删除响应
 */
export interface BatchDeleteResponse {
  count: number;
  failed_ids?: string[];
}

/**
 * 批量更新状态参数
 */
export interface BatchUpdateStatusParams {
  ids: string[];
  status: number;
}

/**
 * 批量更新状态响应
 */
export interface BatchUpdateStatusResponse {
  count: number;
}

/**
 * 立即执行任务参数
 */
export interface ExecuteJobParams {
  job_id: string;
}

/**
 * 立即执行任务响应
 */
export interface ExecuteJobResponse {
  success: boolean;
  message: string;
  log_id?: string;
}

/**
 * 搜索任务参数
 */
export interface SearchJobParams {
  keyword: string;
}

/**
 * 清理日志参数
 */
export interface CleanLogParams {
  days: number;
  status?: string;
}

/**
 * 清理日志响应
 */
export interface CleanLogResponse {
  count: number;
}

// ==================== 任务管理 API ====================

/**
 * 获取任务分组列表
 */
export async function getSchedulerJobGroupsApi() {
  return requestClient.get<string[]>('/api/core/scheduler/job/groups');
}

/**
 * 获取定时任务列表（分页）
 */
export async function getSchedulerJobListApi(params: SchedulerJobQueryParams) {
  return requestClient.get<PaginatedResponse<SchedulerJob>>('/api/core/scheduler/job', {
    params,
  });
}

/**
 * 获取所有定时任务（简化版）
 */
export async function getSchedulerJobAllApi() {
  return requestClient.get<SchedulerJobSimple[]>('/api/core/scheduler/job/all');
}

/**
 * 获取定时任务详情
 */
export async function getSchedulerJobDetailApi(jobId: string) {
  return requestClient.get<SchedulerJob>(`/api/core/scheduler/job/${jobId}`);
}

/**
 * 创建定时任务
 */
export async function createSchedulerJobApi(data: SchedulerJobCreateParams) {
  return requestClient.post<SchedulerJob>('/api/core/scheduler/job', data);
}

/**
 * 更新定时任务
 */
export async function updateSchedulerJobApi(
  jobId: string,
  data: SchedulerJobUpdateParams,
) {
  return requestClient.put<SchedulerJob>(`/api/core/scheduler/job/${jobId}`, data);
}

/**
 * 删除定时任务
 */
export async function deleteSchedulerJobApi(jobId: string, hard?: boolean) {
  return requestClient.delete(`/api/core/scheduler/job/${jobId}`, {
    params: { hard },
  });
}

/**
 * 立即执行任务
 */
export async function executeSchedulerJobApi(data: ExecuteJobParams) {
  return requestClient.post<ExecuteJobResponse>('/api/core/scheduler/job/execute', data);
}

/**
 * 获取任务统计信息
 */
export async function getSchedulerStatisticsApi() {
  return requestClient.get<SchedulerStatistics>('/api/core/scheduler/job/statistics/data');
}

/**
 * 批量更新任务状态
 */
export async function batchUpdateSchedulerJobStatusApi(data: BatchUpdateStatusParams) {
  return requestClient.post<BatchUpdateStatusResponse>(
    '/api/core/scheduler/job/batch/update_status',
    data,
  );
}

/**
 * 批量删除定时任务
 */
export async function batchDeleteSchedulerJobsApi(data: BatchDeleteParams) {
  return requestClient.post<BatchDeleteResponse>(
    '/api/core/scheduler/job/batch/delete',
    data,
  );
}

/**
 * 搜索定时任务
 */
export async function searchSchedulerJobsApi(
  data: SearchJobParams,
  params: { page: number; pageSize: number },
) {
  return requestClient.post<PaginatedResponse<SchedulerJob>>(
    '/api/core/scheduler/job/search',
    data,
    { params },
  );
}

// ==================== 执行日志 API ====================

/**
 * 获取日志统计信息
 */
export async function getSchedulerLogStatisticsApi(params?: SchedulerLogStatisticsParams) {
  return requestClient.get<SchedulerLogStatistics>('/api/core/scheduler/log/statistics/data', {
    params,
  });
}

/**
 * 获取执行日志列表（分页）
 */
export async function getSchedulerLogListApi(params: SchedulerLogQueryParams) {
  return requestClient.get<PaginatedResponse<SchedulerLog>>('/api/core/scheduler/log', {
    params,
  });
}

/**
 * 获取指定任务的执行日志
 */
export async function getSchedulerLogsByJobApi(
  jobId: string,
  params: { page: number; pageSize: number },
) {
  return requestClient.get<PaginatedResponse<SchedulerLog>>(
    `/api/core/scheduler/log/by/job/${jobId}`,
    { params },
  );
}

/**
 * 获取执行日志详情
 */
export async function getSchedulerLogDetailApi(logId: string) {
  return requestClient.get<SchedulerLog>(`/api/core/scheduler/log/${logId}`);
}

/**
 * 删除执行日志
 */
export async function deleteSchedulerLogApi(logId: string) {
  return requestClient.delete(`/api/core/scheduler/log/${logId}`);
}

/**
 * 批量删除执行日志
 */
export async function batchDeleteSchedulerLogsApi(data: BatchDeleteParams) {
  return requestClient.post<BatchDeleteResponse>(
    '/api/core/scheduler/log/batch/delete',
    data,
  );
}

/**
 * 清理旧日志
 */
export async function cleanSchedulerLogsApi(data: CleanLogParams) {
  return requestClient.post<CleanLogResponse>('/api/core/scheduler/log/clean', data);
}

// ==================== 调度器控制 API ====================

/**
 * 启动调度器
 */
export async function startSchedulerApi() {
  return requestClient.post('/api/core/scheduler/start');
}

/**
 * 关闭调度器
 */
export async function shutdownSchedulerApi() {
  return requestClient.post('/api/core/scheduler/shutdown');
}

/**
 * 暂停调度器
 */
export async function pauseSchedulerApi() {
  return requestClient.post('/api/core/scheduler/pause');
}

/**
 * 恢复调度器
 */
export async function resumeSchedulerApi() {
  return requestClient.post('/api/core/scheduler/resume');
}

/**
 * 获取调度器状态
 */
export async function getSchedulerStatusApi() {
  return requestClient.get<SchedulerStatus>('/api/core/scheduler/status');
}