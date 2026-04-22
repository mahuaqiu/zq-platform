---
name: device-debug-realtime-screen
description: 设备调试页面实时屏幕推流改造设计文档
type: project
---

# 设备调试页面实时屏幕推流改造设计文档

## 1. 项目背景

### 1.1 当前问题

现有的设备调试功能使用 `DebugDialog.vue` 弹窗组件，通过 HTTP API 单次截图方式获取设备屏幕：

- **用户体验差**：单次截图刷新有冷却时间限制，无法实时看到操作结果
- **界面局限**：弹窗尺寸固定，无法适配 Windows/Mac 等大屏设备调试需求
- **交互繁琐**：点击、滑动需要通过按钮触发弹窗再输入参数

### 1.2 改造目标

将截图功能从单次 HTTP API 改为 WebSocket 实时屏幕推流，并将弹窗改为独立页面，提供更好的调试体验：

- 实时屏幕推流（约 10 fps）
- 点击/滑动直接在屏幕上操作
- Windows/Mac 支持接近全屏展示
- 新增 APP 安装功能

## 2. 功能需求

### 2.1 核心功能

| 功能 | Windows/Mac | 移动端 | 说明 |
|------|-------------|--------|------|
| 实时屏幕推流 | ✓ | ✓ | WebSocket 连接，JPEG 原始字节流，约 10 fps |
| 点击操作 | ✓ | ✓ | 鼠标点击屏幕 → 远程点击 |
| 滑动操作 | ✓ | ✓ | 鼠标拖拽屏幕 → 远程滑动 |
| 按键操作 | ✓ | ✓ | 弹窗选择按键类型发送 |
| 文本输入 | ✓（弹窗） | ✓（右侧面板） | 输入文本并发送到设备 |
| 截图保存 | ✓ | ✓ | 保存当前屏幕画面到本地 |
| 解锁屏幕 | ✗ | ✓ | 弹窗输入密码（可选），解锁设备 |
| 安装 APP | ✓ | ✓ | 上传安装包并安装 |
| 全屏模式 | ✓ | ✓（右上角按钮） | 全屏查看屏幕 |

### 2.2 快捷按键（仅移动端）

简化为 3 个核心按键：
- HOME
- BACK
- 电源

### 2.3 WebSocket 接口

**URL**: `ws://{host}:{port}/ws/screen/{device_id}`

**Path 参数**:
- `device_id`: 设备 ID（Android/iOS: udid，Windows: windows_screen）

**说明**：路由参数 `deviceId` 使用数据库主键 UUID（`row.id`），页面加载时通过 API 查询设备详情获取 `udid` 字段，用于 WebSocket 连接。

**数据格式**:
- 发送内容：JPEG 原始字节流（非 base64，非 JSON）
- 帧率：约 10 fps
- 接收方式：二进制数据，直接显示

**断连场景**:
| Close Code | Reason | 场景 |
|------------|--------|------|
| 1008 | "Max connections reached" | 连接数超限，拒绝连接 |
| 1001 | "Send timeout" | 发送超时（网络异常） |
| 1000 | - | 客户端主动断开 |

## 3. UI 设计

### 3.1 页面布局

采用独立页面设计，参考设备监控页面的白色风格：

- **页面背景**: #f0f2f5（浅灰色）
- **卡片/面板**: #fff（白色） + 圆角 12px + 阴影
- **主文字**: #111
- **次级文字**: #666
- **边框/分割线**: #e8e8e8

#### 3.1.1 Windows/Mac 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部导航栏 (56px)                                            │
│ [返回] 💻 设备名 | 系统信息 [在线]    WebSocket状态 | fps | 全屏 | 断开 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    屏幕展示区 (94% 视口)                      │
│                    实时屏幕推流画面                           │
│                    [LIVE]                  [坐标显示]         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ 底部工具栏 (56px)                                            │
│ [按键操作] [输入文本] [安装APP] | [截图保存]        操作统计   │
└─────────────────────────────────────────────────────────────┘
```

#### 3.1.2 移动端页面布局

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部导航栏 (56px)                                            │
│ [返回] 📱 设备名 | 系统信息 [在线]    WebSocket状态 | fps | [全屏] | 断开 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────┐    ┌──────────────────────────────┐      │
│   │              │    │ 设备信息                      │      │
│   │  手机屏幕    │    │ UDID | 电池                   │      │
│   │  (340px宽)   │    ├──────────────────────────────┤      │
│   │              │    │ 快捷按键: HOME | BACK | 电源  │      │
│   │  [LIVE]      │    ├──────────────────────────────┤      │
│   │  [坐标]      │    │ 文本输入: [输入框] [发送]     │      │
│   │              │    ├──────────────────────────────┤      │
│   │              │    │ 操作历史                      │      │
│   │              │    ├──────────────────────────────┤      │
│   │              │    │ [截图保存] [解锁] [安装APP]   │      │
│   └──────────────┘    └──────────────────────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 弹窗设计

#### 3.2.1 解锁屏幕弹窗（仅移动端）

- 标题：🔒 解锁屏幕
- 密码输入框（可选）
- 提示：「如果设备无密码锁，可直接解锁」
- 按钮：取消 | 确认解锁

#### 3.2.2 安装 APP 弹窗

- 标题：📦 安装 APP
- 文件上传区域（支持拖拽或点击）
- 支持格式提示：.apk / .ipa / .exe
- 按钮：取消 | 上传并安装

#### 3.2.3 按键操作弹窗

- 标题：⌨ 按键操作
- 按键类型选择
- 按钮：取消 | 发送

#### 3.2.4 输入文本弹窗（Windows/Mac）

- 标题：📝 输入文本
- 文本输入框
- 按钮：取消 | 发送

### 3.3 屏幕交互

- **鼠标点击**：直接在屏幕上点击，发送坐标到设备执行点击操作
- **鼠标拖拽**：拖拽完成滑动操作，记录起始和结束坐标
- **坐标显示**：实时显示鼠标在屏幕上的坐标位置

## 4. 技术方案

### 4.1 WebSocket 连接管理

```typescript
// WebSocket 连接示例
const ws = new WebSocket('ws://localhost:8080/ws/screen/device_id');
ws.binaryType = 'arraybuffer';

ws.onmessage = (event) => {
  // event.data 是 ArrayBuffer，JPEG 原始数据
  const blob = new Blob([event.data], { type: 'image/jpeg' });
  const url = URL.createObjectURL(blob);
  // 更新屏幕图片
};

ws.onclose = (event) => {
  if (event.code === 1008) {
    // 连接数超限
  } else if (event.code === 1001) {
    // 发送超时
  }
};
```

### 4.2 前端组件结构

```
web/apps/web-ele/src/views/device-debug/
├── index.vue              # 主页面入口
├── components/
│   ├── ScreenDisplay.vue  # 实时屏幕展示组件
│   ├── TopNavbar.vue      # 顶部导航栏
│   ├── BottomToolbar.vue  # 底部工具栏
│   ├── MobilePanel.vue    # 移动端右侧面板
│   ├── UnlockDialog.vue   # 解锁屏幕弹窗
│   ├── InstallAppDialog.vue # 安装APP弹窗
│   ├── KeyPressDialog.vue # 按键操作弹窗
│   └── InputTextDialog.vue # 输入文本弹窗
├── hooks/
│   ├── useWebSocket.ts    # WebSocket 连接管理
│   ├── useScreenInteraction.ts # 屏幕交互（点击/滑动）
│   └── useDeviceAction.ts # 设备操作（按键/输入/安装）
├── types.ts               # 类型定义
└── utils.ts               # 工具函数
```

### 4.3 路由配置

新增独立页面路由：

```typescript
// web/apps/web-ele/src/router/routes/modules/device-debug.ts
{
  path: '/device-debug/:deviceId',
  name: 'DeviceDebug',
  component: () => import('#/views/device-debug/index.vue'),
  meta: {
    title: '设备调试',
    hideMenu: true,  // 不显示在侧边栏
  },
}
```

### 4.4 从设备列表页面跳转

修改 `env-machine/list.vue`，点击「调试」按钮时跳转到独立页面：

```typescript
import { useRouter } from 'vue-router';

const router = useRouter();

function handleDebug(row: EnvMachine) {
  router.push(`/device-debug/${row.id}`);
}
```

## 5. 设备类型判断

根据 `device_type` 字段判断布局方式：

```typescript
const isMobileDevice = (deviceType: string) => {
  return ['ios', 'android'].includes(deviceType);
};

const isDesktopDevice = (deviceType: string) => {
  return ['windows', 'mac'].includes(deviceType);
};
```

## 6. 状态显示

- **WebSocket 连接状态**：实时显示连接状态（已连接/断开）
- **帧率显示**：显示当前推流帧率（10 fps）
- **LIVE 标识**：屏幕上的实时标识
- **坐标显示**：鼠标在屏幕上的坐标位置
- **操作统计**：已发送的点击次数、滑动次数

## 7. 错误处理

- WebSocket 连接失败时显示错误提示
- 连接数超限（1008）时提示用户稍后重试
- 发送超时（1001）时自动重连，策略如下：
  - 重试次数：最多 3 次
  - 重试间隔：每次间隔 2 秒
  - 重试失败后提示用户手动刷新
- 操作失败时显示错误信息

## 8. 后续扩展

以下功能需要后续 Worker 支持：

- **APP 安装功能**：需要 Worker 实现 APP 上传和安装接口
- **解锁屏幕密码**：需要 Worker 实现带密码的解锁接口

---

**设计日期**: 2026-04-22
**设计状态**: 待审核