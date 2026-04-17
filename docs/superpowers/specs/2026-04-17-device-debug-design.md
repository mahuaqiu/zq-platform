# 设备调试功能设计文档

## 概述

为设备列表页面增加设备调试功能，支持远程操作在线的 iOS/Android 设备。

### 功能入口

- **触发条件**：设备类型为 iOS 或 Android，且状态为在线
- **入口位置**：设备列表表格操作列，在"编辑"按钮左侧新增"调试"链接
- **交互方式**：点击后打开调试弹窗

## 界面设计

### 弹窗布局

采用三栏布局：左侧操作历史 + 中间手机截图 + 右侧工具栏

```
┌─────────────────────────────────────────────────────────────────┐
│  设备调试 - iPhone 14 Pro    [在线] [iOS]    设备ID: xxx        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌─────────────────────┐    ┌──────────────┐   │
│  │ 操作历史 │    │                     │    │ 刷新截图     │   │
│  │          │    │    手机截图预览      │    │              │   │
│  │ ✓ 点击   │    │    (400x700px)      │    │ 滑动操作     │   │
│  │ ✓ 上滑   │    │                     │    │ ⬆️ ⬇️ ⬅️ ➡️ │   │
│  │ ✓ 刷新   │    │    X:200, Y:90      │    │              │   │
│  │          │    │                     │    │ 自定义滑动   │   │
│  │          │    │                     │    │              │   │
│  │          │    │                     │    │ 文本输入     │   │
│  │          │    │                     │    │              │   │
│  │          │    │                     │    │ 按键操作     │   │
│  │          │    │                     │    │              │   │
│  └──────────┘    ┌─────────────────────┘    └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 核心交互

#### 1. 截图点击操作

- **功能**：点击截图任意位置，发送点击指令到设备对应坐标
- **反馈**：点击位置显示蓝色圆圈指示器（32px），带阴影效果
- **坐标显示**：截图右上角实时显示鼠标悬停位置的坐标

#### 2. 截图刷新

**自动刷新机制**：
- 弹窗打开时，首次获取截图
- 点击、滑动、按键、输入等操作完成后，自动刷新截图
- 无操作时，不自动刷新（避免频繁请求）

**手动刷新**：
- 点击"刷新截图"按钮可手动刷新
- 刷新有冷却间隔（2秒）

**刷新时机**：
```typescript
async function executeAndRefresh(action) {
  await executeOperation(action);
  // 操作完成后自动刷新截图
  await refreshScreenshot();
}
```

#### 3. 滑动操作

**快捷滑动**：
- 四个方向按钮：上滑、下滑、左滑、右滑
- 点击后执行预设的屏幕滑动（从屏幕边缘滑向中心方向）

**自定义滑动弹窗**：
- 起点坐标 (X, Y)
- 终点坐标 (X, Y)
- 滑动时长 (毫秒)
- 可在截图上拖拽选择起点终点

#### 4. 文本输入

- 输入框 + 发送按钮
- 发送文本到设备当前焦点位置
- 需先点击截图定位输入框

#### 5. 按键操作弹窗

按键选择列表：
| 按键 | 说明 |
|------|------|
| Home | 返回主页 |
| Back | 返回上一页 |
| Enter | 确认 |
| Power | 电源键 |
| Volume Up | 音量+ |
| Volume Down | 音量- |

点击按键立即执行。

### 操作历史

- 显示最近操作记录
- 字段：操作类型、参数、时间
- 支持滚动查看

## 交互控制（防止 Worker 过载）

### 1. 操作锁定机制

**核心原则**：一次只能执行一个操作，执行期间禁止其他操作。

- 操作开始时，设置 `isOperating = true`
- 所有操作按钮显示 disabled 状态
- 操作完成后（成功/失败），解锁
- **操作成功后自动刷新截图**（获取最新画面）
- 用户可通过操作历史查看执行状态

### 2. 点击防抖

**防止用户快速连续点击截图**：

```typescript
// 点击防抖：500ms 内重复点击无效
const handleClick = debounce((x, y) => {
  if (!isOperating) {
    executeClick(x, y);
  }
}, 500);
```

- 点击截图后 500ms 内，再次点击无效
- 防抖期间显示提示："操作执行中，请稍候"

### 3. 操作最小间隔

**强制间隔**：每个操作完成后，等待 300ms 才能执行下一个。

```typescript
const MIN_OPERATION_INTERVAL = 300; // ms

let lastOperationTime = 0;

async function executeOperation(action) {
  const now = Date.now();
  const elapsed = now - lastOperationTime;
  
  if (elapsed < MIN_OPERATION_INTERVAL) {
    await sleep(MIN_OPERATION_INTERVAL - elapsed);
  }
  
  // 执行操作...
  lastOperationTime = Date.now();
}
```

### 4. 加载状态反馈

**所有操作**：
- 操作按钮 disabled 状态（执行期间）
- 操作历史记录显示"执行中..."、"成功"或"失败"

### 5. 超时处理

**操作超时时间**：10秒

```typescript
const OPERATION_TIMEOUT = 10000; // ms

async function executeWithTimeout(action) {
  const timeoutPromise = new Promise((_, reject) => 
    setTimeout(() => reject(new Error('操作超时')), OPERATION_TIMEOUT)
  );
  
  return Promise.race([
    executeAction(action),
    timeoutPromise
  ]);
}
```

- 超时后自动取消操作
- 显示错误提示："操作超时，请检查设备状态"
- 解锁操作，允许重试

### 6. 错误处理

**失败提示**：
```
┌─────────────────────────────────────┐
│  ❌ 操作失败                         │
│  原因: 设备响应超时                   │
│  [重试] [关闭]                       │
└─────────────────────────────────────┘
```

- 显示具体失败原因（网络错误、设备离线、超时等）
- 提供"重试"按钮（单次重试，不自动重试）
- 3 次重试失败后提示"设备可能已离线，建议刷新截图检查"

### 7. 刷新截图冷却

**防止频繁刷新截图**：刷新完成后 2 秒内，按钮 disabled。

```typescript
const SCREENSHOT_COOLDOWN = 2000; // ms

let lastScreenshotTime = 0;

function canRefreshScreenshot(): boolean {
  return Date.now() - lastScreenshotTime > SCREENSHOT_COOLDOWN;
}
```

### 8. 操作队列（可选）

如果未来需要支持连续操作，可引入操作队列：

```typescript
interface OperationQueue {
  operations: Operation[];
  maxQueueSize: 5;  // 最大队列长度
  processing: boolean;
}
```

- 队列最多 5 个操作
- 超出提示："操作队列已满，请等待当前操作完成"
- 按顺序执行，每个操作间隔 300ms

### 9. 设备状态检查

**弹窗打开时检查设备状态**：
- 如果设备状态变为 offline，弹窗显示警告
- 自动关闭弹窗，提示"设备已离线"

**定期检查**（可选）：
- 每 30 秒检查一次设备状态
- 状态变化时更新弹窗显示

## Worker API 需求

根据 Worker 现有 API (api.yaml)，调试功能需要调用以下接口：

### 截图获取

```http
POST /task/execute
{
  "platform": "ios" | "android",
  "device_id": "<设备ID>",
  "actions": [
    {"action_type": "screenshot", "value": "debug"}
  ]
}
```

返回结果中的 screenshots 字段包含 base64 编码的截图。

### 点击操作

```http
POST /task/execute
{
  "platform": "ios" | "android",
  "device_id": "<设备ID>",
  "actions": [
    {"action_type": "click", "x": 200, "y": 90}
  ]
}
```

### 滑动操作

```http
POST /task/execute
{
  "platform": "ios" | "android",
  "device_id": "<设备ID>",
  "actions": [
    {
      "action_type": "swipe",
      "from": {"x": 200, "y": 500},
      "to": {"x": 200, "y": 150},
      "duration": 500
    }
  ]
}
```

### 文本输入

```http
POST /task/execute
{
  "platform": "ios" | "android",
  "device_id": "<设备ID>",
  "actions": [
    {"action_type": "input", "x": 100, "y": 200, "text": "输入内容"}
  ]
}
```

### 按键操作

```http
POST /task/execute
{
  "platform": "ios" | "android",
  "device_id": "<设备ID>",
  "actions": [
    {"action_type": "press", "key": "Home"}
  ]
}
```

### 快捷滑动预设

| 方向 | 起点 | 终点 |
|------|------|------|
| 上滑 | (屏幕宽度/2, 屏幕高度*0.8) | (屏幕宽度/2, 屏幕高度*0.2) |
| 下滑 | (屏幕宽度/2, 屏幕高度*0.2) | (屏幕宽度/2, 屏幕高度*0.8) |
| 左滑 | (屏幕宽度*0.8, 屏幕高度/2) | (屏幕宽度*0.2, 屏幕高度/2) |
| 右滑 | (屏幕宽度*0.2, 屏幕高度/2) | (屏幕宽度*0.8, 屏幕高度/2) |

## 数据流

```
前端弹窗
    │
    ├─ 弹窗打开 → 获取初始截图
    │
    ├─ 点击截图 → POST /task/execute (click) → 自动刷新截图
    │
    ├─ 手动刷新 → POST /task/execute (screenshot) → 显示图片
    │
    ├─ 滑动操作 → POST /task/execute (swipe) → 自动刷新截图
    │
    ├─ 文本输入 → POST /task/execute (input) → 自动刷新截图
    │
    └─ 按键操作 → POST /task/execute (press) → 自动刷新截图
    │
    └───────────→ 操作历史记录更新
```

**自动刷新策略**：每次操作成功后自动刷新截图，让用户看到操作后的画面变化。

## 后端接口需求

需要后端提供代理接口，转发请求到 Worker：

### 新增后端 API

```http
POST /api/core/env-machine/{device_id}/debug-action
```

请求体：
```json
{
  "action_type": "click" | "swipe" | "input" | "press" | "screenshot",
  "params": {
    // 根据 action_type 不同
    // click: {x, y}
    // swipe: {from_x, from_y, to_x, to_y, duration}
    // input: {x, y, text}
    // press: {key}
    // screenshot: {}
  }
}
```

响应：
```json
{
  "success": true,
  "result": {
    // 截图操作返回 screenshot_base64
    // 其他操作返回执行状态
  }
}
```

## 前端组件

### 文件结构

```
web/apps/web-ele/src/views/env-machine/
├── list.vue                    # 设备列表页面（修改）
├── DebugDialog.vue             # 调试弹窗组件（新增）
├── modules/
│   ├── SwipeDialog.vue         # 自定义滑动弹窗（新增）
│   └── KeyPressDialog.vue      # 按键选择弹窗（新增）
```

### API 定义

```typescript
// web/apps/web-ele/src/api/core/env-machine.ts

export interface DebugActionParams {
  action_type: 'click' | 'swipe' | 'input' | 'press' | 'screenshot';
  params: Record<string, any>;
}

export interface DebugActionResult {
  success: boolean;
  result?: {
    screenshot_base64?: string;
  };
}

export function debugDeviceActionApi(
  deviceId: string,
  params: DebugActionParams
): Promise<DebugActionResult>;
```

## 成功标准

1. 在线 iOS/Android 设备显示"调试"操作入口
2. 点击打开调试弹窗，显示设备实时截图
3. 点击截图可发送点击指令，显示坐标指示器
4. 刷新截图功能正常工作
5. 快捷滑动（四个方向）执行成功
6. 自定义滑动弹窗可设置坐标并执行
7. 文本输入发送成功
8. 按键操作弹窗按键执行成功
9. 操作历史记录正确显示