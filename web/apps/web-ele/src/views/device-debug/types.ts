/**
 * 设备类型
 */
export type DeviceType = 'windows' | 'mac' | 'ios' | 'android';

/**
 * WebSocket 连接状态
 */
export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

/**
 * WebSocket 关闭原因
 */
export interface WebSocketCloseInfo {
  code: number;
  reason: string;
}

/**
 * 设备操作类型
 */
export type DeviceActionType = 'click' | 'swipe' | 'input' | 'press' | 'screenshot';

/**
 * 操作参数
 */
export interface ClickParams {
  x: number;
  y: number;
}

export interface SwipeParams {
  from_x: number;
  from_y: number;
  to_x: number;
  to_y: number;
  duration?: number;
}

export interface InputParams {
  text: string;
}

export interface PressParams {
  key: string;
}

/**
 * 设备详情（从 API 获取）
 */
export interface DeviceDetail {
  id: string;
  udid: string;
  device_type: string;
  asset_number: string;
  ip: string;
  port: string;
  worker_host: string;
  worker_port: number;
  status: string;
  device_sn?: string;
}

/**
 * 操作历史记录
 */
export interface OperationRecord {
  type: string;
  params: string;
  status: 'pending' | 'success' | 'failed';
  time: string;
}

/**
 * 屏幕尺寸信息
 */
export interface ScreenSize {
  width: number;
  height: number;
}