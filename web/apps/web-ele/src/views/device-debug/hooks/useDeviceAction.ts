import { ref } from 'vue';

import { ElMessage } from 'element-plus';

import { debugDeviceActionApi } from '#/api/core/env-machine';
import type { OperationRecord } from '../types';
import { formatTime, formatHistoryDisplay } from '../utils';

const OPERATION_TIMEOUT = 20000; // 普通操作超时：20秒
const UNLOCK_TIMEOUT = 30000;    // 解锁操作超时：30秒
const MIN_OPERATION_INTERVAL = 300; // 最小操作间隔

export function useDeviceAction(deviceId: string) {
  const isOperating = ref(false);
  const lastOperationTime = ref(0);
  const operationHistory = ref<OperationRecord[]>([]);

  /**
   * 等待
   */
  function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 添加历史记录
   */
  function addHistory(type: string, params: string, status: 'pending' | 'success' | 'failed', error?: string): void {
    operationHistory.value.unshift({
      type,
      params,
      status,
      time: formatTime(),
      error,
    });
    if (operationHistory.value.length > 20) {
      operationHistory.value = operationHistory.value.slice(0, 20);
    }
  }

  /**
   * 更新历史记录状态
   */
  function updateHistoryStatus(status: 'success' | 'failed', error?: string): void {
    const record = operationHistory.value[0];
    if (record) {
      record.status = status;
      if (error) {
        record.error = error;
      }
    }
  }

  /**
   * 执行操作
   */
  async function executeOperation(
    actionType: string,
    params: Record<string, any>,
    _skipRefresh = true, // WebSocket 实时刷新，不需要手动刷新
    isAuto = false
  ): Promise<boolean> {
    // 检查最小间隔
    const now = Date.now();
    const elapsed = now - lastOperationTime.value;
    if (elapsed < MIN_OPERATION_INTERVAL) {
      await sleep(MIN_OPERATION_INTERVAL - elapsed);
    }

    isOperating.value = true;
    lastOperationTime.value = Date.now();

    // 记录操作开始
    if (!isAuto && actionType !== 'screenshot') {
      const displayText = formatHistoryDisplay(actionType, params);
      addHistory(actionType, displayText, 'pending');
    }

    try {
      const timeout = actionType === 'unlock_screen' ? UNLOCK_TIMEOUT : OPERATION_TIMEOUT;

      const result = await debugDeviceActionApi(
        deviceId,
        { action_type: actionType as any, params },
        timeout,
      );

      if (result && result.success) {
        if (!isAuto) {
          updateHistoryStatus('success');
        }
        return true;
      } else {
        const errorMsg = result?.result?.error || result?.error || '操作失败';
        if (!isAuto) {
          updateHistoryStatus('failed', errorMsg);
          ElMessage.error(errorMsg);
        }
        return false;
      }
    } catch (error: any) {
      const errorMsg = error?.message || error?.response?.data?.error || '操作失败';
      if (!isAuto) {
        updateHistoryStatus('failed', errorMsg);
        ElMessage.error(errorMsg);
      }
      return false;
    } finally {
      isOperating.value = false;
    }
  }

  /**
   * 点击操作
   */
  async function click(x: number, y: number, monitor?: number): Promise<boolean> {
    const params: Record<string, any> = { x, y };
    if (monitor !== undefined) {
      params.monitor = monitor;
    }
    return executeOperation('click', params);
  }

  /**
   * 右键点击操作
   */
  async function rightClick(x: number, y: number, monitor?: number): Promise<boolean> {
    const params: Record<string, any> = { x, y };
    if (monitor !== undefined) {
      params.monitor = monitor;
    }
    return executeOperation('right_click', params);
  }

  /**
   * 滑动操作
   */
  async function swipe(fromX: number, fromY: number, toX: number, toY: number, duration = 500, monitor?: number): Promise<boolean> {
    const params: Record<string, any> = { from_x: fromX, from_y: fromY, to_x: toX, to_y: toY, duration };
    if (monitor !== undefined) {
      params.monitor = monitor;
    }
    return executeOperation('swipe', params);
  }

  /**
   * 输入文本
   */
  async function inputText(text: string): Promise<boolean> {
    return executeOperation('input', { x: 0, y: 0, text });
  }

  /**
   * 按键操作
   */
  async function pressKey(key: string): Promise<boolean> {
    return executeOperation('press', { key });
  }

  /**
   * 解锁屏幕
   */
  async function unlockScreen(password?: string): Promise<boolean> {
    return executeOperation('unlock_screen', { value: password || '' });
  }

  return {
    isOperating,
    operationHistory,
    executeOperation,
    click,
    rightClick,
    swipe,
    inputText,
    pressKey,
    unlockScreen,
  };
}