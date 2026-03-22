/**
 * 特性分析 API
 */
import { requestClient } from '#/api/request';

const BASE_URL = '/api/core/feature-analysis';

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

export interface QualityEvaluationItem {
  id: string;
  featureId: string | null;
  featureDesc: string | null;
  featureOwner: string | null;
  delayDays: number | null;
  testCount: string | null;
  bugTotal: string | null;
  bugSerious: string | null;
  bugIntroCount: string | null;
  codeLines: string | null;
  qualityJudge: string | null;
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
  featureIdFather?: string;
  featureId?: string;
  featureOwner?: string;
  featureTaskService?: string;
  sortBy?: string;
  sortOrder?: string;
}): Promise<PaginatedResponse<FeatureAnalysisItem>> {
  return requestClient.get(BASE_URL, { params });
}

/**
 * 获取版本列表
 */
export async function getVersionListApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/versions`);
}

/**
 * 获取及时转测情况饼图数据
 */
export async function getTimelyTestChartApi(
  version?: string,
): Promise<PieChartDataResponse> {
  return requestClient.get(`${BASE_URL}/chart/timely-test`, {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取需求转测情况饼图数据
 */
export async function getTestStatusChartApi(
  version?: string,
): Promise<PieChartDataResponse> {
  return requestClient.get(`${BASE_URL}/chart/test-status`, {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取已转测需求验证情况饼图数据
 */
export async function getVerifyStatusChartApi(
  version?: string,
): Promise<PieChartDataResponse> {
  return requestClient.get(`${BASE_URL}/chart/verify-status`, {
    params: version ? { version } : undefined,
  });
}

/**
 * 获取质量评价列表
 */
export async function getQualityListApi(params: {
  page?: number;
  pageSize?: number;
  version?: string;
  featureId?: string;
  featureDesc?: string;
  sortBy?: string;
  sortOrder?: string;
}): Promise<PaginatedResponse<QualityEvaluationItem>> {
  return requestClient.get(`${BASE_URL}/quality`, { params });
}

/**
 * 获取测试责任人列表
 */
export async function getOwnerListApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/owners`);
}

/**
 * 获取测试归属列表
 */
export async function getTaskServiceListApi(): Promise<{ items: string[] }> {
  return requestClient.get(`${BASE_URL}/task-services`);
}