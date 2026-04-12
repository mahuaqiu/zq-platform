#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: service.py
@Desc: AI助手服务层 - 群组、会话、消息
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.ai_assistant.model import (
    AIGroup,
    AISession,
    AIMessage,
    SessionStatus,
    MessageType,
    DEFAULT_TRIGGER_WORD,
)
from core.ai_assistant.schema import (
    AIGroupCreate,
    AIGroupUpdate,
    AISessionResponse,
    AIMessageResponse,
)


class AIGroupService(BaseService[AIGroup, AIGroupCreate, AIGroupUpdate]):
    """
    群组服务

    继承 BaseService，自动获得以下基础功能：
    - create(): 创建记录
    - get_by_id(): 根据 ID 获取单条记录
    - get_list(): 获取分页列表
    - update(): 更新记录
    - delete(): 删除记录（支持软删除）
    - batch_delete(): 批量删除
    - check_unique(): 检查字段唯一性
    - get_by_field(): 根据字段获取单条记录
    - exists(): 检查记录是否存在
    """

    model = AIGroup

    @classmethod
    async def get_by_group_id(cls, db: AsyncSession, group_id: str) -> Optional[AIGroup]:
        """
        根据外部 group_id 获取群组

        :param db: 数据库会话
        :param group_id: 外部系统群组ID
        :return: 群组记录或 None
        """
        result = await db.execute(
            select(AIGroup).where(
                AIGroup.group_id == group_id,
                AIGroup.is_deleted == False  # noqa: E712
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
        """
        带筛选条件的群组列表查询

        :param db: 数据库会话
        :param group_id: 外部系统群组ID（模糊查询）
        :param group_name: 群组名称（模糊查询）
        :param is_active: 是否启用
        :param page: 页码
        :param page_size: 每页数量
        :return: (群组列表, 总数)
        """
        filters = [AIGroup.is_deleted == False]  # noqa: E712

        if group_id:
            escaped_group_id = group_id.replace("%", r"\%").replace("_", r"\_")
            filters.append(AIGroup.group_id.ilike(f"%{escaped_group_id}%"))

        if group_name:
            escaped_group_name = group_name.replace("%", r"\%").replace("_", r"\_")
            filters.append(AIGroup.group_name.ilike(f"%{escaped_group_name}%"))

        if is_active is not None:
            filters.append(AIGroup.is_active == is_active)

        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def auto_create_group(
        cls,
        db: AsyncSession,
        group_id: str,
        group_name: str,
        is_group: bool = True,
        auto_commit: bool = True
    ) -> AIGroup:
        """
        自动创建群组（如果不存在则创建）

        :param db: 数据库会话
        :param group_id: 外部系统群组ID
        :param group_name: 群组名称
        :param is_group: 是否群聊
        :param auto_commit: 是否自动提交
        :return: 群组记录
        """
        # 先尝试获取已存在的群组
        existing_group = await cls.get_by_group_id(db, group_id)
        if existing_group:
            return existing_group

        # 创建新群组
        create_data = AIGroupCreate(
            group_id=group_id,
            group_name=group_name,
            is_group=is_group,
            trigger_word=DEFAULT_TRIGGER_WORD,
            requires_trigger=True,
            is_active=True,
        )
        return await cls.create(db, create_data, auto_commit=auto_commit)

    @classmethod
    async def update_last_message_time(
        cls,
        db: AsyncSession,
        group_id: str,
        auto_commit: bool = True
    ) -> Optional[AIGroup]:
        """
        更新群组最后消息时间

        :param db: 数据库会话
        :param group_id: 外部系统群组ID
        :param auto_commit: 是否自动提交
        :return: 更新后的群组或 None
        """
        group = await cls.get_by_group_id(db, group_id)
        if not group:
            return None

        group.last_message_time = datetime.now()

        if auto_commit:
            await db.commit()
            await db.refresh(group)
        else:
            await db.flush()
            await db.refresh(group)

        return group

    @classmethod
    async def get_active_groups(cls, db: AsyncSession) -> List[AIGroup]:
        """
        获取所有启用的群组

        :param db: 数据库会话
        :return: 启用的群组列表
        """
        result = await db.execute(
            select(AIGroup).where(
                AIGroup.is_deleted == False,  # noqa: E712
                AIGroup.is_active == True  # noqa: E712
            ).order_by(desc(AIGroup.last_message_time))
        )
        return list(result.scalars().all())


class AISessionService(BaseService[AISession, None, None]):
    """
    会话服务

    继承 BaseService，自动获得基础 CRUD 功能。
    由于会话的创建和更新由业务逻辑控制，泛型参数使用 None。
    """

    model = AISession

    @classmethod
    async def get_by_chat_id(cls, db: AsyncSession, chat_id: str) -> Optional[AISession]:
        """
        根据 chat_id 获取会话

        :param db: 数据库会话
        :param chat_id: NanoClaw chat_id
        :return: 会话记录或 None
        """
        result = await db.execute(
            select(AISession).where(
                AISession.chat_id == chat_id,
                AISession.is_deleted == False  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        group_id: Optional[str] = None,
        status: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[AISession], int]:
        """
        带筛选条件的会话列表查询

        :param db: 数据库会话
        :param group_id: 群组ID
        :param status: 会话状态
        :param is_active: 是否活跃
        :param page: 页码
        :param page_size: 每页数量
        :return: (会话列表, 总数)
        """
        filters = [AISession.is_deleted == False]  # noqa: E712

        if group_id:
            filters.append(AISession.group_id == group_id)

        if status is not None:
            filters.append(AISession.status == status)

        if is_active is not None:
            filters.append(AISession.is_active == is_active)

        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def get_session_with_messages(
        cls,
        db: AsyncSession,
        session_id: str
    ) -> Optional[dict]:
        """
        获取会话详情含消息列表

        :param db: 数据库会话
        :param session_id: 会话ID
        :return: 包含会话和消息的字典，或 None
        """
        # 获取会话
        session = await cls.get_by_id(db, session_id)
        if not session:
            return None

        # 获取消息列表
        messages_result = await db.execute(
            select(AIMessage).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False  # noqa: E712
            ).order_by(AIMessage.send_time)
        )
        messages = list(messages_result.scalars().all())

        # 获取群组名称
        group = await AIGroupService.get_by_group_id(db, session.group_id)

        return {
            "session": session,
            "messages": messages,
            "group_name": group.group_name if group else None,
            "trigger_word": group.trigger_word if group else None,
        }

    @classmethod
    async def close_session(
        cls,
        db: AsyncSession,
        session_id: str,
        auto_commit: bool = True
    ) -> Optional[AISession]:
        """
        关闭会话

        :param db: 数据库会话
        :param session_id: 会话ID
        :param auto_commit: 是否自动提交
        :return: 更新后的会话或 None
        """
        session = await cls.get_by_id(db, session_id)
        if not session:
            return None

        session.status = SessionStatus.CLOSED
        session.is_active = False

        if auto_commit:
            await db.commit()
            await db.refresh(session)
        else:
            await db.flush()
            await db.refresh(session)

        return session

    @classmethod
    async def create_session(
        cls,
        db: AsyncSession,
        group_id: str,
        chat_id: str,
        session_name: Optional[str] = None,
        auto_commit: bool = True
    ) -> AISession:
        """
        创建新会话

        :param db: 数据库会话
        :param group_id: 群组ID
        :param chat_id: NanoClaw chat_id
        :param session_name: 会话名称
        :param auto_commit: 是否自动提交
        :return: 会话记录
        """
        session = AISession(
            group_id=group_id,
            chat_id=chat_id,
            session_name=session_name,
            message_count=0,
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_message_time=datetime.now(),
            is_active=True,
        )
        db.add(session)

        if auto_commit:
            await db.commit()
            await db.refresh(session)
        else:
            await db.flush()
            await db.refresh(session)

        return session

    @classmethod
    async def update_session_activity(
        cls,
        db: AsyncSession,
        session_id: str,
        auto_commit: bool = True
    ) -> Optional[AISession]:
        """
        更新会话活跃时间

        :param db: 数据库会话
        :param session_id: 会话ID
        :param auto_commit: 是否自动提交
        :return: 更新后的会话或 None
        """
        session = await cls.get_by_id(db, session_id)
        if not session:
            return None

        session.last_message_time = datetime.now()

        if auto_commit:
            await db.commit()
            await db.refresh(session)
        else:
            await db.flush()
            await db.refresh(session)

        return session

    @classmethod
    async def get_active_sessions_by_group(
        cls,
        db: AsyncSession,
        group_id: str
    ) -> List[AISession]:
        """
        获取群组下所有活跃会话

        :param db: 数据库会话
        :param group_id: 群组ID
        :return: 活跃会话列表
        """
        result = await db.execute(
            select(AISession).where(
                AISession.group_id == group_id,
                AISession.is_deleted == False,  # noqa: E712
                AISession.is_active == True,  # noqa: E712
                AISession.status == SessionStatus.ACTIVE
            ).order_by(desc(AISession.last_message_time))
        )
        return list(result.scalars().all())

    @classmethod
    async def get_session_stats(cls, db: AsyncSession, group_id: Optional[str] = None) -> dict:
        """
        获取会话统计信息

        :param db: 数据库会话
        :param group_id: 可选，按群组筛选
        :return: 统计信息字典
        """
        base_filter = [AISession.is_deleted == False]  # noqa: E712
        if group_id:
            base_filter.append(AISession.group_id == group_id)

        # 总数
        total_query = select(func.count(AISession.id)).where(*base_filter)
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0

        # 按状态统计
        status_stats = {}
        for status, status_name in [
            (SessionStatus.ACTIVE, "active"),
            (SessionStatus.CLOSED, "closed"),
            (SessionStatus.CLEARED, "cleared"),
        ]:
            status_query = select(func.count(AISession.id)).where(
                *base_filter,
                AISession.status == status
            )
            status_result = await db.execute(status_query)
            status_stats[status_name] = status_result.scalar() or 0

        return {
            "total_count": total_count,
            "status_stats": status_stats,
        }


class AIMessageService(BaseService[AIMessage, None, None]):
    """
    消息服务

    继承 BaseService，自动获得基础 CRUD 功能。
    由于消息的创建由业务逻辑控制，泛型参数使用 None。
    """

    model = AIMessage

    @classmethod
    async def create_user_message(
        cls,
        db: AsyncSession,
        session_id: str,
        sender_id: str,
        content: str,
        sender_name: Optional[str] = None,
        nanoclaw_message_id: Optional[str] = None,
        auto_commit: bool = True
    ) -> AIMessage:
        """
        创建用户消息

        :param db: 数据库会话
        :param session_id: 会话ID
        :param sender_id: 发送者ID
        :param content: 消息内容
        :param sender_name: 发送者名称
        :param nanoclaw_message_id: NanoClaw消息ID
        :param auto_commit: 是否自动提交
        :return: 消息记录
        """
        message = AIMessage(
            session_id=session_id,
            message_type=MessageType.USER,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            nanoclaw_message_id=nanoclaw_message_id,
            send_time=datetime.now(),
            is_context_recovery=False,
        )
        db.add(message)

        if auto_commit:
            await db.commit()
            await db.refresh(message)
        else:
            await db.flush()
            await db.refresh(message)

        # 更新会话消息计数
        await cls.update_session_message_count(db, session_id, auto_commit=auto_commit)

        return message

    @classmethod
    async def create_ai_message(
        cls,
        db: AsyncSession,
        session_id: str,
        content: str,
        nanoclaw_message_id: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
        receive_time: Optional[datetime] = None,
        auto_commit: bool = True
    ) -> AIMessage:
        """
        创建AI回复消息

        :param db: 数据库会话
        :param session_id: 会话ID
        :param content: 消息内容
        :param nanoclaw_message_id: NanoClaw消息ID
        :param reply_to_message_id: 回复消息ID
        :param receive_time: 接收时间
        :param auto_commit: 是否自动提交
        :return: 消息记录
        """
        message = AIMessage(
            session_id=session_id,
            message_type=MessageType.AI,
            sender_id="ai",
            sender_name="AI助手",
            content=content,
            nanoclaw_message_id=nanoclaw_message_id,
            reply_to_message_id=reply_to_message_id,
            send_time=datetime.now(),
            receive_time=receive_time or datetime.now(),
            is_context_recovery=False,
        )
        db.add(message)

        if auto_commit:
            await db.commit()
            await db.refresh(message)
        else:
            await db.flush()
            await db.refresh(message)

        # 更新会话消息计数
        await cls.update_session_message_count(db, session_id, auto_commit=auto_commit)

        return message

    @classmethod
    async def update_session_message_count(
        cls,
        db: AsyncSession,
        session_id: str,
        auto_commit: bool = True
    ) -> None:
        """
        更新会话消息计数

        :param db: 数据库会话
        :param session_id: 会话ID
        :param auto_commit: 是否自动提交
        """
        # 统计消息数量
        count_result = await db.execute(
            select(func.count(AIMessage.id)).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False  # noqa: E712
            )
        )
        message_count = count_result.scalar() or 0

        # 更新会话
        session = await AISessionService.get_by_id(db, session_id)
        if session:
            session.message_count = message_count
            session.last_message_time = datetime.now()

            if auto_commit:
                await db.commit()
            else:
                await db.flush()

    @classmethod
    async def get_messages_by_session(
        cls,
        db: AsyncSession,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[AIMessage]:
        """
        获取会话的消息列表

        :param db: 数据库会话
        :param session_id: 会话ID
        :param limit: 限制数量
        :param offset: 偏移量
        :return: 消息列表
        """
        result = await db.execute(
            select(AIMessage).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False  # noqa: E712
            ).order_by(AIMessage.send_time).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    @classmethod
    async def get_recent_messages(
        cls,
        db: AsyncSession,
        session_id: str,
        limit: int = 20
    ) -> List[AIMessage]:
        """
        获取会话最近的消息（用于上下文恢复）

        :param db: 数据库会话
        :param session_id: 会话ID
        :param limit: 限制数量
        :return: 消息列表（按时间正序）
        """
        result = await db.execute(
            select(AIMessage).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False  # noqa: E712
            ).order_by(desc(AIMessage.send_time)).limit(limit)
        )
        messages = list(result.scalars().all())
        # 反转顺序，使消息按时间正序
        return messages[::-1]

    @classmethod
    async def create_context_recovery_messages(
        cls,
        db: AsyncSession,
        session_id: str,
        messages: List[dict],
        auto_commit: bool = True
    ) -> List[AIMessage]:
        """
        创建上下文恢复消息

        :param db: 数据库会话
        :param session_id: 会话ID
        :param messages: 消息列表，每个消息包含 sender_id, sender_name, content, message_type
        :param auto_commit: 是否自动提交
        :return: 创建的消息列表
        """
        created_messages = []
        for msg in messages:
            message = AIMessage(
                session_id=session_id,
                message_type=msg.get("message_type", MessageType.USER),
                sender_id=msg.get("sender_id", ""),
                sender_name=msg.get("sender_name"),
                content=msg.get("content", ""),
                send_time=msg.get("send_time", datetime.now()),
                is_context_recovery=True,
            )
            db.add(message)
            created_messages.append(message)

        if auto_commit:
            await db.commit()
            for msg in created_messages:
                await db.refresh(msg)
        else:
            await db.flush()
            for msg in created_messages:
                await db.refresh(msg)

        # 更新会话消息计数
        await cls.update_session_message_count(db, session_id, auto_commit=auto_commit)

        return created_messages

    @classmethod
    async def get_message_stats(cls, db: AsyncSession, session_id: Optional[str] = None) -> dict:
        """
        获取消息统计信息

        :param db: 数据库会话
        :param session_id: 可选，按会话筛选
        :return: 统计信息字典
        """
        base_filter = [AIMessage.is_deleted == False]  # noqa: E712
        if session_id:
            base_filter.append(AIMessage.session_id == session_id)

        # 总数
        total_query = select(func.count(AIMessage.id)).where(*base_filter)
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0

        # 按类型统计
        type_stats = {}
        for msg_type, type_name in [
            (MessageType.USER, "user"),
            (MessageType.AI, "ai"),
        ]:
            type_query = select(func.count(AIMessage.id)).where(
                *base_filter,
                AIMessage.message_type == msg_type
            )
            type_result = await db.execute(type_query)
            type_stats[type_name] = type_result.scalar() or 0

        return {
            "total_count": total_count,
            "type_stats": type_stats,
        }

    @classmethod
    async def delete_messages_by_session(
        cls,
        db: AsyncSession,
        session_id: str,
        auto_commit: bool = True
    ) -> int:
        """
        删除指定会话的所有消息（软删除）

        :param db: 数据库会话
        :param session_id: 会话ID
        :param auto_commit: 是否自动提交事务
        :return: 删除的消息数量
        """
        # 查询该会话的所有消息
        result = await db.execute(
            select(AIMessage).where(
                AIMessage.session_id == session_id,
                AIMessage.is_deleted == False
            )
        )
        messages = list(result.scalars().all())

        # 软删除所有消息
        count = 0
        for msg in messages:
            msg.is_deleted = True
            count += 1

        if auto_commit:
            await db.commit()
        else:
            await db.flush()

        return count