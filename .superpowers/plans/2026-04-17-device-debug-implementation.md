# 设备调试功能实现计划

基于设计文档 `docs/superpowers/specs/2026-04-17-device-debug-design.md`

## 实现步骤

### 1. 后端 API - 调试操作代理接口

**文件**: `backend-fastapi/core/env_machine/api.py`

新增接口：
```python
@router.post("/{machine_id}/debug-action", summary="设备调试操作")
async def debug_device_action(machine_id: str, data: DebugActionRequest, db: AsyncSession = Depends(get_db)):
    """
    代理转发调试操作到 Worker
    
    流程：
    1. 根据 machine_id 查询设备信息（ip, port, device_type, device_sn）
    2. 构造 Worker API 请求体
    3. POST http://{ip}:{port}/task/execute
    4. 返回结果
    """
```

**文件**: `backend-fastapi/core/env_machine/schema.py`

新增 Schema：
```python
class DebugActionRequest(BaseModel):
    action_type: str  # click/swipe/input/press/screenshot
    params: Dict[str, Any]  # 操作参数

class DebugActionResponse(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]]  # screenshot_base64 等
```

---

### 2. 前端 API 定义

**文件**: `web/apps/web-ele/src/api/core/env-machine.ts`

新增接口：
```typescript
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

export function debugDeviceActionApi(deviceId: string, params: DebugActionParams): Promise<DebugActionResult>;
```

---

### 3. 前端组件 - 调试弹窗

**新建文件**: `web/apps/web-ele/src/views/env-machine/DebugDialog.vue`

核心功能：
- 三栏布局：操作历史（左）+ 截图预览（中）+ 工具栏（右）
- 截图点击操作（显示坐标指示器）
- 鼠标悬停显示坐标
- 刷新截图按钮
- 快捷滑动（四个方向）
- 文本输入
- 操作历史记录

交互控制：
- `isOperating` 状态锁
- 点击防抖（500ms）
- 操作最小间隔（300ms）
- 超时处理（10s）
- 截图冷却（2s）
- 操作成功后自动刷新截图

**新建文件**: `web/apps/web-ele/src/views/env-machine/modules/SwipeDialog.vue`

自定义滑动弹窗：
- 起点/终点坐标输入
- 滑动时长输入
- 可在截图上拖拽选择起点终点

**新建文件**: `web/apps/web-ele/src/views/env-machine/modules/KeyPressDialog.vue`

按键选择弹窗：
- 6个按键：Home, Back, Enter, Power, Volume Up, Volume Down
- 点击立即执行

---

### 4. 修改设备列表页面

**文件**: `web/apps/web-ele/src/views/env-machine/list.vue`

修改点：
- 操作列新增"调试"链接
- 条件显示：`isMobileDevice(row.device_type) && row.status === 'online'`
- 点击打开 DebugDialog 弹窗
- 传入设备信息：id, device_type, device_sn, ip, port

---

## 文件清单

| 文件 | 操作 |
|------|------|
| `backend-fastapi/core/env_machine/schema.py` | 新增 DebugActionRequest/Response |
| `backend-fastapi/core/env_machine/api.py` | 新增 debug-action 接口 |
| `web/apps/web-ele/src/api/core/env-machine.ts` | 新增 debugDeviceActionApi |
| `web/apps/web-ele/src/views/env-machine/DebugDialog.vue` | 新建 |
| `web/apps/web-ele/src/views/env-machine/modules/SwipeDialog.vue` | 新建 |
| `web/apps/web-ele/src/views/env-machine/modules/KeyPressDialog.vue` | 新建 |
| `web/apps/web-ele/src/views/env-machine/list.vue` | 修改，添加调试入口 |

---

## 实现顺序

1. 后端 API（schema + api）
2. 前端 API 定义
3. 前端组件（DebugDialog → SwipeDialog → KeyPressDialog）
4. 修改 list.vue 添加入口
5. 测试验证