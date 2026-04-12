import { requestClient } from '#/api/request';

// ========== 类型定义 ==========

/**
 * AI 群组
 */
export interface AIGroup {
  id: string;
  group_id: string;
  group_name: string;
  is_group: boolean;
  trigger_word: string;
  requires_trigger: boolean;
  is_active: boolean;
  last_message_time?: string;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * AI 会话
 */
export interface AISession {
  id: string;
  group_id: string;
  group_name?: string;
  chat_id: string;
  session_name?: string;
  message_count: number;
  status: number; // 0-活跃, 1-已关闭, 2-已清除
  start_time: string;
  last_message_time: string;
  is_active: boolean;
  sys_create_datetime?: string;
}

/**
 * AI 消息
 */
export interface AIMessage {
  id: string;
  session_id: string;
  message_type: number; // 0-用户, 1-AI
  sender_id: string;
  sender_name?: string;
  content: string;
  nanoclaw_message_id?: string;
  send_time: string;
  receive_time?: string;
  is_context_recovery: boolean;
}

/**
 * AI 会话详情
 */
export interface AISessionDetail {
  session: AISession;
  messages: AIMessage[];
  group_name?: string;
  trigger_word?: string; // 触发词（AI助手名称）
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

// ========== 群组 API ==========

/**
 * 获取 AI 群组列表
 */
export async function getAIGroupListApi(params: {
  group_id?: string;
  group_name?: string;
  is_active?: boolean;
  page: number;
  page_size: number;
}) {
  return requestClient.get<PaginatedResponse<AIGroup>>('/api/core/ai/group', {
    params,
  });
}

/**
 * 获取 AI 群组详情
 */
export async function getAIGroupDetailApi(id: string) {
  return requestClient.get<AIGroup>(`/api/core/ai/group/${id}`);
}

/**
 * 创建 AI 群组
 */
export async function createAIGroupApi(data: {
  group_id: string;
  group_name: string;
  is_group?: boolean;
  trigger_word?: string;
  requires_trigger?: boolean;
  is_active?: boolean;
}) {
  return requestClient.post<AIGroup>('/api/core/ai/group', data);
}

/**
 * 更新 AI 群组
 */
export async function updateAIGroupApi(id: string, data: Partial<AIGroup>) {
  return requestClient.put<AIGroup>(`/api/core/ai/group/${id}`, data);
}

/**
 * 删除 AI 群组
 */
export async function deleteAIGroupApi(id: string) {
  return requestClient.delete(`/api/core/ai/group/${id}`);
}

// ========== 会话 API ==========

/**
 * 获取 AI 会话列表
 */
export async function getAISessionListApi(params: {
  group_id?: string;
  status?: number;
  page: number;
  page_size: number;
}) {
  return requestClient.get<PaginatedResponse<AISession>>('/api/core/ai/session', {
    params,
  });
}

/**
 * 获取 AI 会话详情
 */
export async function getAISessionDetailApi(id: string) {
  return requestClient.get<AISessionDetail>(`/api/core/ai/session/${id}`);
}

/**
 * 在会话中发送消息
 */
export async function sendMessageInSessionApi(sessionId: string, content: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/send`, {
    content,
  });
}

/**
 * 清除会话上下文
 */
export async function clearSessionContextApi(sessionId: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/clear`);
}

/**
 * 关闭会话
 */
export async function closeSessionApi(sessionId: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/close`);
}

/**
 * 创建新会话（基于现有会话的群组）
 */
export async function createNewSessionApi(sessionId: string) {
  return requestClient.post<AISession>(
    `/api/core/ai/session/${sessionId}/new-session`,
  );
}

/**
 * 手动创建会话（为指定群组）
 */
export async function createSessionApi(data: {
  group_id: string;
  group_name?: string;
  is_group?: boolean;
}) {
  return requestClient.post<AISession>('/api/core/ai/session', data);
}

/**
 * 删除会话
 */
export async function deleteSessionApi(id: string) {
  return requestClient.delete(`/api/core/ai/session/${id}`);
}