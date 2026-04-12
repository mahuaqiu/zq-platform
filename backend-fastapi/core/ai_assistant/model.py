#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: model.py
@Desc: AI助手数据模型 - 群组、会话、消息
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer, Index

from app.base_model import BaseModel


class AIGroup(BaseModel):
    """
    AI助手群组表

    字段说明：
    - group_id: 外部系统群组ID（唯一标识）
    - group_name: 群组名称
    - is_group: 是否群聊
    - trigger_word: 触发词
    - requires_trigger: 是否需要触发词
    - is_active: 是否启用
    - last_message_time: 最后消息时间
    """
    __tablename__ = "ai_assistant_group"

    # 外部系统群组ID
    group_id = Column(String(100), unique=True, nullable=False, index=True, comment="外部系统群组ID")

    # 群组名称
    group_name = Column(String(200), nullable=False, comment="群组名称")

    # 是否群聊
    is_group = Column(Boolean, default=True, nullable=False, comment="是否群聊")

    # 触发词
    trigger_word = Column(String(50), nullable=False, default="@Andy", comment="触发词")

    # 是否需要触发词
    requires_trigger = Column(Boolean, default=True, nullable=False, comment="是否需要触发词")

    # 是否启用
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否启用")

    # 最后消息时间
    last_message_time = Column(DateTime, nullable=True, comment="最后消息时间")


class AISession(BaseModel):
    """
    AI助手会话表

    字段说明：
    - group_id: 关联群组ID
    - chat_id: NanoClaw chat_id（唯一标识）
    - session_name: 会话名称
    - message_count: 消息计数
    - status: 状态: 0-活跃, 1-已关闭, 2-已清除
    - start_time: 开始时间
    - last_message_time: 最后消息时间
    - is_active: 是否活跃
    """
    __tablename__ = "ai_assistant_session"

    # 关联群组ID
    group_id = Column(String(100), nullable=False, index=True, comment="关联群组ID")

    # NanoClaw chat_id
    chat_id = Column(String(150), unique=True, nullable=False, index=True, comment="NanoClaw chat_id")

    # 会话名称
    session_name = Column(String(200), nullable=True, comment="会话名称")

    # 消息计数
    message_count = Column(Integer, default=0, nullable=False, comment="消息计数")

    # 状态：0-活跃, 1-已关闭, 2-已清除
    status = Column(Integer, default=0, nullable=False, index=True, comment="状态: 0-活跃, 1-已关闭, 2-已清除")

    # 开始时间
    start_time = Column(DateTime, nullable=False, default=datetime.now, comment="开始时间")

    # 最后消息时间
    last_message_time = Column(DateTime, nullable=False, default=datetime.now, comment="最后消息时间")

    # 是否活跃
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否活跃")

    # 状态显示名称映射
    STATUS_DISPLAY = {
        0: "活跃",
        1: "已关闭",
        2: "已清除",
    }

    def get_status_display(self) -> str:
        """返回状态的中文显示名称"""
        return self.STATUS_DISPLAY.get(self.status, str(self.status))


class AIMessage(BaseModel):
    """
    AI助手消息表

    字段说明：
    - session_id: 关联会话ID
    - message_type: 消息类型: 0-用户, 1-AI
    - sender_id: 发送者ID
    - sender_name: 发送者名称
    - content: 消息内容
    - nanoclaw_message_id: NanoClaw消息ID
    - reply_to_message_id: 回复消息ID
    - send_time: 发送时间
    - receive_time: 接收时间
    - is_context_recovery: 是否上下文恢复消息
    """
    __tablename__ = "ai_assistant_message"

    # 关联会话ID
    session_id = Column(String(36), nullable=False, index=True, comment="关联会话ID")

    # 消息类型：0-用户, 1-AI
    message_type = Column(Integer, nullable=False, index=True, comment="消息类型: 0-用户, 1-AI")

    # 发送者ID
    sender_id = Column(String(100), nullable=False, comment="发送者ID")

    # 发送者名称
    sender_name = Column(String(100), nullable=True, comment="发送者名称")

    # 消息内容
    content = Column(Text, nullable=False, comment="消息内容")

    # NanoClaw消息ID
    nanoclaw_message_id = Column(String(100), nullable=True, comment="NanoClaw消息ID")

    # 回复消息ID
    reply_to_message_id = Column(String(100), nullable=True, comment="回复消息ID")

    # 发送时间
    send_time = Column(DateTime, nullable=False, default=datetime.now, comment="发送时间")

    # 接收时间
    receive_time = Column(DateTime, nullable=True, comment="接收时间")

    # 是否上下文恢复消息
    is_context_recovery = Column(Boolean, default=False, nullable=False, comment="是否上下文恢复消息")

    # 消息类型显示名称映射
    MESSAGE_TYPE_DISPLAY = {
        0: "用户",
        1: "AI",
    }

    def get_message_type_display(self) -> str:
        """返回消息类型的中文显示名称"""
        return self.MESSAGE_TYPE_DISPLAY.get(self.message_type, str(self.message_type))