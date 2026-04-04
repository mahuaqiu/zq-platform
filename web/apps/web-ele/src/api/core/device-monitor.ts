import { requestClient } from '#/api/request';

// 类型定义
export interface DeviceTypeStats {
  type: string;
  total: number;
  enabled: number;
  disabled: number;
}

export interface DeviceStats {
  total: number;
  online: number;
  offline: number;
  by_type: DeviceTypeStats[];
}

export interface Apply24hStats {
  total: number;
  success: number;
  failed: number;
}

export interface TopTagItem {
  tag: string;
  count: number;
}

export interface TopDurationItem {
  ip?: string;
  device_sn?: string;
  device_type: string;
  duration_minutes: number;
  duration_display: string;
}

export interface OfflineMachineItem {
  id: string;
  name?: string;
  ip?: string;
  device_sn?: string;
  device_type: string;
  offline_duration: string;
}

export interface DashboardStatsResponse {
  device_stats: DeviceStats;
  apply_24h: Apply24hStats;
  top10_tags: TopTagItem[];
  top20_duration: TopDurationItem[];
  top10_insufficient: TopTagItem[];
  offline_machines: OfflineMachineItem[];
}

// API 接口
export function getDashboardStatsApi(namespace?: string) {
  return requestClient.get<DashboardStatsResponse>('/api/core/env/dashboard/stats', {
    params: { namespace },
  });
}