/**
 * 特性分析 API
 */
import { requestClient } from '#/api/request';

// 类型定义
export interface FeatureAnalysisItem {
  id: string;
  featureIdFather: string | null;
  featureId: string | null;
  featureDesc: string | null;
  featureOwner: string | null;
  featureTaskService: string | null;
  featureSafeTest: string | null;
  featureTestExpectTime: string | null;
  featureTestStartTime: string | null;
  testStatus: string;
  featureProgress: string | null;
  featureRisk: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface PieChartDataItem {
  name: string;
  value: number;
}

export interface PieChartDataResponse {
  seriesData: PieChartDataItem[];
}

export interface VersionListResponse {
  items: string[];
}

// API 接口

/**
 * 获取需求列表
 */
export async function getFeatureListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
}): Promise<PaginatedResponse<FeatureAnalysisItem>> {
  return requestClient.get('/core/feature-analysis', { params });
}

/**
 * 获取版本列表
 */
export async function getVersionListApi(): Promise<VersionListResponse> {
  return requestClient.get('/core/feature-analysis/versions');
}

/**
 * 获取及时转测情况饼图数据
 */
export async function getTimelyTestChartApi(
  version?: string,
): Promise<PieChartDataResponse> {
  return requestClient.get('/core/feature-analysis/chart/timely-test', {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取需求转测情况饼图数据
 */
export async function getTestStatusChartApi(
  version?: string,
): Promise<PieChartDataResponse> {
  return requestClient.get('/core/feature-analysis/chart/test-status', {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取已转测需求验证情况饼图数据
 */
export async function getVerifyStatusChartApi(
  version?: string,
): Promise<PieChartDataResponse> {
  return requestClient.get('/core/feature-analysis/chart/verify-status', {
    params: version ? { version } : undefined,
  });
}