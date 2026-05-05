/**
 * 性能监控模块配置
 */

/**
 * 从环境变量获取预设进程列表
 * 环境变量格式：VITE_PERF_MONITOR_PRESET_PROCESSSES=chrome.exe,node.exe,python.exe
 */
function getPresetProcessesFromEnv(): string[] {
  const envValue = import.meta.env.VITE_PERF_MONITOR_PRESET_PROCESSSES;
  if (envValue) {
    return envValue.split(',').map((s: string) => s.trim()).filter(Boolean);
  }
  // 默认预设进程
  return [
    'chrome.exe',
    'node.exe',
    'python.exe',
    'vscode.exe',
    'java.exe',
    'idea64.exe',
  ];
}

/**
 * 预设进程列表（用于快捷搜索推荐）
 * 从 .env 配置文件读取
 */
export const PRESET_PROCESSSES = getPresetProcessesFromEnv();

/**
 * localStorage 存储键名
 */
export const STORAGE_KEY_PROCESS_HISTORY = 'perf-monitor-process-history';

/**
 * 最大推荐数量
 */
export const MAX_RECOMMEND_COUNT = 6;

/**
 * 从历史记录获取推荐进程
 * 按使用频率排序，返回最常用的进程名
 */
export function getRecommendedProcesses(): string[] {
  try {
    const history = JSON.parse(
      localStorage.getItem(STORAGE_KEY_PROCESS_HISTORY) || '{}',
    );
    return Object.entries(history)
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_RECOMMEND_COUNT)
      .map(([name]) => name);
  } catch {
    return [];
  }
}

/**
 * 保存采集进程到历史记录
 * @param processes 采集的进程名列表
 */
export function saveProcessesToHistory(processes: string[]): void {
  try {
    const history = JSON.parse(
      localStorage.getItem(STORAGE_KEY_PROCESS_HISTORY) || '{}',
    );
    processes.forEach((name) => {
      history[name] = (history[name] || 0) + 1;
    });
    localStorage.setItem(STORAGE_KEY_PROCESS_HISTORY, JSON.stringify(history));
  } catch {
    // ignore storage errors
  }
}

/**
 * 获取显示用的进程推荐列表
 * 优先使用历史记录，如果没有历史则使用预设列表
 */
export function getDisplayProcesses(): string[] {
  const recommended = getRecommendedProcesses();
  if (recommended.length > 0) {
    return recommended;
  }
  return PRESET_PROCESSSES;
}