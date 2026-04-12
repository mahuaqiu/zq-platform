#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: model.py
@Desc: AI助手数据模型 - 角色、群组、会话、消息
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer, Index, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.base_model import BaseModel
from app.database import Base


# ==================== 常量定义 ====================

class SessionStatus:
    """会话状态常量"""
    ACTIVE = 0      # 活跃
    CLOSED = 1      # 已关闭
    CLEARED = 2     # 已清除


class MessageType:
    """消息类型常量"""
    USER = 0        # 用户消息
    AI = 1          # AI回复


# 默认触发词
DEFAULT_TRIGGER_WORD = "@Andy"


# ==================== 关联表定义 ====================

# 群组-角色关联表（多对多）
ai_group_role = Table(
    'ai_group_role',
    Base.metadata,
    Column('group_id', String(21), ForeignKey('ai_assistant_group.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', String(21), ForeignKey('ai_assistant_role.id', ondelete='CASCADE'), primary_key=True),
    Column('sort', Integer, default=0, comment="排序"),
)


# ==================== 角色模型 ====================

class AIRole(BaseModel):
    """
    AI角色表

    字段说明：
    - name: 角色名称（用于触发词：@角色名称）
    - role_id: 角色ID（外部系统标识，可选）
    - description: 角色描述
    - system_prompt: 系统提示词
    - avatar: 角色头像URL
    - is_active: 是否启用
    """
    __tablename__ = "ai_assistant_role"

    # 角色名称（用于触发词：@角色名称）
    name = Column(String(50), unique=True, nullable=False, index=True, comment="角色名称")

    # 角色ID（外部系统标识，可选，不填则自动生成）
    role_id = Column(String(50), unique=True, nullable=True, index=True, comment="角色ID")

    # 角色描述
    description = Column(Text, nullable=True, comment="角色描述")

    # 系统提示词（核心配置）
    system_prompt = Column(Text, nullable=True, comment="系统提示词")

    # 角色头像URL
    avatar = Column(String(512), nullable=True, comment="角色头像URL")

    # 是否启用
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否启用")


# ==================== 群组模型 ====================

class AIGroup(BaseModel):
    """
    AI助手群组表

    字段说明：
    - group_id: 外部系统群组ID（唯一标识）
    - group_name: 群组名称
    - is_group: 是否群聊
    - trigger_word: 触发词（可空，如果有关联角色则使用角色的触发词）
    - requires_trigger: 是否需要触发词
    - is_active: 是否启用
    - last_message_time: 最后消息时间
    - roles: 关联角色（多对多）
    """
    __tablename__ = "ai_assistant_group"

    # 外部系统群组ID
    group_id = Column(String(100), unique=True, nullable=False, index=True, comment="外部系统群组ID")

    # 群组名称
    group_name = Column(String(200), nullable=False, comment="群组名称")

    # 是否群聊
    is_group = Column(Boolean, default=True, nullable=False, comment="是否群聊")

    # 触发词（可空，如果有关联角色则使用角色的触发词）
    trigger_word = Column(String(50), nullable=True, default=None, comment="触发词")

    # 是否需要触发词
    requires_trigger = Column(Boolean, default=True, nullable=False, comment="是否需要触发词")

    # 是否启用
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否启用")

    # 最后消息时间
    last_message_time = Column(DateTime, nullable=True, comment="最后消息时间")

    # 多对多关系：关联的角色
    roles = relationship("AIRole", secondary=ai_group_role, backref="groups", lazy="selectin")


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
    status = Column(Integer, default=SessionStatus.ACTIVE, nullable=False, index=True, comment="状态: 0-活跃, 1-已关闭, 2-已清除")

    # 开始时间
    start_time = Column(DateTime, nullable=False, default=datetime.now, comment="开始时间")

    # 最后消息时间
    last_message_time = Column(DateTime, nullable=False, default=datetime.now, comment="最后消息时间")

    # 是否活跃
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否活跃")

    # 状态显示名称映射
    STATUS_DISPLAY = {
        SessionStatus.ACTIVE: "活跃",
        SessionStatus.CLOSED: "已关闭",
        SessionStatus.CLEARED: "已清除",
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
    - profile_id: 角色ID（多角色群组时有效）
    - profile_name: 角色显示名称（多角色群组时有效）
    - trigger_word: 触发词（多角色群组时有效）
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

    # 角色ID（多角色群组时有效，如 xiaoma、小威）
    profile_id = Column(String(100), nullable=True, comment="角色ID（多角色群组时有效）")

    # 角色显示名称（多角色群组时有效，如 小马助手）
    profile_name = Column(String(100), nullable=True, comment="角色显示名称（多角色群组时有效）")

    # 触发词（多角色群组时有效，如 @xiaoma、@小威）
    trigger_word = Column(String(50), nullable=True, comment="触发词（多角色群组时有效）")

    # 消息类型显示名称映射
    MESSAGE_TYPE_DISPLAY = {
        MessageType.USER: "用户",
        MessageType.AI: "AI",
    }

    def get_message_type_display(self) -> str:
        """返回消息类型的中文显示名称"""
        return self.MESSAGE_TYPE_DISPLAY.get(self.message_type, str(self.message_type))