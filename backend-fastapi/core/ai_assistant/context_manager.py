#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: context_manager.py
@Desc: AI助手上下文管理逻辑
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.ai_assistant.model import AISession, AIMessage, AIGroup, SessionStatus
from core.ai_assistant.nanoclaw_client import nanoclaw_client

logger = logging.getLogger(__name__)

# 配置常量
TIME_WINDOW_MINUTES = getattr(settings, 'CONTEXT_TIME_WINDOW', 120)
MESSAGE_LIMIT = getattr(settings, 'CONTEXT_MESSAGE_LIMIT', 50)
RECOVERY_COUNT = getattr(settings, 'CONTEXT_RECOVERY_COUNT', 10)


class ContextManager:
    """上下文管理器

    负责管理会话的上下文逻辑：
    - 时间窗口检查：超过指定时间无消息，创建新会话
    - 消息数量限制：达到上限时清除上下文并恢复部分消息
    - 会话生命周期管理
    """

    @staticmethod
    def generate_chat_id(group_id: str) -> str:
        """生成 chat_id: {group_id}_{YYYYMMDD}_{HHMMSS}

        Args:
            group_id: 群组ID

        Returns:
            格式化的 chat_id，如: tech-group-001_20260412_143000
        """
        now = datetime.now()
        return f"{group_id}_{now.strftime('%Y%m%d_%H%M%S')}"

    @staticmethod
    async def check_time_window(session: AISession) -> bool:
        """检查是否超过时间窗口

        检查会话的最后消息时间是否超过配置的时间窗口。

        Args:
            session: 会话对象

        Returns:
            True 表示已超过时间窗口，需要创建新会话
            False 表示仍在时间窗口内
        """
        if not session.last_message_time:
            return True

        time_window = timedelta(minutes=TIME_WINDOW_MINUTES)
        elapsed = datetime.now() - session.last_message_time

        is_exceeded = elapsed > time_window
        if is_exceeded:
            logger.info(
                f"会话 {session.chat_id} 超过时间窗口: "
                f"已过 {elapsed.total_seconds() / 60:.1f} 分钟, "
                f"限制 {TIME_WINDOW_MINUTES} 分钟"
            )

        return is_exceeded

    @staticmethod
    async def check_message_limit(session: AISession) -> bool:
        """检查是否达到消息数量上限

        检查会话的消息计数是否达到配置的上限。

        Args:
            session: 会话对象

        Returns:
            True 表示已达到上限，需要清除上下文
            False 表示未达到上限
        """
        is_reached = session.message_count >= MESSAGE_LIMIT

        if is_reached:
            logger.info(
                f"会话 {session.chat_id} 达到消息上限: "
                f"当前 {session.message_count} 条, "
                f"上限 {MESSAGE_LIMIT} 条"
            )

        return is_reached

    @staticmethod
    async def get_active_session(db: AsyncSession, group_id: str) -> Optional[AISession]:
        """获取群组的活跃会话

        查找群组的活跃会话（status=ACTIVE 且 is_active=True）。

        Args:
            db: 数据库会话
            group_id: 群组ID

        Returns:
            活跃的会话对象，如果不存在则返回 None
        """
        stmt = (
            select(AISession)
            .where(AISession.group_id == group_id)
            .where(AISession.status == SessionStatus.ACTIVE)
            .where(AISession.is_active == True)
            .where(AISession.is_deleted == False)
            .order_by(desc(AISession.last_message_time))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_new_session(
        db: AsyncSession,
        group: AIGroup,
        carryover_messages: Optional[List[AIMessage]] = None,
        auto_commit: bool = True
    ) -> AISession:
        """创建新会话

        为群组创建新会话，并可选地继承历史消息。

        Args:
            db: 数据库会话
            group: 群组对象
            carryover_messages: 需要继承的历史消息列表（上下文恢复）
            auto_commit: 是否自动提交事务

        Returns:
            新创建的会话对象
        """
        # 生成新的 chat_id
        chat_id = ContextManager.generate_chat_id(group.group_id)

        # 创建会话对象
        new_session = AISession(
            group_id=group.group_id,
            chat_id=chat_id,
            session_name=f"{group.group_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            message_count=0,
            status=SessionStatus.ACTIVE,
            start_time=datetime.now(),
            last_message_time=datetime.now(),
            is_active=True,
        )

        db.add(new_session)
        await db.flush()  # 获取生成的 ID

        logger.info(f"创建新会话: chat_id={chat_id}, group_id={group.group_id}")

        # 向 NanoClaw 注册群组
        try:
            result = await nanoclaw_client.register_group(
                chat_id=chat_id,
                name=group.group_name,
                folder=group.group_id,  # 使用 group_id 作为 folder
                trigger=group.trigger_word,
                is_group=group.is_group,
                requires_trigger=group.requires_trigger
            )

            if "error" in result:
                logger.error(f"NanoClaw 注册群组失败: {result}")
            else:
                logger.info(f"NanoClaw 注册群组成功: chat_id={chat_id}")
        except Exception as e:
            logger.error(f"NanoClaw 注册群组异常: {str(e)}")

        # 如果有继承消息，进行上下文恢复
        if carryover_messages:
            await ContextManager.recover_context(new_session, carryover_messages, group.is_group)
            # 设置消息计数为恢复的消息数量
            new_session.message_count = len(carryover_messages)

        if auto_commit:
            await db.commit()
            await db.refresh(new_session)
        else:
            await db.flush()

        return new_session

    @staticmethod
    async def recover_context(session: AISession, messages: List[AIMessage], is_group: bool = True) -> None:
        """恢复上下文

        将历史消息发送给 NanoClaw 以恢复上下文。

        Args:
            session: 当前会话
            messages: 需要恢复的消息列表
            is_group: 是否为群聊，默认为 True
        """
        logger.info(f"会话 {session.chat_id} 开始恢复上下文: {len(messages)} 条消息")

        for msg in messages:
            try:
                # 发送消息到 NanoClaw
                result = await nanoclaw_client.send_message(
                    chat_id=session.chat_id,
                    sender=msg.sender_id,
                    content=msg.content,
                    sender_name=msg.sender_name,
                    is_group=is_group  # 使用参数
                )

                if "error" in result:
                    logger.error(f"恢复上下文消息失败: {result}")
                else:
                    logger.debug(f"恢复上下文消息成功: message_id={msg.id}")
            except Exception as e:
                logger.error(f"恢复上下文消息异常: {str(e)}")

        logger.info(f"会话 {session.chat_id} 上下文恢复完成")

    @staticmethod
    async def get_recent_messages(
        db: AsyncSession,
        session_id: str,
        limit: int = RECOVERY_COUNT
    ) -> List[AIMessage]:
        """获取最近N条消息

        按时间倒序获取会话的最近 N 条消息。

        Args:
            db: 数据库会话
            session_id: 会话ID
            limit: 获取的消息数量，默认使用 RECOVERY_COUNT

        Returns:
            消息列表，按时间正序排列
        """
        stmt = (
            select(AIMessage)
            .where(AIMessage.session_id == session_id)
            .where(AIMessage.is_deleted == False)
            .order_by(desc(AIMessage.send_time))
            .limit(limit)
        )
        result = await db.execute(stmt)
        messages = list(result.scalars().all())

        # 反转列表，按时间正序返回
        messages.reverse()
        return messages

    @staticmethod
    async def handle_message_limit(
        db: AsyncSession,
        session: AISession
    ) -> Tuple[AISession, List[AIMessage]]:
        """处理消息数量上限

        当会话达到消息数量上限时：
        1. 调用 NanoClaw 清除上下文
        2. 获取最近 N 条消息
        3. 标记当前会话为已清除
        4. 创建新会话并继承消息

        Args:
            db: 数据库会话
            session: 达到上限的会话

        Returns:
            Tuple[新会话, 继承的消息列表]
        """
        logger.info(f"处理会话消息上限: session_id={session.id}, chat_id={session.chat_id}")

        # 1. 调用 NanoClaw 清除上下文
        try:
            clear_result = await nanoclaw_client.clear_session(session.chat_id)
            if "error" in clear_result:
                logger.error(f"NanoClaw 清除会话失败: {clear_result}")
            else:
                logger.info(f"NanoClaw 清除会话成功: chat_id={session.chat_id}")
        except Exception as e:
            logger.error(f"NanoClaw 清除会话异常: {str(e)}")

        # 2. 获取最近 N 条消息用于上下文恢复
        recovery_messages = await ContextManager.get_recent_messages(
            db,
            str(session.id),
            RECOVERY_COUNT
        )

        # 3. 标记当前会话为已清除
        session.status = SessionStatus.CLEARED
        session.is_active = False
        await db.commit()

        # 4. 获取群组信息
        stmt = select(AIGroup).where(AIGroup.group_id == session.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()

        if not group:
            logger.error(f"找不到群组: group_id={session.group_id}")
            raise ValueError(f"群组不存在: {session.group_id}")

        # 5. 创建新会话并继承消息
        new_session = await ContextManager.create_new_session(
            db,
            group,
            carryover_messages=recovery_messages
        )

        logger.info(
            f"消息上限处理完成: "
            f"old_session={session.chat_id}, "
            f"new_session={new_session.chat_id}, "
            f"recovered={len(recovery_messages)} messages"
        )

        return new_session, recovery_messages

    @staticmethod
    async def get_or_create_session(
        db: AsyncSession,
        group: AIGroup
    ) -> Tuple[AISession, bool]:
        """获取或创建活跃会话

        检查群组的活跃会话：
        - 如果存在且在时间窗口内，返回该会话
        - 如果超过时间窗口，创建新会话
        - 如果不存在，创建新会话

        Args:
            db: 数据库会话
            group: 群组对象

        Returns:
            Tuple[会话对象, 是否为新创建]
        """
        # 查找活跃会话
        active_session = await ContextManager.get_active_session(db, group.group_id)

        if active_session:
            # 检查时间窗口
            is_exceeded = await ContextManager.check_time_window(active_session)

            if not is_exceeded:
                # 在时间窗口内，返回现有会话
                return active_session, False

            # 超过时间窗口，关闭旧会话
            active_session.status = SessionStatus.CLOSED
            active_session.is_active = False
            await db.commit()
            logger.info(f"关闭过期会话: chat_id={active_session.chat_id}")

        # 创建新会话
        new_session = await ContextManager.create_new_session(db, group)
        return new_session, True

    @staticmethod
    async def should_clear_context(session: AISession) -> bool:
        """检查是否需要清除上下文

        检查会话是否达到消息数量上限。

        Args:
            session: 会话对象

        Returns:
            True 表示需要清除上下文
        """
        return await ContextManager.check_message_limit(session)

    @staticmethod
    async def close_session(db: AsyncSession, session: AISession) -> None:
        """关闭会话

        将会话标记为关闭状态。

        Args:
            db: 数据库会话
            session: 要关闭的会话
        """
        session.status = SessionStatus.CLOSED
        session.is_active = False
        await db.commit()

        logger.info(f"关闭会话: chat_id={session.chat_id}")