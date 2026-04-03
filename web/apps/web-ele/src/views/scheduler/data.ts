import type { SchedulerJob } from '#/api/core/scheduler';

/**
 * 触发类型选项
 */
export const TRIGGER_TYPE_OPTIONS = [
  { label: 'Cron表达式', value: 'cron' },
  { label: '固定间隔', value: 'interval' },
  { label: '指定时间', value: 'date' },
];

/**
 * 任务状态选项
 * 0: 禁用, 1: 启用, 2: 暂停
 */
export const JOB_STATUS_OPTIONS = [
  { label: '启用', value: 1, type: 'success' },
  { label: '禁用', value: 0, type: 'danger' },
  { label: '暂停', value: 2, type: 'warning' },
];

/**
 * 日志状态选项
 */
export const LOG_STATUS_OPTIONS = [
  { label: '成功', value: 'success', type: 'success' },
  { label: '失败', value: 'failed', type: 'danger' },
  { label: '超时', value: 'timeout', type: 'warning' },
  { label: '执行中', value: 'running', type: 'info' },
  { label: '待执行', value: 'pending', type: 'info' },
];

/**
 * 清理日志天数选项
 */
export const CLEAN_DAYS_OPTIONS = [
  { label: '最近7天', value: 7 },
  { label: '最近30天', value: 30 },
  { label: '最近90天', value: 90 },
  { label: '最近180天', value: 180 },
];

/**
 * 获取触发类型显示名称
 * @param type 触发类型
 * @returns 显示名称
 */
export function getTriggerTypeLabel(type: string): string {
  const option = TRIGGER_TYPE_OPTIONS.find((opt) => opt.value === type);
  return option?.label ?? type;
}

/**
 * 获取任务状态显示名称
 * @param status 任务状态
 * @returns 显示名称
 */
export function getJobStatusLabel(status: number): string {
  const option = JOB_STATUS_OPTIONS.find((opt) => opt.value === status);
  return option?.label ?? '未知';
}

/**
 * 获取任务状态样式类
 * @param status 任务状态
 * @returns 样式类名
 */
export function getJobStatusClass(status: number): string {
  switch (status) {
    case 1: // 启用
      return 'success';
    case 0: // 禁用
      return 'danger';
    case 2: // 暂停
      return 'warning';
    default:
      return 'info';
  }
}

/**
 * 获取日志状态显示名称
 * @param status 日志状态
 * @returns 显示名称
 */
export function getLogStatusLabel(status: string): string {
  const option = LOG_STATUS_OPTIONS.find((opt) => opt.value === status);
  return option?.label ?? status;
}

/**
 * 获取日志状态样式类
 * @param status 日志状态
 * @returns 样式类名
 */
export function getLogStatusClass(status: string): string {
  switch (status) {
    case 'success':
      return 'success';
    case 'failed':
      return 'danger';
    case 'timeout':
      return 'warning';
    case 'running':
      return 'info';
    case 'pending':
      return 'info';
    default:
      return 'info';
  }
}

/**
 * 格式化触发配置显示
 * @param job 任务对象
 * @returns 格式化后的触发配置字符串
 */
export function formatTriggerConfig(job: SchedulerJob): string {
  if (!job) return '-';

  switch (job.trigger_type) {
    case 'cron':
      return job.cron_expression || '-';
    case 'interval':
      return job.interval_seconds ? `${job.interval_seconds}秒` : '-';
    case 'date':
      return job.run_date || '-';
    default:
      return '-';
  }
}

/**
 * 格式化日期时间
 * @param dateStr 日期字符串
 * @returns 格式化后的日期时间字符串
 */
export function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '-';

  try {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  } catch {
    return dateStr;
  }
}

/**
 * 格式化执行耗时
 * @param duration 耗时（秒）
 * @returns 格式化后的耗时字符串
 */
export function formatDuration(duration?: number): string {
  if (duration === undefined || duration === null) return '-';

  if (duration < 1) {
    return `${(duration * 1000).toFixed(0)}毫秒`;
  } else if (duration < 60) {
    return `${duration.toFixed(2)}秒`;
  } else {
    const minutes = Math.floor(duration / 60);
    const seconds = (duration % 60).toFixed(0);
    return `${minutes}分${seconds}秒`;
  }
}