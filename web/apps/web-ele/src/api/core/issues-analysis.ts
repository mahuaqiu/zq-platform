/**
 * 问题分析 API
 */
import { requestClient } from '#/api/request';

const BASE_URL = '/api/core/issues-analysis';

// 类型定义
export interface IssuesAnalysisItem {
  id: string;
  issuesId: string | null;
  issuesTitle: string | null;
  issuesServices: string | null;
  issuesOwner: string | null;
  issuesTestOwner: string | null;
  issuesSeverity: string | null;
  issuesProbability: string | null;
  issuesStatus: string | null;
  issuesVersion: string | null;
  featureId: string | null;
  featureDesc: string | null;
  syncTime: string | null;
  createBy: string | null;
  createTime: string | null;
  modifyTime: string | null;
}

export interface IssuesListParams {
  page?: number;
  pageSize?: number;
  version?: string;
  featureDesc?: string;
  issuesOwner?: string;
  issuesSeverity?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface VersionListResponse {
  items: string[];
}

// API 接口

/**
 * 获取问题列表
 */
export async function getIssuesListApi(
  params: IssuesListParams,
): Promise<PaginatedResponse<IssuesAnalysisItem>> {
  return requestClient.get(BASE_URL, { params });
}

/**
 * 获取版本列表
 */
export async function getIssuesVersionsApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/versions`);
}

/**
 * 获取责任人列表
 */
export async function getIssuesOwnersApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/owners`);
}

/**
 * 获取严重程度列表
 */
export async function getIssuesSeveritiesApi(): Promise<VersionListResponse> {
  return requestClient.get(`${BASE_URL}/severities`);
}