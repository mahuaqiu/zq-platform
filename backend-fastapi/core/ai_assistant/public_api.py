#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: public_api.py
@Desc: AI助手公开接口 - 无需鉴权的外部接口
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
        if not group:
            # 自动创建群组
            group = await AIGroupService.auto_create_group(
                db,
                group_id=data.group_id,
                group_name=data.group_name or data.group_id,
                is_group=data.is_group or True,
                auto_commit=False
            )
            logger.info(f"自动创建群组: group_id={data.group_id}")

        # 2. 获取或创建活跃会话（检查时间窗口）
        session, is_new = await ContextManager.get_or_create_session(db, group)

        # 3. 检查消息数量上限
        if await ContextManager.should_clear_context(session):
            # 达到上限，清除上下文并创建新会话
            session, recovery_messages = await ContextManager.handle_message_limit(db, session)
            logger.info(f"达到消息上限，创建新会话: chat_id={session.chat_id}")

        # 4. 发送消息到 NanoClaw
        send_result = await nanoclaw_client.send_message(
            chat_id=session.chat_id,
            sender=data.sender_id,
            content=data.content,
            sender_name=data.sender_name,
            chat_name=group.group_name,
            is_group=group.is_group
        )

        if "error" in send_result:
            logger.error(f"NanoClaw 发送消息失败: {send_result}")
            # 即使 NanoClaw 发送失败，也存储消息记录
            nanoclaw_message_id = None
        else:
            nanoclaw_message_id = send_result.get("message_id")
            logger.info(f"NanoClaw 发送消息成功: chat_id={session.chat_id}")

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
    1. 根据 chat_id 找到会话
    2. 存储 AI 回复消息
    3. 更新会话状态

    Args:
        data: NanoClawCallback 回调数据
        db: 数据库会话

    Returns:
        dict: {"status": "ok"}
    """
    try:
        # 1. 根据 chat_id 找到会话
        session = await AISessionService.get_by_chat_id(db, data.chat_id)
        if not session:
            logger.warning(f"回调消息找不到会话: chat_id={data.chat_id}")
            raise HTTPException(status_code=404, detail="会话不存在")

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