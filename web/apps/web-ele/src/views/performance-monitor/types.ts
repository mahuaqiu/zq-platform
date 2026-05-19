// 曲线图数据点
export interface ChartDataPoint {
  time: number; // relative_time
  value: number;
}

// 图表系列
export interface ChartSeries {
  name: string;
  data: ChartDataPoint[];
  color: string;
  unit?: string; // 单位：'%'、'GB'、'MB' 等
}

// 图表标签（用于 ChartPanel）
export interface ChartTag {
  name: string;
  start: number; // 起始相对时间
  duration: number; // 时间长度
  type: 'peak' | 'mean';
  color: string;
}

// 次要指标卡片数据
export interface MetricCardData {
  name: string;
  value: number;
  unit: string;
  color?: string;
  historyData: number[]; // 迷你趋势线数据
}

// TOP10 数据
export interface Top10Item {
  name: string;
  value: number;
  trendData: number[]; // 迷你趋势线
  color: string;
}

// TOP10 进程数据（原始格式）
export interface Top10ProcessItem {
  name: string;
  cpu?: number;
  gpu?: number;
}

// 性能数据点
export interface PerformanceData {
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
  target_processes?: any[];
  top10_cpu?: Top10ProcessItem[];
  top10_gpu?: Top10ProcessItem[];
  hwinfo_raw?: any;
}

// 版本颜色映射（与性能监控页面一致，使用 Element Plus 配色）
export const VERSION_COLORS = [
  '#409eff', // 蓝（与性能监控一致）
  '#67c23a', // 绿（与性能监控一致）
  '#e6a23c', // 橙/黄
  '#f56c6c', // 红
  '#909399', // 灰
  '#9c27b0', // 紫
];

// 采集状态枚举
export enum CollectStatusEnum {
  IDLE = 'idle',
  RUNNING = 'running',
  STOPPING = 'stopping',
}

// 标签类型
export type TagType = 'peak' | 'mean';

// 区间合并结果
export interface MergedInterval {
  start: number;
  end: number;
  type: TagType;
}

// 数据摘要
export interface SummaryRow {
  version_name: string;
  color: string;
  peak_cpu?: number;
  peak_process_cpu?: number;
  peak_gpu?: number;
  peak_process_gpu?: number;
  peak_commit_memory?: number;
  peak_memory_usage?: number;
  peak_hwinfo?: number; // HWiNFO 指标峰值
  mean_cpu?: number;
  mean_process_cpu?: number;
  mean_gpu?: number;
  mean_process_gpu?: number;
  mean_commit_memory?: number;
  mean_memory_usage?: number;
  mean_hwinfo?: number; // HWiNFO 指标平均值
}

// 时间轴标记点
export interface TimelineMarker {
  type: 'version' | 'collect' | 'current';
  id: string;
  time: Date;
  name?: string;
  color?: string;
}

// 区间摘要
export interface TagSummary {
  tagId: string;
  tagName: string;
  tagType: 'peak' | 'mean';
  start: number;
  duration: number;
  metrics: Record<string, number>;
}

// 对比标签（跨版本共享，使用相对时间）
export interface CompareTag {
  id: string;
  name: string;
  type: 'peak' | 'stable'; // 冲高 / 稳态（区别于 TagType 'peak' | 'mean'）
  start_time: number; // 相对时间（秒）
  end_time: number; // 相对时间（秒）
  note?: string;
}