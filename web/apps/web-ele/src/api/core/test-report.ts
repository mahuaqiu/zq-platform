import { requestClient } from '#/api/request';

/**
 * 测试报告类型定义
 */

// 轮次统计项
export interface RoundStatItem {
  round: number;
  failCount: number;
}

// 失败步骤分布项
export interface StepDistributionItem {
  step: string;
  count: number;
}

// 报告列表项
export interface TestReportListItem {
  id: string;
  taskId: string;
  taskName: string;
  executeTime: string | null;
  totalCases: number;
  failTotal: number;
  passRate: string;
  compareChange: number | null;
}

// 报告汇总
export interface TestReportSummary {
  id: string;
  taskId: string;
  taskName: string;
  totalCases: number;
  failTotal: number;
  passRate: string;
  compareChange: number | null;
  lastFailTotal: number | null;
  roundStats: RoundStatItem[] | null;
  failAlways: number | null;
  failUnstable: number | null;
  stepDistribution: StepDistributionItem[] | null;
  aiAnalysis: string | null;
  analysisStatus: string | null;
  executeTime: string | null;
}

// 报告明细
export interface TestReportDetail {
  id: string;
  taskId: string;
  taskName: string;
  caseName: string;
  caseFailStep: string;
  caseFailLog: string;
  caseRound: number;
  logUrl: string | null;
  failTime: string | null;
  createTime: string;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

const BASE_URL = '/api/core/test-report';

/**
 * 获取报告列表
 */
export async function getReportListApi(params: {
  page?: number;
  pageSize?: number;
  taskName?: string;
}): Promise<PaginatedResponse<TestReportListItem>> {
  return requestClient.get(BASE_URL, { params });
}

/**
 * 获取报告汇总
 */
export async function getReportSummaryApi(taskId: string): Promise<TestReportSummary> {
  return requestClient.get(`${BASE_URL}/summary/${taskId}`);
}

/**
 * 获取报告明细
 * @param taskId 任务执行ID
 * @param category 分类筛选: all/final_fail/always_fail/unstable
 */
export async function getReportDetailApi(
  taskId: string,
  category?: string,
): Promise<PaginatedResponse<TestReportDetail>> {
  return requestClient.get(`${BASE_URL}/detail/${taskId}`, {
    params: category ? { category } : undefined,
  });
}

/**
 * 获取用例日志地址
 */
export async function getCaseLogApi(
  taskId: string,
  caseName: string,
): Promise<{ logUrl: string | null }> {
  return requestClient.get(`${BASE_URL}/log/${taskId}/${encodeURIComponent(caseName)}`);
}