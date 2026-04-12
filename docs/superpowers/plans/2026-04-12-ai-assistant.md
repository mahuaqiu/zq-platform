# AI助手中间服务实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 zq-platform 对接 NanoClaw AI 助手服务的 HTTP 中间服务，包括群组管理、会话管理、消息存储和外部接口。

**Architecture:** 采用双层会话模型，本系统控制上下文切换（时间窗口 + 消息数量上限），通过回调模式与 NanoClaw 交互。

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL（后端），Vue 3 + Element Plus（前端）

---

## 文件结构

### 后端文件

| 文件 | 职责 |
|------|------|
| `backend-fastapi/core/ai_assistant/model.py` | 数据模型定义（Group、Session、Message） |
| `backend-fastapi/core/ai_assistant/schema.py` | Pydantic Schema 定义 |
| `backend-fastapi/core/ai_assistant/service.py` | 业务逻辑层（继承 BaseService） |
| `backend-fastapi/core/ai_assistant/api.py` | FastAPI 路由（群组管理、会话管理） |
| `backend-fastapi/core/ai_assistant/public_api.py` | 外部接口（无需鉴权） |
| `backend-fastapi/core/ai_assistant/nanoclaw_client.py` | NanoClaw API 客户端封装 |
| `backend-fastapi/core/ai_assistant/context_manager.py` | 上下文管理逻辑 |
| `backend-fastapi/core/router.py` | 注册新模块路由 |
| `backend-fastapi/scripts/init_ai_assistant_menu.py` | 菜单初始化脚本 |
| `backend-fastapi/env/dev.env` | 环境配置（添加 NanoClaw 配置） |

### 前端文件

| 文件 | 职责 |
|------|------|
| `web/apps/web-ele/src/api/core/ai-assistant.ts` | API 接口定义 |
| `web/apps/web-ele/src/views/ai-assistant/group/index.vue` | 群组管理页面 |
| `web/apps/web-ele/src/views/ai-assistant/session/index.vue` | 会话列表页面 |
| `web/apps/web-ele/src/views/ai-assistant/session/detail.vue` | 会话详情页面（聊天界面） |
| `web/apps/web-ele/src/router/routes/modules/ai-assistant.ts` | 路由配置 |

---

## Phase 1：基础功能

### Task 1: 创建后端数据模型

**Files:**
- Create: `backend-fastapi/core/ai_assistant/model.py`

- [ ] **Step 1: 创建 ai_assistant 模块目录**

```bash
mkdir -p backend-fastapi/core/ai_assistant
```

- [ ] **Step 2: 创建 model.py - 群组模型**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: model.py
@Desc: AI助手数据模型 - 群组、会话、消息
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime
from app.base_model import BaseModel


class AIGroup(BaseModel):
    """AI助手群组表"""
    __tablename__ = "ai_assistant_group"
    
    group_id = Column(String(100), unique=True, nullable=False, index=True, comment="外部系统群组ID")
    group_name = Column(String(200), nullable=False, comment="群组名称")
    is_group = Column(Boolean, default=True, nullable=False, comment="是否群聊")
    trigger_word = Column(String(50), nullable=False, default="@Andy", comment="触发词")
    requires_trigger = Column(Boolean, default=True, nullable=False, comment="是否需要触发词")
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否启用")
    last_message_time = Column(DateTime, nullable=True, comment="最后消息时间")
```

- [ ] **Step 3: 添加会话模型到 model.py**

```python
class AISession(BaseModel):
    """AI助手会话表"""
    __tablename__ = "ai_assistant_session"
    
    group_id = Column(String(100), nullable=False, index=True, comment="关联群组ID")
    chat_id = Column(String(150), unique=True, nullable=False, index=True, comment="NanoClaw chat_id")
    session_name = Column(String(200), nullable=True, comment="会话名称")
    message_count = Column(Integer, default=0, nullable=False, comment="消息计数")
    status = Column(Integer, default=0, nullable=False, index=True, comment="状态: 0-活跃, 1-已关闭, 2-已清除")
    start_time = Column(DateTime, nullable=False, default=datetime.now, comment="开始时间")
    last_message_time = Column(DateTime, nullable=False, default=datetime.now, comment="最后消息时间")
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否活跃")
```

- [ ] **Step 4: 添加消息模型到 model.py**

```python
class AIMessage(BaseModel):
    """AI助手消息表"""
    __tablename__ = "ai_assistant_message"
    
    session_id = Column(String(36), nullable=False, index=True, comment="关联会话ID")
    message_type = Column(Integer, nullable=False, index=True, comment="消息类型: 0-用户, 1-AI")
    sender_id = Column(String(100), nullable=False, comment="发送者ID")
    sender_name = Column(String(100), nullable=True, comment="发送者名称")
    content = Column(Text, nullable=False, comment="消息内容")
    nanoclaw_message_id = Column(String(100), nullable=True, comment="NanoClaw消息ID")
    reply_to_message_id = Column(String(100), nullable=True, comment="回复消息ID")
    send_time = Column(DateTime, nullable=False, default=datetime.now, comment="发送时间")
    receive_time = Column(DateTime, nullable=True, comment="接收时间")
    is_context_recovery = Column(Boolean, default=False, nullable=False, comment="是否上下文恢复消息")
```

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/core/ai_assistant/model.py
git commit -m "feat(ai-assistant): add data models for group, session and message"
```

---

### Task 2: 创建数据库迁移

**Files:**
- Modify: `backend-fastapi/alembic/versions/` (新建迁移文件)

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend-fastapi && alembic revision --autogenerate -m "add ai_assistant tables"
```

- [ ] **Step 2: 检查生成的迁移文件**

打开生成的迁移文件，确认包含：
- `ai_assistant_group` 表
- `ai_assistant_session` 表
- `ai_assistant_message` 表

- [ ] **Step 3: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

- [ ] **Step 4: 验证表创建**

```bash
# 使用数据库工具检查表是否存在
# 或者启动后端服务验证
```

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(ai-assistant): add database migration for ai_assistant tables"
```

---

### Task 3: 创建 Schema 定义

**Files:**
- Create: `backend-fastapi/core/ai_assistant/schema.py`

- [ ] **Step 1: 创建 Schema 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: schema.py
@Desc: AI助手 Schema 定义
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field


# ========== 群组 Schema ==========

class AIGroupCreate(BaseModel):
    """创建群组"""
    group_id: str = Field(..., description="外部系统群组ID")
    group_name: str = Field(..., description="群组名称")
    is_group: bool = Field(default=True, description="是否群聊")
    trigger_word: str = Field(default="@Andy", description="触发词")
    requires_trigger: bool = Field(default=True, description="是否需要触发词")
    is_active: bool = Field(default=True, description="是否启用")


class AIGroupUpdate(BaseModel):
    """更新群组"""
    group_name: Optional[str] = None
    is_group: Optional[bool] = None
    trigger_word: Optional[str] = None
    requires_trigger: Optional[bool] = None
    is_active: Optional[bool] = None


class AIGroupResponse(BaseModel):
    """群组响应"""
    id: str
    group_id: str
    group_name: str
    is_group: bool
    trigger_word: str
    requires_trigger: bool
    is_active: bool
    last_message_time: Optional[datetime]
    sys_create_datetime: Optional[datetime]
    sys_update_datetime: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


# ========== 会话 Schema ==========

class AISessionResponse(BaseModel):
    """会话响应"""
    id: str
    group_id: str
    chat_id: str
    session_name: Optional[str]
    message_count: int
    status: int
    start_time: datetime
    last_message_time: datetime
    is_active: bool
    sys_create_datetime: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class AISessionDetail(BaseModel):
    """会话详情（含消息列表）"""
    session: AISessionResponse
    messages: List["AIMessageResponse"]
    group_name: Optional[str] = None


# ========== 消息 Schema ==========

class AIMessageResponse(BaseModel):
    """消息响应"""
    id: str
    session_id: str
    message_type: int
    sender_id: str
    sender_name: Optional[str]
    content: str
    nanoclaw_message_id: Optional[str]
    send_time: datetime
    receive_time: Optional[datetime]
    is_context_recovery: bool
    
    model_config = ConfigDict(from_attributes=True)


class AIMessageSend(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容")


# ========== 外部接口 Schema ==========

class ExternalSendMessage(BaseModel):
    """外部系统发送消息"""
    group_id: str = Field(..., description="外部系统群组ID")
    sender_id: str = Field(..., description="发送者ID")
    sender_name: Optional[str] = Field(None, description="发送者名称")
    content: str = Field(..., description="消息内容")
    is_group: Optional[bool] = Field(True, description="是否群聊")
    group_name: Optional[str] = Field(None, description="群组名称")


class ExternalSendMessageResponse(BaseModel):
    """外部发送消息响应"""
    status: str = "ok"
    session_id: str
    chat_id: str
    message_id: str


class NanoClawCallback(BaseModel):
    """NanoClaw回调消息"""
    chat_id: str = Field(..., description="chat_id")
    message: str = Field(..., description="AI回复内容")
    timestamp: str = Field(..., description="时间戳")


# ========== 分页响应 ==========

class AIGroupListResponse(BaseModel):
    """群组列表响应"""
    items: List[AIGroupResponse]
    total: int


class AISessionListResponse(BaseModel):
    """会话列表响应"""
    items: List[AISessionResponse]
    total: int
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/ai_assistant/schema.py
git commit -m "feat(ai-assistant): add pydantic schemas for api"
```

---

### Task 4: 创建 NanoClaw 客户端

**Files:**
- Create: `backend-fastapi/core/ai_assistant/nanoclaw_client.py`

- [ ] **Step 1: 创建 NanoClaw 客户端文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: nanoclaw_client.py
@Desc: NanoClaw API 客户端封装
"""
import logging
from typing import Optional, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class NanoClawClient:
    """NanoClaw API 客户端"""
    
    def __init__(self):
        self.api_url = settings.NANOCLAW_API_URL
        self.token = settings.NANOCLAW_API_TOKEN
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        url = f"{self.api_url}/api/health"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            return resp.json()
    
    async def register_group(
        self,
        chat_id: str,
        name: str,
        folder: str,
        trigger: str,
        is_group: bool = True,
        requires_trigger: bool = True
    ) -> Dict[str, Any]:
        """注册群组到 NanoClaw"""
        url = f"{self.api_url}/api/register"
        data = {
            "chat_id": chat_id,
            "name": name,
            "folder": folder,
            "trigger": trigger,
            "is_group": is_group,
            "requires_trigger": requires_trigger
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=self.headers, json=data)
            return resp.json()
    
    async def send_message(
        self,
        chat_id: str,
        sender: str,
        content: str,
        sender_name: Optional[str] = None,
        chat_name: Optional[str] = None,
        is_group: bool = True
    ) -> Dict[str, Any]:
        """发送消息到 NanoClaw"""
        url = f"{self.api_url}/api/message"
        data = {
            "chat_id": chat_id,
            "sender": sender,
            "content": content,
            "is_group": is_group
        }
        if sender_name:
            data["sender_name"] = sender_name
        if chat_name:
            data["chat_name"] = chat_name
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=self.headers, json=data)
            return resp.json()
    
    async def clear_session(self, chat_id: str) -> Dict[str, Any]:
        """清除 NanoClaw 会话"""
        url = f"{self.api_url}/api/clear"
        data = {"chat_id": chat_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=self.headers, json=data)
            return resp.json()
    
    async def get_session_info(self, chat_id: str) -> Dict[str, Any]:
        """查询 NanoClaw 会话状态"""
        url = f"{self.api_url}/api/session/{chat_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self.headers)
            return resp.json()


# 全局客户端实例
nanoclaw_client = NanoClawClient()
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/ai_assistant/nanoclaw_client.py
git commit -m "feat(ai-assistant): add nanoclaw api client"
```

---

### Task 5: 创建上下文管理器

**Files:**
- Create: `backend-fastapi/core/ai_assistant/context_manager.py`

- [ ] **Step 1: 创建上下文管理器文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: context_manager.py
@Desc: AI助手上下文管理逻辑
"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.config import settings
from core.ai_assistant.model import AISession, AIMessage, AIGroup
from core.ai_assistant.nanoclaw_client import nanoclaw_client

# 配置常量
TIME_WINDOW_MINUTES = getattr(settings, 'CONTEXT_TIME_WINDOW', 120)  # 2小时
MESSAGE_LIMIT = getattr(settings, 'CONTEXT_MESSAGE_LIMIT', 50)
RECOVERY_COUNT = getattr(settings, 'CONTEXT_RECOVERY_COUNT', 10)


class ContextManager:
    """上下文管理器"""
    
    @staticmethod
    def generate_chat_id(group_id: str) -> str:
        """生成 chat_id: {group_id}_{YYYYMMDD}_{HHMMSS}"""
        now = datetime.now()
        return f"{group_id}_{now.strftime('%Y%m%d_%H%M%S')}"
    
    @staticmethod
    async def check_time_window(session: AISession) -> bool:
        """检查是否超过时间窗口，需要创建新会话"""
        if not session.last_message_time:
            return False
        threshold = timedelta(minutes=TIME_WINDOW_MINUTES)
        return datetime.now() - session.last_message_time > threshold
    
    @staticmethod
    async def check_message_limit(session: AISession) -> bool:
        """检查是否达到消息数量上限"""
        return session.message_count >= MESSAGE_LIMIT
    
    @staticmethod
    async def get_active_session(db: AsyncSession, group_id: str) -> Optional[AISession]:
        """获取群组的活跃会话"""
        result = await db.execute(
            select(AISession).where(
                AISession.group_id == group_id,
                AISession.status == 0,  # 活跃状态
                AISession.is_active == True,
                AISession.is_deleted == False
            ).order_by(desc(AISession.last_message_time))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_new_session(
        db: AsyncSession,
        group: AIGroup,
        carryover_messages: Optional[List[AIMessage]] = None
    ) -> AISession:
        """创建新会话"""
        now = datetime.now()
        chat_id = ContextManager.generate_chat_id(group.group_id)
        
        session = AISession(
            group_id=group.group_id,
            chat_id=chat_id,
            message_count=0,
            status=0,
            start_time=now,
            last_message_time=now,
            is_active=True
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        
        # 注册到 NanoClaw
        await nanoclaw_client.register_group(
            chat_id=chat_id,
            name=group.group_name,
            folder=f"http_{group.group_id}",
            trigger=group.trigger_word,
            is_group=group.is_group,
            requires_trigger=group.requires_trigger
        )
        
        # 如果有继承消息，发送上下文恢复
        if carryover_messages:
            await ContextManager.recover_context(session, carryover_messages)
        
        return session
    
    @staticmethod
    async def recover_context(session: AISession, messages: List[AIMessage]):
        """恢复上下文（发送历史消息到 NanoClaw）"""
        for msg in messages:
            # 标记为上下文恢复消息
            msg.is_context_recovery = True
            # 发送到 NanoClaw
            await nanoclaw_client.send_message(
                chat_id=session.chat_id,
                sender=msg.sender_id,
                content=msg.content,
                sender_name=msg.sender_name
            )
    
    @staticmethod
    async def get_recent_messages(db: AsyncSession, session_id: str, limit: int = 10) -> List[AIMessage]:
        """获取最近N条消息"""
        result = await db.execute(
            select(AIMessage).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False
            ).order_by(desc(AIMessage.send_time)).limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def handle_message_limit(db: AsyncSession, session: AISession) -> Tuple[AISession, List[AIMessage]]:
        """处理消息数量上限：清除上下文并创建新会话"""
        # 1. 调用 NanoClaw 清除
        await nanoclaw_client.clear_session(session.chat_id)
        
        # 2. 获取最近10条消息
        recent_messages = await ContextManager.get_recent_messages(db, session.id, RECOVERY_COUNT)
        
        # 3. 更新会话状态为已清除
        session.status = 2
        
        # 4. 获取群组信息
        group_result = await db.execute(
            select(AIGroup).where(AIGroup.group_id == session.group_id)
        )
        group = group_result.scalar_one_or_none()
        
        # 5. 创建新会话并继承上下文
        new_session = await ContextManager.create_new_session(db, group, recent_messages)
        
        await db.flush()
        return new_session, recent_messages
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/ai_assistant/context_manager.py
git commit -m "feat(ai-assistant): add context manager for session handling"
```

---

### Task 6: 创建 Service 层

**Files:**
- Create: `backend-fastapi/core/ai_assistant/service.py`

- [ ] **Step 1: 创建 Service 文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: service.py
@Desc: AI助手业务逻辑层
"""
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.ai_assistant.model import AIGroup, AISession, AIMessage
from core.ai_assistant.schema import AIGroupCreate, AIGroupUpdate
from core.ai_assistant.context_manager import ContextManager
from core.ai_assistant.nanoclaw_client import nanoclaw_client


class AIGroupService(BaseService[AIGroup, AIGroupCreate, AIGroupUpdate]):
    """群组服务"""
    model = AIGroup
    
    @classmethod
    async def get_by_group_id(cls, db: AsyncSession, group_id: str) -> Optional[AIGroup]:
        """根据外部 group_id 获取群组"""
        result = await db.execute(
            select(AIGroup).where(
                AIGroup.group_id == group_id,
                AIGroup.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        group_id: Optional[str] = None,
        group_name: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[AIGroup], int]:
        """带筛选条件的列表查询"""
        query = select(AIGroup).where(AIGroup.is_deleted == False)
        
        if group_id:
            query = query.where(AIGroup.group_id.ilike(f"%{group_id}%"))
        if group_name:
            query = query.where(AIGroup.group_name.ilike(f"%{group_name}%"))
        if is_active is not None:
            query = query.where(AIGroup.is_active == is_active)
        
        # 排序
        query = query.order_by(desc(AIGroup.sys_create_datetime))
        
        # 计数
        count_query = select(AIGroup).where(AIGroup.is_deleted == False)
        if group_id:
            count_query = count_query.where(AIGroup.group_id.ilike(f"%{group_id}%"))
        if group_name:
            count_query = count_query.where(AIGroup.group_name.ilike(f"%{group_name}%"))
        if is_active is not None:
            count_query = count_query.where(AIGroup.is_active == is_active)
        
        count_result = await db.execute(count_query)
        total = len(list(count_result.scalars().all()))
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        return items, total
    
    @classmethod
    async def auto_create_group(cls, db: AsyncSession, group_id: str, group_name: str, is_group: bool = True) -> AIGroup:
        """自动创建群组（外部接口调用时）"""
        group = AIGroup(
            group_id=group_id,
            group_name=group_name,
            is_group=is_group,
            trigger_word="@Andy",
            requires_trigger=True,
            is_active=True
        )
        db.add(group)
        await db.flush()
        await db.refresh(group)
        return group


class AISessionService(BaseService[AISession, None, None]):
    """会话服务"""
    model = AISession
    
    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        group_id: Optional[str] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[AISession], int]:
        """带筛选条件的会话列表"""
        query = select(AISession).where(AISession.is_deleted == False)
        
        if group_id:
            query = query.where(AISession.group_id == group_id)
        if status is not None:
            query = query.where(AISession.status == status)
        
        query = query.order_by(desc(AISession.last_message_time))
        
        # 计数
        count_result = await db.execute(query)
        total = len(list(count_result.scalars().all()))
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        return items, total
    
    @classmethod
    async def get_session_with_messages(cls, db: AsyncSession, session_id: str) -> Optional[dict]:
        """获取会话详情含消息列表"""
        session = await cls.get_by_id(db, session_id)
        if not session:
            return None
        
        # 获取消息列表
        msg_result = await db.execute(
            select(AIMessage).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False
            ).order_by(AIMessage.send_time)
        )
        messages = list(msg_result.scalars().all())
        
        # 获取群组名称
        group_result = await db.execute(
            select(AIGroup).where(AIGroup.group_id == session.group_id)
        )
        group = group_result.scalar_one_or_none()
        
        return {
            "session": session,
            "messages": messages,
            "group_name": group.group_name if group else None
        }
    
    @classmethod
    async def close_session(cls, db: AsyncSession, session_id: str) -> bool:
        """关闭会话"""
        session = await cls.get_by_id(db, session_id)
        if not session:
            return False
        session.status = 1  # 已关闭
        session.is_active = False
        await db.flush()
        return True


class AIMessageService(BaseService[AIMessage, None, None]):
    """消息服务"""
    model = AIMessage
    
    @classmethod
    async def create_user_message(
        cls,
        db: AsyncSession,
        session_id: str,
        sender_id: str,
        content: str,
        sender_name: Optional[str] = None
    ) -> AIMessage:
        """创建用户消息"""
        now = datetime.now()
        message = AIMessage(
            session_id=session_id,
            message_type=0,  # 用户消息
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            send_time=now
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return message
    
    @classmethod
    async def create_ai_message(
        cls,
        db: AsyncSession,
        session_id: str,
        content: str,
        receive_time: datetime = None
    ) -> AIMessage:
        """创建AI回复消息"""
        message = AIMessage(
            session_id=session_id,
            message_type=1,  # AI回复
            sender_id="nanoclaw",
            sender_name="AI",
            content=content,
            send_time=datetime.now(),
            receive_time=receive_time or datetime.now()
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return message
    
    @classmethod
    async def update_session_message_count(cls, db: AsyncSession, session_id: str):
        """更新会话消息计数"""
        result = await db.execute(
            select(AISession).where(AISession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.message_count += 1
            session.last_message_time = datetime.now()
            await db.flush()
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/ai_assistant/service.py
git commit -m "feat(ai-assistant): add service layer for group, session and message"
```

---

### Task 7: 创建外部接口 API

**Files:**
- Create: `backend-fastapi/core/ai_assistant/public_api.py`

- [ ] **Step 1: 创建外部接口文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: public_api.py
@Desc: AI助手外部接口（无需鉴权）
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from core.ai_assistant.schema import (
    ExternalSendMessage,
    ExternalSendMessageResponse,
    NanoClawCallback
)
from core.ai_assistant.service import AIGroupService, AISessionService, AIMessageService
from core.ai_assistant.model import AIGroup
from core.ai_assistant.context_manager import ContextManager
from core.ai_assistant.nanoclaw_client import nanoclaw_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["AI助手外部接口"])


@router.post("/sendmsg", response_model=ExternalSendMessageResponse, summary="外部发送消息")
async def external_send_message(
    data: ExternalSendMessage,
    db: AsyncSession = Depends(get_db)
) -> ExternalSendMessageResponse:
    """
    外部系统发送消息入口
    
    处理流程：
    1. 查找或创建群组
    2. 获取或创建活跃会话（检查时间窗口）
    3. 检查消息数量上限
    4. 发送消息到 NanoClaw
    5. 存储消息记录
    """
    try:
        # 1. 查找或创建群组
        group = await AIGroupService.get_by_group_id(db, data.group_id)
        if not group:
            group_name = data.group_name or data.group_id
            group = await AIGroupService.auto_create_group(
                db, data.group_id, group_name, data.is_group or True
            )
        
        if not group.is_active:
            raise HTTPException(status_code=400, detail="群组已禁用")
        
        # 2. 获取活跃会话
        session = await ContextManager.get_active_session(db, data.group_id)
        
        need_new_session = False
        carryover_messages = None
        
        if session:
            # 检查时间窗口
            if await ContextManager.check_time_window(session):
                need_new_session = True
                logger.info(f"会话超过时间窗口，创建新会话: {session.chat_id}")
            
            # 检查消息数量上限
            elif await ContextManager.check_message_limit(session):
                session, carryover_messages = await ContextManager.handle_message_limit(db, session)
                logger.info(f"会话达到消息上限，已清除并创建新会话: {session.chat_id}")
        else:
            need_new_session = True
        
        # 创建新会话
        if need_new_session:
            session = await ContextManager.create_new_session(db, group)
            logger.info(f"创建新会话: {session.chat_id}")
        
        # 3. 发送消息到 NanoClaw
        nanoclaw_resp = await nanoclaw_client.send_message(
            chat_id=session.chat_id,
            sender=data.sender_id,
            content=data.content,
            sender_name=data.sender_name,
            chat_name=group.group_name,
            is_group=group.is_group
        )
        
        # 4. 存储用户消息
        message = await AIMessageService.create_user_message(
            db, session.id, data.sender_id, data.content, data.sender_name
        )
        
        # 更新消息计数
        await AIMessageService.update_session_message_count(db, session.id)
        
        # 更新群组最后消息时间
        group.last_message_time = datetime.now()
        
        await db.commit()
        
        logger.info(f"外部消息发送成功: group={data.group_id}, session={session.id}")
        
        return ExternalSendMessageResponse(
            status="ok",
            session_id=session.id,
            chat_id=session.chat_id,
            message_id=message.id
        )
    
    except Exception as e:
        await db.rollback()
        logger.error(f"外部消息发送失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callback/message", summary="NanoClaw回调接口")
async def nanoclaw_callback(
    data: NanoClawCallback,
    db: AsyncSession = Depends(get_db)
):
    """
    NanoClaw AI回复回调接口
    
    处理流程：
    1. 根据 chat_id 找到会话
    2. 存储 AI 回复消息
    3. 更新会话状态
    """
    try:
        # 1. 根据 chat_id 找到会话
        from sqlalchemy import select
        from core.ai_assistant.model import AISession
        
        result = await db.execute(
            select(AISession).where(AISession.chat_id == data.chat_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.warning(f"未找到对应会话: chat_id={data.chat_id}")
            return {"status": "ok", "message": "session not found"}
        
        # 2. 存储 AI 回复消息
        receive_time = datetime.fromisoformat(data.timestamp.replace('Z', '+00:00'))
        await AIMessageService.create_ai_message(
            db, session.id, data.message, receive_time
        )
        
        # 3. 更新会话状态
        await AIMessageService.update_session_message_count(db, session.id)
        
        await db.commit()
        
        logger.info(f"NanoClaw回调处理成功: chat_id={data.chat_id}")
        
        return {"status": "ok"}
    
    except Exception as e:
        await db.rollback()
        logger.error(f"NanoClaw回调处理失败: {e}")
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/ai_assistant/public_api.py
git commit -m "feat(ai-assistant): add public api for external sendmsg and nanoclaw callback"
```

---

### Task 8: 创建管理接口 API

**Files:**
- Create: `backend-fastapi/core/ai_assistant/api.py`

- [ ] **Step 1: 创建管理接口文件**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: api.py
@Desc: AI助手管理接口（需鉴权）
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.base_schema import PaginatedResponse
from core.ai_assistant.schema import (
    AIGroupCreate, AIGroupUpdate, AIGroupResponse,
    AISessionResponse, AISessionDetail, AIMessageResponse,
    AIMessageSend
)
from core.ai_assistant.service import AIGroupService, AISessionService, AIMessageService
from core.ai_assistant.model import AISession
from core.ai_assistant.context_manager import ContextManager
from core.ai_assistant.nanoclaw_client import nanoclaw_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI助手管理"])


# ========== 群组管理接口 ==========

@router.get("/group", response_model=PaginatedResponse[AIGroupResponse], summary="群组列表")
async def list_groups(
    group_id: Optional[str] = None,
    group_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取群组列表"""
    items, total = await AIGroupService.get_list_with_filters(
        db, group_id, group_name, is_active, page, page_size
    )
    return PaginatedResponse(
        items=[AIGroupResponse.model_validate(i) for i in items],
        total=total
    )


@router.get("/group/{group_id}", response_model=AIGroupResponse, summary="群组详情")
async def get_group(group_id: str, db: AsyncSession = Depends(get_db)):
    """获取群组详情"""
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    return AIGroupResponse.model_validate(group)


@router.post("/group", response_model=AIGroupResponse, summary="创建群组")
async def create_group(data: AIGroupCreate, db: AsyncSession = Depends(get_db)):
    """创建群组"""
    # 检查 group_id 是否已存在
    existing = await AIGroupService.get_by_group_id(db, data.group_id)
    if existing:
        raise HTTPException(status_code=400, detail="群组ID已存在")
    
    group = await AIGroupService.create(db, data)
    return AIGroupResponse.model_validate(group)


@router.put("/group/{group_id}", response_model=AIGroupResponse, summary="更新群组")
async def update_group(group_id: str, data: AIGroupUpdate, db: AsyncSession = Depends(get_db)):
    """更新群组"""
    group = await AIGroupService.update(db, group_id, data)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    return AIGroupResponse.model_validate(group)


@router.delete("/group/{group_id}", summary="删除群组")
async def delete_group(group_id: str, db: AsyncSession = Depends(get_db)):
    """删除群组（软删除）"""
    await AIGroupService.delete(db, group_id)
    return {"status": "ok", "message": "删除成功"}


@router.get("/group/{group_id}/sessions", response_model=PaginatedResponse[AISessionResponse], summary="群组会话列表")
async def get_group_sessions(
    group_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取群组的会话列表"""
    # 通过 group_id 字段查询（不是主键）
    items, total = await AISessionService.get_list_with_filters(
        db, group_id=group_id, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[AISessionResponse.model_validate(i) for i in items],
        total=total
    )


# ========== 会话管理接口 ==========

@router.get("/session", response_model=PaginatedResponse[AISessionResponse], summary="会话列表")
async def list_sessions(
    group_id: Optional[str] = None,
    status: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取会话列表"""
    items, total = await AISessionService.get_list_with_filters(
        db, group_id, status, page, page_size
    )
    return PaginatedResponse(
        items=[AISessionResponse.model_validate(i) for i in items],
        total=total
    )


@router.get("/session/{session_id}", response_model=AISessionDetail, summary="会话详情")
async def get_session_detail(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取会话详情（含消息列表）"""
    data = await AISessionService.get_session_with_messages(db, session_id)
    if not data:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return AISessionDetail(
        session=AISessionResponse.model_validate(data["session"]),
        messages=[AIMessageResponse.model_validate(m) for m in data["messages"]],
        group_name=data["group_name"]
    )


@router.post("/session/{session_id}/send", summary="发送消息")
async def send_message_in_session(
    session_id: str,
    data: AIMessageSend,
    db: AsyncSession = Depends(get_db)
):
    """在会话中发送消息"""
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status != 0:
        raise HTTPException(status_code=400, detail="会话已关闭或已清除")
    
    # 发送到 NanoClaw
    # 获取群组信息
    from sqlalchemy import select
    from core.ai_assistant.model import AIGroup
    group_result = await db.execute(
        select(AIGroup).where(AIGroup.group_id == session.group_id)
    )
    group = group_result.scalar_one_or_none()
    
    await nanoclaw_client.send_message(
        chat_id=session.chat_id,
        sender="system",
        content=data.content,
        sender_name="系统用户",
        chat_name=group.group_name if group else None
    )
    
    # 存储消息
    await AIMessageService.create_user_message(
        db, session_id, "system", data.content, "系统用户"
    )
    
    # 更新计数
    await AIMessageService.update_session_message_count(db, session_id)
    
    await db.commit()
    
    return {"status": "ok", "message": "消息已发送"}


@router.post("/session/{session_id}/clear", summary="清除上下文")
async def clear_session_context(session_id: str, db: AsyncSession = Depends(get_db)):
    """清除会话上下文"""
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 调用 NanoClaw 清除
    await nanoclaw_client.clear_session(session.chat_id)
    
    # 更新状态
    session.status = 2  # 已清除
    
    await db.commit()
    
    return {"status": "ok", "message": "上下文已清除"}


@router.post("/session/{session_id}/close", summary="关闭会话")
async def close_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """关闭会话"""
    success = await AISessionService.close_session(db, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    await db.commit()
    
    return {"status": "ok", "message": "会话已关闭"}


@router.post("/session/{session_id}/new-session", summary="创建新会话")
async def create_new_session_for_group(session_id: str, db: AsyncSession = Depends(get_db)):
    """为会话所属群组创建新会话"""
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 获取群组
    from sqlalchemy import select
    from core.ai_assistant.model import AIGroup
    group_result = await db.execute(
        select(AIGroup).where(AIGroup.group_id == session.group_id)
    )
    group = group_result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    
    # 创建新会话
    new_session = await ContextManager.create_new_session(db, group)
    
    await db.commit()
    
    return {"status": "ok", "session_id": new_session.id, "chat_id": new_session.chat_id}
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/ai_assistant/api.py
git commit -m "feat(ai-assistant): add management api for group and session"
```

---

### Task 9: 注册路由

**Files:**
- Modify: `backend-fastapi/core/router.py`

- [ ] **Step 1: 在 router.py 中导入并注册路由**

在文件顶部添加导入：
```python
from core.ai_assistant.api import router as ai_assistant_router
from core.ai_assistant.public_api import router as ai_public_router
```

在路由注册部分添加：
```python
router.include_router(ai_assistant_router)
router.include_router(ai_public_router)
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/core/router.py
git commit -m "feat(ai-assistant): register ai_assistant routes"
```

---

### Task 10: 添加环境配置

**Files:**
- Modify: `backend-fastapi/env/dev.env`
- Modify: `backend-fastapi/app/config.py`

- [ ] **Step 1: 添加 NanoClaw 配置到 dev.env**

```bash
# NanoClaw API 配置
NANOCLAW_API_URL=http://localhost:8080
NANOCLAW_API_TOKEN=your-secret-token

# 上下文管理配置
CONTEXT_TIME_WINDOW=120
CONTEXT_MESSAGE_LIMIT=50
CONTEXT_RECOVERY_COUNT=10
```

- [ ] **Step 2: 在 app/config.py 中添加配置字段**

在 Settings 类中添加以下字段（如果不存在）：

```python
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # NanoClaw 配置
    NANOCLAW_API_URL: str = "http://localhost:8080"
    NANOCLAW_API_TOKEN: str = ""
    
    # 上下文管理配置
    CONTEXT_TIME_WINDOW: int = 120  # 分钟
    CONTEXT_MESSAGE_LIMIT: int = 50  # 消息数量上限
    CONTEXT_RECOVERY_COUNT: int = 10  # 清除后保留消息数
```

- [ ] **Step 3: 验证配置加载**

启动后端服务，确认配置正确加载：
```bash
cd backend-fastapi && python -c "from app.config import settings; print(settings.NANOCLAW_API_URL)"
```

- [ ] **Step 4: Commit**

```bash
git add backend-fastapi/env/dev.env backend-fastapi/app/config.py
git commit -m "feat(ai-assistant): add nanoclaw configuration"
```

---

## Phase 2：前端页面

### Task 11: 创建前端 API 接口

**Files:**
- Create: `web/apps/web-ele/src/api/core/ai-assistant.ts`

- [ ] **Step 1: 创建 API 接口文件**

```typescript
import { requestClient } from '#/api/request';

// ========== 类型定义 ==========

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

export interface AISession {
  id: string;
  group_id: string;
  chat_id: string;
  session_name?: string;
  message_count: number;
  status: number; // 0-活跃, 1-已关闭, 2-已清除
  start_time: string;
  last_message_time: string;
  is_active: boolean;
  sys_create_datetime?: string;
}

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

export interface AISessionDetail {
  session: AISession;
  messages: AIMessage[];
  group_name?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

// ========== 群组 API ==========

export async function getAIGroupListApi(params: {
  group_id?: string;
  group_name?: string;
  is_active?: boolean;
  page: number;
  page_size: number;
}) {
  return requestClient.get<PaginatedResponse<AIGroup>>('/api/core/ai/group', { params });
}

export async function getAIGroupDetailApi(id: string) {
  return requestClient.get<AIGroup>(`/api/core/ai/group/${id}`);
}

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

export async function updateAIGroupApi(id: string, data: Partial<AIGroup>) {
  return requestClient.put<AIGroup>(`/api/core/ai/group/${id}`, data);
}

export async function deleteAIGroupApi(id: string) {
  return requestClient.delete(`/api/core/ai/group/${id}`);
}

// ========== 会话 API ==========

export async function getAISessionListApi(params: {
  group_id?: string;
  status?: number;
  page: number;
  page_size: number;
}) {
  return requestClient.get<PaginatedResponse<AISession>>('/api/core/ai/session', { params });
}

export async function getAISessionDetailApi(id: string) {
  return requestClient.get<AISessionDetail>(`/api/core/ai/session/${id}`);
}

export async function sendMessageInSessionApi(sessionId: string, content: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/send`, { content });
}

export async function clearSessionContextApi(sessionId: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/clear`);
}

export async function closeSessionApi(sessionId: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/close`);
}

export async function createNewSessionApi(sessionId: string) {
  return requestClient.post(`/api/core/ai/session/${sessionId}/new-session`);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/api/core/ai-assistant.ts
git commit -m "feat(ai-assistant): add frontend api definitions"
```

---

### Task 12: 创建群组管理页面

**Files:**
- Create: `web/apps/web-ele/src/views/ai-assistant/group/index.vue`

- [ ] **Step 1: 创建群组管理页面**

```vue
<script lang="ts" setup>
import type { AIGroup } from '#/api/core/ai-assistant';

import { ref, onMounted } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import {
  getAIGroupListApi,
  createAIGroupApi,
  updateAIGroupApi,
  deleteAIGroupApi,
} from '#/api/core/ai-assistant';

defineOptions({ name: 'AIGroupPage' });

// 数据
const tableData = ref<AIGroup[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 筛选条件
const searchForm = ref({
  group_id: '',
  group_name: '',
  is_active: undefined as boolean | undefined,
});

// 弹窗
const dialogVisible = ref(false);
const dialogLoading = ref(false);
const isEdit = ref(false);
const editId = ref('');

// 表单数据
const formData = ref({
  group_id: '',
  group_name: '',
  is_group: true,
  trigger_word: '@Andy',
  requires_trigger: true,
  is_active: true,
});

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getAIGroupListApi({
      group_id: searchForm.value.group_id || undefined,
      group_name: searchForm.value.group_name || undefined,
      is_active: searchForm.value.is_active,
      page: currentPage.value,
      page_size: pageSize.value,
    });
    tableData.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
}

// 重置
function handleReset() {
  searchForm.value = {
    group_id: '',
    group_name: '',
    is_active: undefined,
  };
  currentPage.value = 1;
  loadData();
}

// 新增
function handleCreate() {
  isEdit.value = false;
  editId.value = '';
  formData.value = {
    group_id: '',
    group_name: '',
    is_group: true,
    trigger_word: '@Andy',
    requires_trigger: true,
    is_active: true,
  };
  dialogVisible.value = true;
}

// 编辑
function handleEdit(row: AIGroup) {
  isEdit.value = true;
  editId.value = row.id;
  formData.value = {
    group_id: row.group_id,
    group_name: row.group_name,
    is_group: row.is_group,
    trigger_word: row.trigger_word,
    requires_trigger: row.requires_trigger,
    is_active: row.is_active,
  };
  dialogVisible.value = true;
}

// 删除
function handleDelete(row: AIGroup) {
  ElMessageBox.confirm(`确定要删除群组 "${row.group_name}" 吗？`, '删除确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteAIGroupApi(row.id);
      ElMessage.success('删除成功');
      loadData();
    } catch {
      ElMessage.error('删除失败');
    }
  });
}

// 提交表单
async function handleSubmit() {
  if (!formData.value.group_id || !formData.value.group_name) {
    ElMessage.warning('请填写必填字段');
    return;
  }
  
  dialogLoading.value = true;
  try {
    if (isEdit.value) {
      await updateAIGroupApi(editId.value, formData.value);
      ElMessage.success('更新成功');
    } else {
      await createAIGroupApi(formData.value);
      ElMessage.success('创建成功');
    }
    dialogVisible.value = false;
    loadData();
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '操作失败';
    ElMessage.error(msg);
  } finally {
    dialogLoading.value = false;
  }
}

// 分页
function handlePageChange(page: number) {
  currentPage.value = page;
  loadData();
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col">
      <!-- 搜索区域 -->
      <div class="env-search-area">
        <div class="env-search-form">
          <div class="env-search-item">
            <label class="env-search-label">群组ID</label>
            <ElInput v-model="searchForm.group_id" placeholder="搜索群组ID" clearable style="width: 150px" />
          </div>
          <div class="env-search-item">
            <label class="env-search-label">群组名称</label>
            <ElInput v-model="searchForm.group_name" placeholder="搜索群组名称" clearable style="width: 150px" />
          </div>
          <div class="env-search-item">
            <label class="env-search-label">状态</label>
            <ElSelect v-model="searchForm.is_active" placeholder="全部" clearable style="width: 100px">
              <ElOption label="启用" :value="true" />
              <ElOption label="禁用" :value="false" />
            </ElSelect>
          </div>
          <div class="env-search-buttons">
            <ElButton type="primary" @click="handleSearch">查询</ElButton>
            <ElButton @click="handleReset">重置</ElButton>
          </div>
          <ElButton type="success" class="env-create-btn" @click="handleCreate">+ 新增群组</ElButton>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="env-table-wrapper">
        <ElTable :data="tableData" v-loading="loading" class="env-table" border>
          <ElTableColumn prop="group_id" label="群组ID" min-width="120" />
          <ElTableColumn prop="group_name" label="群组名称" min-width="150" />
          <ElTableColumn prop="trigger_word" label="触发词" min-width="80" />
          <ElTableColumn prop="is_group" label="是否群聊" min-width="80" align="center">
            <template #default="{ row }">
              {{ row.is_group ? '是' : '否' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="requires_trigger" label="需触发词" min-width="80" align="center">
            <template #default="{ row }">
              {{ row.requires_trigger ? '是' : '否' }}
            </template>
          </ElTableColumn>
          <ElTableColumn prop="is_active" label="状态" min-width="80" align="center">
            <template #default="{ row }">
              <span :class="row.is_active ? 'env-status-success' : 'env-status-danger'">
                {{ row.is_active ? '启用' : '禁用' }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" min-width="120">
            <template #default="{ row }">
              <a class="env-link" @click="handleEdit(row)">编辑</a>
              <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 分页 -->
        <div class="env-pagination">
          <ElPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <ElDialog v-model="dialogVisible" :title="isEdit ? '编辑群组' : '新增群组'" width="500px">
      <ElForm label-width="100px">
        <ElFormItem v-if="!isEdit" label="群组ID" required>
          <ElInput v-model="formData.group_id" placeholder="如：tech-group-001" />
        </ElFormItem>
        <ElFormItem label="群组名称" required>
          <ElInput v-model="formData.group_name" placeholder="如：技术讨论群" />
        </ElFormItem>
        <ElFormItem label="触发词" required>
          <ElInput v-model="formData.trigger_word" placeholder="如：@Andy" />
        </ElFormItem>
        <ElFormItem label="是否群聊">
          <ElSelect v-model="formData.is_group" style="width: 100%">
            <ElOption label="是" :value="true" />
            <ElOption label="否" :value="false" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="是否需要触发词">
          <ElSelect v-model="formData.requires_trigger" style="width: 100%">
            <ElOption label="是" :value="true" />
            <ElOption label="否" :value="false" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="启用状态">
          <ElSelect v-model="formData.is_active" style="width: 100%">
            <ElOption label="启用" :value="true" />
            <ElOption label="禁用" :value="false" />
          </ElSelect>
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="dialogLoading" @click="handleSubmit">确定</ElButton>
      </template>
    </ElDialog>
  </Page>
</template>

<style scoped>
/* 使用 env-machine 页面的样式 */
.env-search-area { padding: 16px; margin-bottom: 16px; background: #fafafa; border-radius: 4px; }
.env-search-form { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; }
.env-search-item { display: flex; flex-direction: column; gap: 4px; }
.env-search-label { display: block; font-size: 12px; color: #666; }
.env-search-buttons { display: flex; gap: 8px; align-items: flex-end; }
.env-create-btn { font-weight: 500; color: #fff !important; background: #52c41a !important; border-color: #52c41a !important; }
.env-table-wrapper { flex: 1; padding: 16px; overflow: auto; background: #fff; border-radius: 4px; }
.env-table { --el-table-border-color: #e8e8e8; --el-table-header-bg-color: #fafafa; }
.env-status-success { color: #52c41a; }
.env-status-danger { color: #ff4d4f; }
.env-link { margin-right: 12px; color: #1890ff; cursor: pointer; }
.env-link:hover { text-decoration: underline; }
.env-link-danger { margin-right: 0; color: #ff4d4f; }
.env-pagination { display: flex; justify-content: flex-end; padding: 16px 0 0; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/ai-assistant/group/index.vue
git commit -m "feat(ai-assistant): add group management page"
```

---

### Task 13: 创建会话列表页面

**Files:**
- Create: `web/apps/web-ele/src/views/ai-assistant/session/index.vue`

- [ ] **Step 1: 创建会话列表页面**

```vue
<script lang="ts" setup>
import type { AISession } from '#/api/core/ai-assistant';

import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElInput,
  ElMessage,
} from 'element-plus';

import { getAISessionListApi } from '#/api/core/ai-assistant';

defineOptions({ name: 'AISessionPage' });

const router = useRouter();

// 数据
const sessionList = ref<AISession[]>([]);
const total = ref(0);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

// 搜索
const searchKeyword = ref('');

// 状态映射
const statusMap: Record<number, { text: string; color: string }> = {
  0: { text: '活跃', color: '#52c41a' },
  1: { text: '已关闭', color: '#ff4d4f' },
  2: { text: '已清除', color: '#e6a23c' },
};

// 加载数据
async function loadData() {
  loading.value = true;
  try {
    const res = await getAISessionListApi({
      page: currentPage.value,
      page_size: pageSize.value,
    });
    sessionList.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    ElMessage.error('加载数据失败');
  } finally {
    loading.value = false;
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1;
  loadData();
}

// 打开详情
function openDetail(session: AISession) {
  router.push(`/ai-assistant/session/${session.id}`);
}

// 格式化时间
function formatTime(time: string) {
  if (!time) return '';
  const date = new Date(time);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`;
  
  return date.toLocaleDateString();
}

// 获取预览文本
function getPreview(session: AISession) {
  if (session.status === 2) return '[上下文已清除]';
  if (session.status === 1) return '[会话已关闭]';
  return `消息数: ${session.message_count}`;
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="session-page">
      <!-- 页面头部 -->
      <div class="page-header">
        <h4>会话管理</h4>
        <div class="search-box">
          <ElInput v-model="searchKeyword" placeholder="搜索群组名称" clearable style="width: 200px" />
          <ElButton type="primary" @click="handleSearch">搜索</ElButton>
        </div>
      </div>

      <!-- 微信风格会话列表 -->
      <div class="wechat-list" v-loading="loading">
        <div 
          v-for="session in sessionList" 
          :key="session.id" 
          class="wechat-item"
          @click="openDetail(session)"
        >
          <div class="wechat-avatar" :class="{ group: true }">
            {{ session.group_id.charAt(0).toUpperCase() }}
          </div>
          <div class="wechat-content">
            <div class="wechat-header">
              <span class="wechat-name">{{ session.group_id }}</span>
              <span class="wechat-time">{{ formatTime(session.last_message_time) }}</span>
            </div>
            <div class="wechat-preview" :style="{ color: statusMap[session.status]?.color || '#b2b2b2' }">
              {{ getPreview(session) }}
            </div>
          </div>
          <div class="session-status">
            <span class="status-tag" :style="{ color: statusMap[session.status]?.color }">
              {{ statusMap[session.status]?.text }}
            </span>
          </div>
        </div>
        
        <!-- 空状态 -->
        <div v-if="sessionList.length === 0 && !loading" class="empty-state">
          暂无会话数据
        </div>
      </div>
    </div>
  </Page>
</template>

<style scoped>
.session-page { background: #fff; min-height: 100%; }
.page-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  padding: 16px 20px; 
  background: #fff; 
  border-bottom: 1px solid #ebeef5; 
}
.search-box { display: flex; gap: 10px; }

/* 微信风格列表 */
.wechat-list { background: #fff; }
.wechat-item { 
  display: flex; 
  padding: 12px 16px; 
  border-bottom: 1px solid #ededed; 
  cursor: pointer; 
  transition: background-color 0.2s; 
}
.wechat-item:hover { background-color: #f5f5f5; }
.wechat-avatar { 
  width: 48px; 
  height: 48px; 
  border-radius: 6px; 
  background: linear-gradient(135deg, #07c160, #10aeff); 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  color: white; 
  font-size: 18px; 
  font-weight: 500;
  margin-right: 12px; 
}
.wechat-content { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.wechat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.wechat-name { font-size: 16px; color: #191919; }
.wechat-time { font-size: 12px; color: #b2b2b2; }
.wechat-preview { font-size: 14px; color: #b2b2b2; }
.session-status { display: flex; align-items: center; }
.status-tag { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.empty-state { text-align: center; padding: 40px; color: #b2b2b2; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/ai-assistant/session/index.vue
git commit -m "feat(ai-assistant): add session list page with wechat style"
```

---

### Task 14: 创建会话详情页面

**Files:**
- Create: `web/apps/web-ele/src/views/ai-assistant/session/detail.vue`

- [ ] **Step 1: 创建会话详情页面**

```vue
<script lang="ts" setup>
import type { AISessionDetail, AIMessage } from '#/api/core/ai-assistant';

import { ref, onMounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElInput,
  ElMessage,
  ElMessageBox,
} from 'element-plus';

import {
  getAISessionDetailApi,
  sendMessageInSessionApi,
  clearSessionContextApi,
  closeSessionApi,
  createNewSessionApi,
} from '#/api/core/ai-assistant';

defineOptions({ name: 'AISessionDetailPage' });

const route = useRoute();
const router = useRouter();

// 数据
const sessionDetail = ref<AISessionDetail | null>(null);
const messages = ref<AIMessage[]>([]);
const loading = ref(false);
const sendLoading = ref(false);

// 输入
const inputContent = ref('');

// 操作菜单
const showActionMenu = ref(false);

// 状态映射
const statusMap: Record<number, string> = {
  0: '活跃',
  1: '已关闭',
  2: '已清除',
};

// 加载详情
async function loadDetail() {
  const sessionId = route.params.id as string;
  if (!sessionId) return;
  
  loading.value = true;
  try {
    const res = await getAISessionDetailApi(sessionId);
    sessionDetail.value = res;
    messages.value = res.messages || [];
    
    // 滚动到底部
    await nextTick();
    scrollToBottom();
  } catch (error) {
    ElMessage.error('加载会话详情失败');
  } finally {
    loading.value = false;
  }
}

// 发送消息
async function handleSend() {
  if (!inputContent.value.trim()) {
    ElMessage.warning('请输入消息内容');
    return;
  }
  
  const sessionId = route.params.id as string;
  sendLoading.value = true;
  try {
    await sendMessageInSessionApi(sessionId, inputContent.value);
    ElMessage.success('消息已发送');
    inputContent.value = '';
    
    // 刷新消息列表
    await loadDetail();
  } catch (error) {
    ElMessage.error('发送失败');
  } finally {
    sendLoading.value = false;
  }
}

// 清除上下文
async function handleClearContext() {
  ElMessageBox.confirm('确定清除上下文？清除后将保留最近10条消息作为新会话的上下文。', '清除上下文', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    const sessionId = route.params.id as string;
    try {
      await clearSessionContextApi(sessionId);
      ElMessage.success('上下文已清除');
      showActionMenu.value = false;
      await loadDetail();
    } catch {
      ElMessage.error('清除失败');
    }
  });
}

// 关闭会话
async function handleCloseSession() {
  ElMessageBox.confirm('确定关闭该会话？', '关闭会话', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    const sessionId = route.params.id as string;
    try {
      await closeSessionApi(sessionId);
      ElMessage.success('会话已关闭');
      showActionMenu.value = false;
      router.back();
    } catch {
      ElMessage.error('关闭失败');
    }
  });
}

// 创建新会话
async function handleNewSession() {
  const sessionId = route.params.id as string;
  try {
    const res = await createNewSessionApi(sessionId);
    ElMessage.success('已创建新会话');
    showActionMenu.value = false;
    router.push(`/ai-assistant/session/${res.session_id}`);
  } catch {
    ElMessage.error('创建失败');
  }
}

// 滚动到底部
function scrollToBottom() {
  const container = document.querySelector('.message-list');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// 格式化时间
function formatTime(time: string) {
  if (!time) return '';
  const date = new Date(time);
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// 格式化日期
function formatDate(time: string) {
  if (!time) return '';
  const date = new Date(time);
  return date.toLocaleDateString('zh-CN');
}

// 返回列表
function goBack() {
  router.back();
}

// 切换菜单
function toggleMenu() {
  showActionMenu.value = !showActionMenu.value;
}

onMounted(() => {
  loadDetail();
});
</script>

<template>
  <Page auto-content-height>
    <div class="chat-page" v-loading="loading">
      <!-- 聊天头部 -->
      <div class="chat-header">
        <span class="chat-back" @click="goBack">‹</span>
        <div class="chat-title-wrap">
          <span class="chat-title">{{ sessionDetail?.group_name || sessionDetail?.session?.group_id }}</span>
          <span class="chat-meta">chat_id: {{ sessionDetail?.session?.chat_id }}</span>
        </div>
        <div class="chat-actions" @click="toggleMenu">
          <span class="chat-more">⋮</span>
          
          <!-- 操作菜单 -->
          <div v-if="showActionMenu" class="action-menu">
            <div class="action-item" @click="handleClearContext">清除上下文</div>
            <div class="action-item danger" @click="handleCloseSession">关闭会话</div>
            <div class="action-item" @click="handleNewSession">创建新会话</div>
          </div>
        </div>
      </div>

      <!-- 会话信息栏 -->
      <div class="session-info-bar">
        <span>
          消息数: <span class="count">{{ sessionDetail?.session?.message_count || 0 }}</span> / 50 |
          状态: {{ statusMap[sessionDetail?.session?.status || 0] }} |
          开始: {{ formatDate(sessionDetail?.session?.start_time || '') }}
        </span>
      </div>

      <!-- 消息列表 -->
      <div class="message-list">
        <!-- 按日期分组显示消息 -->
        <template v-for="(msg, index) in messages" :key="msg.id">
          <!-- 用户消息 -->
          <div v-if="msg.message_type === 0" class="msg-row user">
            <div class="msg-avatar user">{{ (msg.sender_name || msg.sender_id).charAt(0) }}</div>
            <div class="msg-content-wrap">
              <div class="msg-sender">{{ msg.sender_name || msg.sender_id }}</div>
              <div class="msg-bubble user">{{ msg.content }}</div>
              <div class="msg-time">{{ formatTime(msg.send_time) }}</div>
            </div>
          </div>
          
          <!-- AI回复 -->
          <div v-else class="msg-row">
            <div class="msg-avatar ai">AI</div>
            <div class="msg-content-wrap">
              <div class="msg-sender" style="color: #07c160;">AI</div>
              <div class="msg-bubble ai">{{ msg.content }}</div>
              <div class="msg-time">{{ formatTime(msg.receive_time || msg.send_time) }}</div>
            </div>
          </div>
        </template>
        
        <!-- 空状态 -->
        <div v-if="messages.length === 0 && !loading" class="empty-messages">
          暂无消息记录
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-footer">
        <ElInput 
          v-model="inputContent" 
          placeholder="输入消息（可含 @Andy）" 
          class="chat-input"
          @keyup.enter="handleSend"
        />
        <ElButton type="primary" class="send-btn" :loading="sendLoading" @click="handleSend">
          发送
        </ElButton>
      </div>
    </div>
  </Page>
</template>

<style scoped>
.chat-page { 
  display: flex; 
  flex-direction: column; 
  height: 100%; 
  background: #ededed; 
}

/* 头部 */
.chat-header { 
  display: flex; 
  align-items: center; 
  padding: 12px 16px; 
  background: #ededed; 
  border-bottom: 1px solid #d9d9d9; 
}
.chat-back { font-size: 24px; cursor: pointer; color: #191919; margin-right: 16px; }
.chat-title-wrap { flex: 1; }
.chat-title { font-size: 17px; font-weight: 500; }
.chat-meta { font-size: 12px; color: #b2b2b2; margin-left: 8px; }
.chat-actions { position: relative; cursor: pointer; }
.chat-more { font-size: 20px; color: #191919; }
.action-menu { 
  position: absolute; 
  top: 30px; 
  right: 0; 
  background: #4c4c4c; 
  border-radius: 6px; 
  padding: 8px 0; 
  z-index: 100; 
}
.action-item { 
  padding: 10px 16px; 
  color: white; 
  font-size: 14px; 
  cursor: pointer; 
  white-space: nowrap; 
}
.action-item:hover { background: #5c5c5c; }
.action-item.danger { color: #fa5151; }

/* 信息栏 */
.session-info-bar { 
  padding: 12px 16px; 
  background: white; 
  font-size: 13px; 
  color: #909399; 
  border-bottom: 1px solid #ebeef5; 
}
.count { color: #409eff; font-weight: 500; }

/* 消息列表 */
.message-list { 
  flex: 1; 
  overflow-y: auto; 
  padding: 16px; 
  background: #ededed; 
}
.msg-row { 
  display: flex; 
  margin-bottom: 16px; 
  align-items: flex-start; 
}
.msg-row.user { flex-direction: row-reverse; }
.msg-avatar { 
  width: 40px; 
  height: 40px; 
  border-radius: 6px; 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  color: white; 
  font-size: 14px; 
  font-weight: 500;
}
.msg-avatar.user { background: #fa5151; }
.msg-avatar.ai { background: #576b95; }
.msg-content-wrap { max-width: 70%; margin: 0 12px; }
.msg-sender { font-size: 12px; color: #b2b2b2; margin-bottom: 4px; }
.msg-row.user .msg-sender { text-align: right; }
.msg-bubble { 
  padding: 10px 14px; 
  border-radius: 6px; 
  font-size: 15px; 
  line-height: 1.5; 
  word-break: break-word; 
}
.msg-bubble.user { background: #95ec69; }
.msg-bubble.ai { background: white; }
.msg-time { font-size: 12px; color: #b2b2b2; margin-top: 4px; }
.msg-row.user .msg-time { text-align: right; }
.empty-messages { text-align: center; padding: 40px; color: #b2b2b2; }

/* 输入区域 */
.chat-footer { 
  display: flex; 
  padding: 12px 16px; 
  background: #f7f7f7; 
  border-top: 1px solid #d9d9d9; 
  gap: 12px; 
}
.chat-input { flex: 1; }
.send-btn { background: #07c160; border-color: #07c160; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/views/ai-assistant/session/detail.vue
git commit -m "feat(ai-assistant): add session detail page with chat interface"
```

---

### Task 15: 创建路由配置

**Files:**
- Create: `web/apps/web-ele/src/router/routes/modules/ai-assistant.ts`

- [ ] **Step 1: 创建路由配置文件**

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/ai-assistant',
    name: 'AIAssistant',
    component: () => import('#/layouts/default/index.vue'),
    redirect: '/ai-assistant/session',
    children: [
      {
        path: 'session',
        name: 'AIAssistantSession',
        component: () => import('#/views/ai-assistant/session/index.vue'),
        meta: {
          title: '会话管理',
        },
      },
      {
        path: 'session/:id',
        name: 'AIAssistantSessionDetail',
        component: () => import('#/views/ai-assistant/session/detail.vue'),
        meta: {
          title: '会话详情',
          hideInMenu: true,
        },
      },
      {
        path: 'group',
        name: 'AIAssistantGroup',
        component: () => import('#/views/ai-assistant/group/index.vue'),
        meta: {
          title: '群组管理',
        },
      },
    ],
  },
];

export default routes;
```

- [ ] **Step 2: Commit**

```bash
git add web/apps/web-ele/src/router/routes/modules/ai-assistant.ts
git commit -m "feat(ai-assistant): add frontend route configuration"
```

---

### Task 16: 创建菜单初始化脚本

**Files:**
- Create: `backend-fastapi/scripts/init_ai_assistant_menu.py`

- [ ] **Step 1: 创建菜单初始化脚本**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化 AI助手菜单
执行方式: cd backend-fastapi && python scripts/init_ai_assistant_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from core.menu.model import Menu

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


async def init_menus():
    """初始化菜单"""
    async with AsyncSessionLocal() as session:
        for menu_data in MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
                continue

            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                icon=menu_data.get("icon"),
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"创建菜单: {menu_data['title']}")

        await session.commit()
        print("\n菜单初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_menus())
```

- [ ] **Step 2: Commit**

```bash
git add backend-fastapi/scripts/init_ai_assistant_menu.py
git commit -m "feat(ai-assistant): add menu initialization script"
```

---

## Phase 3：测试与完善

### Task 17: 测试外部接口

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi && python main.py
```

验证服务启动成功：控制台显示 "Application startup complete"

- [ ] **Step 2: 测试 /api/public/sendmsg**

```bash
curl -X POST http://localhost:8000/api/public/sendmsg \
  -H "Content-Type: application/json" \
  -d '{"group_id":"test-001","sender_id":"user-1","sender_name":"测试用户","content":"@Andy 你好"}'
```

**验证标准**：
- 响应状态码：200
- 响应 body 包含 `{"status": "ok", "session_id": "...", "chat_id": "...", "message_id": "..."}`
- 数据库 `ai_assistant_group` 表新增记录：group_id = "test-001"
- 数据库 `ai_assistant_session` 表新增记录
- 数据库 `ai_assistant_message` 表新增记录

- [ ] **Step 3: 测试 /api/public/callback/message**

模拟 NanoClaw 回调（使用 Step 2 返回的 chat_id）：
```bash
curl -X POST http://localhost:8000/api/public/callback/message \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"test-001_20260412_143000","message":"你好，有什么可以帮助你的？","timestamp":"2026-04-12T14:30:00Z"}'
```

**验证标准**：
- 响应状态码：200
- 响应 body 包含 `{"status": "ok"}`
- 数据库 `ai_assistant_message` 表新增 message_type = 1 的记录
- 会话的 message_count 增加到 2

- [ ] **Step 4: 测试群组管理接口**

```bash
# 获取群组列表
curl http://localhost:8000/api/core/ai/group?page=1&page_size=20

# 获取会话列表
curl http://localhost:8000/api/core/ai/session?page=1&page_size=20
```

**验证标准**：
- 响应包含 `{"items": [...], "total": N}`
- items 数组包含之前创建的数据

---

### Task 18: 运行菜单初始化

- [ ] **Step 1: 执行菜单初始化脚本**

```bash
cd backend-fastapi && python scripts/init_ai_assistant_menu.py
```

**验证标准**：
- 控制台输出 "创建菜单: AI助手"
- 控制台输出 "创建菜单: 会话管理"
- 控制台输出 "创建菜单: 群组管理"
- 控制台输出 "菜单初始化完成！"

- [ ] **Step 2: 验证数据库菜单记录**

```bash
# 查询菜单表
psql -d your_database -c "SELECT id, name, title, parent_id FROM core_menu WHERE id LIKE 'ai-assistant%';"
```

**验证标准**：
- 数据库包含 3 条菜单记录
- parent_id 正确关联（会话管理和群组管理的 parent_id 为 ai-assistant-root）

- [ ] **Step 3: 验证前端菜单显示**

刷新前端页面（已登录超级管理员账号）。

**验证标准**：
- 左侧菜单栏出现 "AI助手" 一级菜单
- 点击展开后显示 "会话管理" 和 "群组管理" 二级菜单
- 点击菜单可正常跳转到对应页面

---

### Task 19: 最终集成测试

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd web && pnpm dev
```

**验证标准**：
- 服务启动成功，显示本地访问地址（如 http://localhost:5555）
- 无报错信息

- [ ] **Step 2: 测试群组管理页面**

1. 访问群组管理页面：`/ai-assistant/group`
2. 点击「新增群组」按钮
3. 填写表单：群组ID = "demo-group", 群组名称 = "演示群组", 触发词 = "@Andy"
4. 点击确定，验证创建成功提示
5. 在表格中查看新增的群组记录
6. 点击「编辑」按钮，修改群组名称为 "演示群组-已修改"
7. 点击确定，验证更新成功提示
8. 点击「删除」按钮，确认删除
9. 验证删除成功提示，表格中不再显示该记录

**验证标准**：
- 所有操作响应正常，无前端报错
- 表格数据正确刷新
- 弹窗显示和关闭正常

- [ ] **Step 3: 测试会话管理页面**

1. 访问会话列表页面：`/ai-assistant/session`
2. 查看之前测试创建的会话列表
3. 点击某个会话进入详情页
4. 在详情页查看消息气泡列表（用户消息 + AI回复）
5. 在输入框输入消息："@Andy 测试消息"
6. 点击「发送」按钮，验证发送成功提示
7. 点击右上角「⋮」菜单
8. 测试「清除上下文」功能
9. 测试「关闭会话」功能
10. 测试「创建新会话」功能

**验证标准**：
- 消息气泡正确显示（用户右侧绿色，AI左侧白色）
- 发送消息后消息列表正确刷新
- 操作菜单功能正常执行
- 页面样式符合微信风格设计

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "feat(ai-assistant): complete ai assistant module implementation"
```

**验证标准**：
- Git 提交成功
- 工作区无未提交文件（`git status` 显示 clean）

---

## 附录

### 状态码说明

| 会话状态 | 值 | 说明 |
|----------|---|------|
| 活跃 | 0 | 正在使用 |
| 已关闭 | 1 | 用户手动关闭 |
| 已清除 | 2 | 上下文已清除 |

| 消息类型 | 值 | 说明 |
|----------|---|------|
| 用户消息 | 0 | 用户发送的消息 |
| AI回复 | 1 | NanoClaw 返回的回复 |

### 关键配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| CONTEXT_TIME_WINDOW | 120 | 时间窗口（分钟） |
| CONTEXT_MESSAGE_LIMIT | 50 | 消息数量上限 |
| CONTEXT_RECOVERY_COUNT | 10 | 清除后保留消息数 |