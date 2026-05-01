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

// 版本颜色映射
export const VERSION_COLORS = [
  '#67c23a', // 绿
  '#f56c6c', // 红
  '#e6a23c', // 橙
  '#409eff', // 蓝
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
  peak_commit_memory?: number;
  peak_memory_usage?: number;
  mean_cpu?: number;
  mean_process_cpu?: number;
  mean_gpu?: number;
  mean_commit_memory?: number;
  mean_memory_usage?: number;
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