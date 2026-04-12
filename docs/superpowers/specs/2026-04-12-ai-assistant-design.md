# AI助手中间服务设计文档

## 概述

本设计文档描述 zq-platform 对接 NanoClaw AI 助手服务的 HTTP 中间服务设计方案。

### 核心目标

- 提供 AI 助手功能的管理界面
- 实现与 NanoClaw 的回调模式对接
- 支持上下文管理机制（时间窗口 + 消息数量上限）
- 提供外部 HTTP 接口供第三方系统调用

### 技术选型

| 项目 | 技术栈 |
|------|--------|
| 后端 | FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue 3 + Element Plus |
| 对接模式 | 回调模式 |
| 配置管理 | .env 环境变量 |

---

## 一、数据模型设计

### 1.1 群组表 `ai_assistant_group`

存储外部系统的群组信息，与 NanoClaw 的注册信息对应。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | UUID | 是 | 主键 |
| group_id | String(100) | 是 | 外部系统的群组标识（唯一） |
| group_name | String(200) | 是 | 群组名称 |
| is_group | Boolean | 是 | 是否群聊（默认 true） |
| trigger_word | String(50) | 是 | 触发词，如 `@Andy` |
| requires_trigger | Boolean | 是 | 是否需要触发词（默认 true） |
| is_active | Boolean | 是 | 是否启用（默认 true） |
| last_message_time | DateTime | 否 | 最后消息时间 |
| sort | Integer | 否 | 排序字段 |
| is_deleted | Boolean | 是 | 软删除标记 |
| sys_create_datetime | DateTime | 是 | 创建时间 |
| sys_update_datetime | DateTime | 是 | 更新时间 |

**继承自 BaseModel**：id, sort, is_deleted, sys_create_datetime, sys_update_datetime, sys_creator_id, sys_modifier_id

### 1.2 会话表 `ai_assistant_session`

存储 Session 信息，每个 Session 对应一个 NanoClaw 的 chat_id。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | UUID | 是 | 主键 |
| group_id | String(100) | 是 | 关联的群组ID（逻辑外键） |
| chat_id | String(150) | 是 | NanoClaw的chat_id，格式：`{group_id}_{YYYYMMDD}_{HHMMSS}` |
| session_name | String(200) | 否 | 会话名称（可选） |
| message_count | Integer | 是 | 当前消息计数（默认 0） |
| status | Integer | 是 | 状态：0-活跃，1-已关闭，2-已清除（默认 0） |
| start_time | DateTime | 是 | 会话开始时间 |
| last_message_time | DateTime | 是 | 最后消息时间 |
| is_active | Boolean | 是 | 是否活跃（默认 true） |
| sort | Integer | 否 | 排序字段 |
| is_deleted | Boolean | 是 | 软删除标记 |
| sys_create_datetime | DateTime | 是 | 创建时间 |
| sys_update_datetime | DateTime | 是 | 更新时间 |

**继承自 BaseModel**

**chat_id生成规则**：
```
chat_id = {group_id}_{YYYYMMDD}_{HHMMSS}
示例：tech-group-001_20260412_143000
```

### 1.3 消息表 `ai_assistant_message`

存储所有对话消息。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | UUID | 是 | 主键 |
| session_id | String(36) | 是 | 关联的会话ID（逻辑外键） |
| message_type | Integer | 是 | 消息类型：0-用户消息，1-AI回复 |
| sender_id | String(100) | 是 | 发送者ID |
| sender_name | String(100) | 否 | 发送者名称 |
| content | Text | 是 | 消息内容 |
| nanoclaw_message_id | String(100) | 否 | NanoClaw返回的消息ID |
| reply_to_message_id | String(100) | 否 | 回复的消息ID |
| send_time | DateTime | 是 | 发送时间 |
| receive_time | DateTime | 否 | 接收时间（AI回复时） |
| is_context_recovery | Boolean | 否 | 是否为上下文恢复消息（清除后重发） |
| sort | Integer | 否 | 排序字段 |
| is_deleted | Boolean | 是 | 软删除标记 |
| sys_create_datetime | DateTime | 是 | 创建时间 |
| sys_update_datetime | DateTime | 是 | 更新时间 |

**继承自 BaseModel**

### 1.4 数据关系

```
ai_assistant_group (群组)
    │
    ├──→ ai_assistant_session (会话) [1:N]
    │        │
    │        ├──→ ai_assistant_message (消息) [1:N]
```

- 一个群组可以有多个会话（基于时间窗口切换）
- 一个会话可以有多条消息（最多50条后触发清除）

---

## 二、API接口设计

### 2.1 群组管理接口（需鉴权）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/core/ai-group` | GET | 群组列表（分页） |
| `/api/core/ai-group/{id}` | GET | 群组详情 |
| `/api/core/ai-group` | POST | 创建群组 |
| `/api/core/ai-group/{id}` | PUT | 更新群组 |
| `/api/core/ai-group/{id}` | DELETE | 删除群组（软删除） |
| `/api/core/ai-group/{id}/sessions` | GET | 获取群组的会话列表 |

### 2.2 会话管理接口（需鉴权）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/core/ai-session` | GET | 会话列表（支持按群组筛选） |
| `/api/core/ai-session/{id}` | GET | 会话详情（含消息列表） |
| `/api/core/ai-session/{id}/messages` | GET | 会话消息列表（支持分页） |
| `/api/core/ai-session/{id}/send` | POST | 在会话中发送消息 |
| `/api/core/ai-session/{id}/clear` | POST | 清除上下文 |
| `/api/core/ai-session/{id}/close` | POST | 关闭会话 |
| `/api/core/ai-session/{id}/new-session` | POST | 为群组创建新会话 |

### 2.3 外部接口（无需鉴权）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/public/sendmsg` | POST | 外部系统发送消息入口 |
| `/api/public/callback/message` | POST | NanoClaw回调接口 |

### 2.4 外部接口详细设计

#### 2.4.1 `/api/public/sendmsg` - 发送消息入口

**请求体**：
```json
{
  "group_id": "external-group-001",
  "sender_id": "user-123",
  "sender_name": "张三",
  "content": "@Andy 请帮我写一个排序函数",
  "is_group": true,
  "group_name": "技术讨论群"
}
```

**响应**：
```json
{
  "status": "ok",
  "session_id": "session-uuid",
  "chat_id": "group-001_20260412_143000",
  "message_id": "message-uuid"
}
```

#### 2.4.2 `/api/public/callback/message` - NanoClaw回调

**请求体**（NanoClaw发送）：
```json
{
  "chat_id": "group-001_20260412_143000",
  "message": "这是AI的回复内容...",
  "timestamp": "2026-04-12T14:35:00Z"
}
```

**响应**：
```json
{
  "status": "ok"
}
```

---

## 三、核心流程设计

### 3.1 外部消息处理流程

```
外部系统 → POST /api/public/sendmsg
         │
         ▼
    ┌────────────────────────────────────┐
    │  1. 查找群组（by group_id）         │
    │     - 不存在则自动创建              │
    │     - trigger_word 使用传入值       │
    │       或默认值 "@Andy"              │
    │     - requires_trigger 默认 true   │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  2. 查找活跃会话                    │
    │     - 条件：last_message_time       │
    │       超过2小时 → 创建新会话        │
    │     - 新会话chat_id格式:            │
    │       {group_id}_{datetime}        │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  3. 检查消息数量                    │
    │     - message_count >= 50          │
    │       → 调用 NanoClaw /api/clear    │
    │       → 获取最近10条消息            │
    │       → 创建新会话并发送上下文      │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  4. 向 NanoClaw 注册群组            │
    │     - POST /api/register           │
    │     - 使用会话的 chat_id            │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  5. 发送消息到 NanoClaw             │
    │     - POST /api/message            │
    │     - 使用会话的 chat_id            │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  6. 存储用户消息                    │
    │     - 记录到 ai_assistant_message   │
    │     - 更新会话 message_count       │
    │     - 更新 last_message_time       │
    └────────────────────────────────────┘
         │
         ▼
    返回响应 → 外部系统
```

### 3.2 NanoClaw回调处理流程

```
NanoClaw → POST /api/public/callback/message
         │
         ▼
    ┌────────────────────────────────────┐
    │  1. 根据 chat_id 找到会话          │
    │     - chat_id格式: {group_id}_{dt} │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  2. 存储 AI 回复消息                │
    │     - message_type = 1 (AI回复)    │
    │     - 记录 receive_time             │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  3. 更新会话状态                    │
    │     - message_count += 1           │
    │     - last_message_time 更新       │
    └────────────────────────────────────┘
         │
         ▼
    ┌────────────────────────────────────┐
    │  4. 调用外部系统回复接口            │
    │     - POST 外部 /sendmsg           │
    │     - 传递 AI 回复内容             │
    │     - （如果有配置外部回调地址）    │
    └────────────────────────────────────┘
         │
         ▼
    返回 {"status": "ok"} → NanoClaw
```

### 3.3 上下文清除策略

**触发条件**：
1. **自动触发**：消息数量 >= 50
2. **手动触发**：页面点击"清除上下文"按钮
3. **时间窗口**：超过2小时无消息自动创建新会话

**清除流程**：
```
消息数量 >= 50 时：
│
├─→ 1. 调用 NanoClaw POST /api/clear
│
├─→ 2. 获取最近10条消息（按时间排序）
│
├─→ 3. 将10条消息作为新会话的首批上下文发送给 NanoClaw
│      - 逐条发送 POST /api/message
│      - 标记为"上下文恢复消息"（is_context_recovery = true）
│
├─→ 4. 更新本地会话状态 status = 2 (已清除)
│
├─→ 5. 创建新会话，继承前10条消息
│
└─→ 6. 新会话从第11条消息开始计数
```

---

## 四、前端页面设计

### 4.1 菜单结构

```
AI助手（一级菜单，图标：ep:chat-dot-round）
    │
    ├── 会话管理（二级菜单）
    │       │
    │       ├── 列表页：微信风格会话列表
    │       │
    │       └── 详情页：微信风格聊天界面
    │
    ├── 群组管理（二级菜单）
    │       │
    │       └── Element Plus 表格页面
```

### 4.2 会话管理页面

**设计风格**：
- **列表页**：微信风格会话列表（头像 + 名称 + 预览 + 时间）
- **详情页**：微信风格聊天界面（气泡消息 + 输入框）

**页面布局**：

**列表页**：
```
┌─────────────────────────────────────────────────────┐
│  会话管理                      [搜索框] [搜索按钮]   │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐│
│  │ [头像] 技术讨论群                    10:30      ││
│  │        张三: @Andy 请帮我分析...               ││
│  └─────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────┐│
│  │ [头像] 产品需求群                    08:45  [3] ││
│  │        AI: 好的，我来帮你整理...               ││
│  └─────────────────────────────────────────────────┘│
│  ...                                               │
└─────────────────────────────────────────────────────┘
```

**详情页**：
```
┌─────────────────────────────────────────────────────┐
│  ‹ 技术讨论群  chat_id: tech-group_20260412    ⋮   │
├─────────────────────────────────────────────────────┤
│  消息数: 45/50 | 状态: 活跃 | 开始: 2026-04-12      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────┐          [头像] 张三 │
│  │ @Andy 请帮我写一个...    │                      │
│  │              14:30:00    │                      │
│  └──────────────────────────┘                      │
│                                                     │
│  [头像] AI Andy                                    │
│  ┌──────────────────────────┐                      │
│  │ 好的，这是排序函数...    │                      │
│  │              14:30:45    │                      │
│  └──────────────────────────┐                      │
│                                                     │
│  ...                                               │
├─────────────────────────────────────────────────────┤
│  [输入框: 输入消息（可含 @Andy）]    [发送]        │
└─────────────────────────────────────────────────────┘
```

**操作按钮**（右上角⋮菜单）：
- 清除上下文
- 关闭会话
- 创建新会话

### 4.3 群组管理页面

**设计风格**：Element Plus 表格 + 弹窗

**页面布局**：
```
┌─────────────────────────────────────────────────────┐
│  群组管理                                          │
├─────────────────────────────────────────────────────┤
│  群组ID: [____] 名称: [____] 状态: [全部▼] [查询] │
│                                    [+ 新增群组]    │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐│
│  │ 群组ID │ 群组名称 │ 触发词 │ 群聊 │需触发词│状态││
│  ├─────────────────────────────────────────────────┤│
│  │ grp-01│ 技术群  │ @Andy │  是  │  是   │启用││
│  │ grp-02│ 产品群  │ @Bot  │  是  │  是   │启用││
│  └─────────────────────────────────────────────────┘│
│                              [分页组件]             │
└─────────────────────────────────────────────────────┘
```

**编辑弹窗**：
- 群组ID（必填）
- 群组名称（必填）
- 触发词（必填）
- 是否群聊（复选框）
- 是否需要触发词（复选框）
- 启用状态（复选框）

---

## 五、环境配置

### 5.1 后端配置（.env）

```bash
# NanoClaw 配置
NANOCLAW_API_URL=http://nanoclaw-host:8080
NANOCLAW_API_TOKEN=your-secret-token

# 外部回调配置（可选）
EXTERNAL_CALLBACK_URL=http://external-system/callback

# 上下文管理配置
CONTEXT_TIME_WINDOW=120  # 分钟（2小时）
CONTEXT_MESSAGE_LIMIT=50  # 消息数量上限
CONTEXT_RECOVERY_COUNT=10  # 清除后保留的消息数
```

### 5.2 菜单初始化脚本

```python
# scripts/init_ai_assistant_menu.py
MENUS = [
    {
        "id": "ai-assistant-root",
        "name": "AIAssistant",
        "title": "AI助手",
        "path": "/ai-assistant",
        "type": "catalog",
        "icon": "ep:chat-dot-round",
        "order": 50,
        "parent_id": None,
    },
    {
        "id": "ai-assistant-session",
        "name": "AIAssistantSession",
        "title": "会话管理",
        "path": "/ai-assistant/session",
        "type": "menu",
        "component": "/views/ai-assistant/session/index",
        "parent_id": "ai-assistant-root",
        "order": 1,
    },
    {
        "id": "ai-assistant-group",
        "name": "AIAssistantGroup",
        "title": "群组管理",
        "path": "/ai-assistant/group",
        "type": "menu",
        "component": "/views/ai-assistant/group/index",
        "parent_id": "ai-assistant-root",
        "order": 2,
    },
]
```

---

## 六、后端模块结构

### 6.1 目录结构

```
backend-fastapi/
├── core/
│   ├── ai_assistant/
│   │   ├── model.py          # 数据模型定义
│   │   ├── schema.py         # Pydantic Schema
│   │   ├── service.py        # 业务逻辑层
│   │   ├── api.py            # FastAPI 路由
│   │   └── nanoclaw_client.py # NanoClaw API 客户端
│   │   └── context_manager.py # 上下文管理逻辑
│   │   └── public_api.py     # 外部接口（无需鉴权）
│   └── router.py             # 路由注册
├── scripts/
│   └── init_ai_assistant_menu.py
└── env/
│   └── dev.env               # 环境配置
```

### 6.2 NanoClaw 客户端

```python
# core/ai_assistant/nanoclaw_client.py

class NanoClawClient:
    def __init__(self, api_url: str, token: str):
        self.api_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    
    async def health_check(self) -> dict:
        """健康检查"""
        ...
    
    async def register_group(
        self, 
        chat_id: str, 
        name: str, 
        folder: str, 
        trigger: str,
        is_group: bool = True,
        requires_trigger: bool = True
    ) -> dict:
        """注册群组"""
        ...
    
    async def send_message(
        self,
        chat_id: str,
        sender: str,
        content: str,
        sender_name: str = None
    ) -> dict:
        """发送消息"""
        ...
    
    async def clear_session(self, chat_id: str) -> dict:
        """清除会话"""
        ...
    
    async def get_session_info(self, chat_id: str) -> dict:
        """查询会话状态"""
        ...
```

### 6.3 上下文管理器

```python
# core/ai_assistant/context_manager.py

class ContextManager:
    TIME_WINDOW = 120  # 分钟
    MESSAGE_LIMIT = 50
    RECOVERY_COUNT = 10
    
    async def check_time_window(self, session: Session) -> bool:
        """检查是否需要创建新会话（超过时间窗口）"""
        ...
    
    async def check_message_limit(self, session: Session) -> bool:
        """检查是否需要清除上下文（消息数量上限）"""
        ...
    
    async def create_new_session(
        self, 
        group: Group, 
        carryover_messages: List[Message] = None
    ) -> Session:
        """创建新会话"""
        ...
    
    async def recover_context(
        self, 
        session: Session, 
        messages: List[Message]
    ):
        """恢复上下文（发送历史消息）"""
        ...
```

---

## 七、错误处理

### 7.1 错误码定义

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 404 | 群组或会话不存在 |
| 500 | NanoClaw 调用失败 |

### 7.2 NanoClaw 调用失败处理

- 记录失败日志
- 返回友好错误信息
- 支持重试机制（可选）

---

## 八、测试要点

### 8.1 功能测试

- 外部接口 `/api/public/sendmsg` 消息发送
- NanoClaw 回调 `/api/public/callback/message` 接收
- 上下文管理（时间窗口 + 消息数量）
- 页面发送消息功能

### 8.2 边界测试

- 时间窗口临界值（2小时）
- 消息数量临界值（50条）
- 上下文恢复（10条消息）

---

## 九、实现优先级

### Phase 1：基础功能

1. 数据模型创建 + 数据库迁移
2. 群组管理接口 + 前端页面
3. 外部接口 `/api/public/sendmsg`
4. NanoClaw 回调接口

### Phase 2：会话管理

1. 会话管理接口 + 前端页面
2. 上下文管理逻辑
3. 页面发送消息功能

### Phase 3：完善功能

1. 上下文恢复机制
2. 错误处理优化
3. 性能优化

---

## 附录：NanoClaw API 参考

详见：`.superpowers/brainstorm/202604121440/HTTP_API_INTEGRATION.md`