#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: public_api.py
@Desc: AI助手公开接口 - 无需鉴权的外部接口
"""
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from core.ai_assistant.model import AIGroup, AISession, AIMessage, MessageType
from core.ai_assistant.schema import (
    ExternalSendMessage,
    ExternalSendMessageResponse,
    NanoClawCallback,
)
from core.ai_assistant.service import AIGroupService, AISessionService, AIMessageService
from core.ai_assistant.context_manager import ContextManager
from core.ai_assistant.nanoclaw_client import nanoclaw_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["公开接口"])


# ==================== 保底轮询任务 ====================

async def _poll_fallback_task(chat_id: str, session_id: str):
    """
    保底轮询任务：等待2分钟后开始轮询

    如果回调未收到响应，启动轮询机制获取 AI 回复。

    Args:
        chat_id: NanoClaw chat_id
        session_id: 本系统会话 ID
    """
    # 等待 2 分钟（等待回调响应）
    await asyncio.sleep(120)

    logger.info(f"保底轮询开始: chat_id={chat_id}, session_id={session_id}")

    # 开始轮询（5次，间隔60秒）
    reply = await nanoclaw_client.poll_for_reply(
        chat_id=chat_id,
        session_id=session_id,
        max_attempts=5,
        interval_seconds=60,
    )

    if reply:
        logger.info(f"保底轮询成功获取回复: chat_id={chat_id}")
    else:
        logger.warning(f"保底轮询未获取到回复: chat_id={chat_id}")


@router.post("/sendmsg", response_model=ExternalSendMessageResponse, summary="外部发送消息")
async def external_send_message(
    data: ExternalSendMessage,
    db: AsyncSession = Depends(get_db)
) -> ExternalSendMessageResponse:
    """
    外部系统发送消息接口（无需鉴权）

    处理流程：
    1. 查找或创建群组
    2. 获取或创建活跃会话（检查时间窗口）
    3. 检查消息数量上限
    4. 发送消息到 NanoClaw
    5. 存储消息记录

    Args:
        data: ExternalSendMessage 请求数据
        db: 数据库会话

    Returns:
        ExternalSendMessageResponse: 包含 session_id, chat_id, message_id
    """
    try:
        # 1. 查找或创建群组
        group = await AIGroupService.get_by_group_id(db, data.group_id)
        is_new_group = False
        if not group:
            # 自动创建群组
            group = await AIGroupService.auto_create_group(
                db,
                group_id=data.group_id,
                group_name=data.group_name or data.group_id,
                is_group=data.is_group or True,
                auto_commit=False
            )
            is_new_group = True
            logger.info(f"自动创建群组: group_id={data.group_id}")

        # 如果是新创建的群组，需要注册到 NanoClaw
        if is_new_group:
            # 使用默认配置注册（无角色时使用默认触发词 @Andy）
            register_result = await nanoclaw_client.register_group(
                chat_id=group.group_id,
                folder=f"group_{group.group_id}",
                name=group.group_name,
                trigger="@Andy",  # 默认触发词
                is_group=group.is_group,
                requires_trigger=group.requires_trigger
            )
            if "error" in register_result:
                logger.warning(f"NanoClaw 自动注册群组失败: {register_result}")
            else:
                logger.info(f"NanoClaw 自动注册群组成功: group_id={group.group_id}")

        # 2. 获取或创建活跃会话（检查时间窗口）
        session, is_new = await ContextManager.get_or_create_session(db, group)

        # 3. 检查消息数量上限
        if await ContextManager.should_clear_context(session):
            # 达到上限，清除上下文并创建新会话
            session, recovery_messages = await ContextManager.handle_message_limit(db, session)
            logger.info(f"达到消息上限，创建新会话: chat_id={session.chat_id}")

        # 4. 发送消息到 NanoClaw（支持回调模式）
        # 使用 group.group_id 作为 chat_id，保持上下文共享
        callback_url = settings.NANOCLAW_CALLBACK_URL
        send_result = await nanoclaw_client.send_message(
            chat_id=group.group_id,  # 使用群组 ID，而不是 session.chat_id
            sender=data.sender_id,
            content=data.content,
            sender_name=data.sender_name,
            chat_name=group.group_name,
            is_group=group.is_group,
            callback_url=callback_url,  # 传递回调 URL
        )

        if "error" in send_result:
            logger.error(f"NanoClaw 发送消息失败: {send_result}")
            # 即使 NanoClaw 发送失败，也存储消息记录
            nanoclaw_message_id = None
        else:
            nanoclaw_message_id = send_result.get("message_id")
            logger.info(f"NanoClaw 发送消息成功: chat_id={group.group_id}, session_id={session.id}, callback_mode={bool(callback_url)}")

            # 如果使用回调模式，启动保底轮询任务
            if callback_url:
                asyncio.create_task(
                    _poll_fallback_task(
                        chat_id=group.group_id,  # 使用群组 ID
                        session_id=str(session.id),
                    )
                )
                logger.info(f"已启动保底轮询任务: chat_id={group.group_id}, session_id={session.id}")

        # 5. 存储消息记录
        message = await AIMessageService.create_user_message(
            db,
            session_id=str(session.id),
            sender_id=data.sender_id,
            content=data.content,
            sender_name=data.sender_name,
            nanoclaw_message_id=nanoclaw_message_id,
            auto_commit=False
        )

        # 更新群组最后消息时间
        await AIGroupService.update_last_message_time(db, data.group_id, auto_commit=False)

        # 更新会话活跃时间
        await AISessionService.update_session_activity(db, str(session.id), auto_commit=False)

        # 提交所有数据库更改
        await db.commit()

        logger.info(
            f"外部消息处理完成: "
            f"group_id={data.group_id}, "
            f"session_id={session.id}, "
            f"message_id={message.id}"
        )

        return ExternalSendMessageResponse(
            status="ok",
            session_id=str(session.id),
            chat_id=session.chat_id,
            message_id=str(message.id)
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"外部发送消息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理消息失败: {str(e)}")


@router.post("/callback/message", summary="NanoClaw回调接口")
async def nanoclaw_callback(
    data: NanoClawCallback,
    db: AsyncSession = Depends(get_db)
):
    """
    NanoClaw 回调接口（接收 AI 回复）

    处理流程：
    1. 根据 chat_id（group_id）找到活跃会话
    2. 存储 AI 回复消息
    3. 更新会话状态

    Args:
        data: NanoClawCallback 回调数据
        db: 数据库会话

    Returns:
        dict: {"status": "ok"}
    """
    try:
        # 1. 根据 chat_id（group_id）找到活跃会话
        # 注意：chat_id 在发送消息时是 group.group_id，所以回调时也是 group_id
        sessions = await AISessionService.get_active_sessions_by_group(db, data.chat_id)
        if not sessions:
            logger.warning(f"回调消息找不到活跃会话: chat_id={data.chat_id} (group_id)")
            raise HTTPException(status_code=404, detail="会话不存在")

        # 取最新的活跃会话
        session = sessions[0]
        logger.info(f"找到活跃会话: session_id={session.id}, group_id={data.chat_id}")

        # 2. 存储 AI 回复消息
        receive_time = datetime.now()
        if data.timestamp:
            try:
                # 尝试解析时间戳，去掉 timezone 以兼容数据库
                parsed_time = datetime.fromisoformat(data.timestamp.replace("Z", "+00:00"))
                receive_time = parsed_time.replace(tzinfo=None)
            except ValueError:
                logger.warning(f"无法解析时间戳: {data.timestamp}")

        message = await AIMessageService.create_ai_message(
            db,
            session_id=str(session.id),
            content=data.message,
            nanoclaw_message_id=None,  # 回调消息没有 NanoClaw 消息 ID
            reply_to_message_id=None,
            receive_time=receive_time,
            auto_commit=False
        )

        # 3. 更新会话状态
        await AISessionService.update_session_activity(db, str(session.id), auto_commit=False)

        # 更新群组最后消息时间
        await AIGroupService.update_last_message_time(db, session.group_id, auto_commit=False)

        # 提交数据库更改
        await db.commit()

        logger.info(
            f"NanoClaw 回调处理完成: "
            f"chat_id={data.chat_id}, "
            f"session_id={session.id}, "
            f"message_id={message.id}"
        )

        return {"status": "ok"}

    except HTTPException:
        # 已经是 HTTPException，直接抛出
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"NanoClaw 回调处理失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理回调失败: {str(e)}")