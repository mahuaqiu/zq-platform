#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: schema.py
@Desc: AI助手 Schema 定义 - 角色、群组、会话、消息
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============ 角色 Schema ============

class AIRoleCreate(BaseModel):
    """创建角色"""
    name: str = Field(..., max_length=50, description="角色名称")
    role_id: Optional[str] = Field(None, max_length=50, description="角色ID（可选，不填则自动生成）")
    description: Optional[str] = Field(None, description="角色描述")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    avatar: Optional[str] = Field(None, description="角色头像URL")
    is_active: bool = Field(default=True, description="是否启用")


class AIRoleUpdate(BaseModel):
    """更新角色"""
    name: Optional[str] = Field(None, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    avatar: Optional[str] = Field(None, description="角色头像URL")
    is_active: Optional[bool] = Field(None, description="是否启用")


class AIRoleResponse(BaseModel):
    """角色响应"""
    id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    role_id: Optional[str] = Field(None, description="角色ID")
    description: Optional[str] = Field(None, description="角色描述")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    avatar: Optional[str] = Field(None, description="角色头像URL")
    is_active: bool = Field(..., description="是否启用")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


# ============ 群组 Schema ============

class AIGroupCreate(BaseModel):
    """创建群组"""
    group_id: str = Field(..., description="外部系统群组ID")
    group_name: str = Field(..., description="群组名称")
    is_group: bool = Field(default=True, description="是否群聊")
    requires_trigger: bool = Field(default=True, description="是否需要触发词")
    is_active: bool = Field(default=True, description="是否启用")
    role_ids: Optional[List[str]] = Field(None, description="关联角色ID列表")


class AISessionCreate(BaseModel):
    """手动创建会话"""
    group_id: str = Field(..., description="外部系统群组ID")


class AIGroupUpdate(BaseModel):
    """更新群组"""
    group_name: Optional[str] = Field(None, description="群组名称")
    is_group: Optional[bool] = Field(None, description="是否群聊")
    trigger_word: Optional[str] = Field(None, description="触发词")
    requires_trigger: Optional[bool] = Field(None, description="是否需要触发词")
    is_active: Optional[bool] = Field(None, description="是否启用")
    role_ids: Optional[List[str]] = Field(None, description="关联角色ID列表")


class AIGroupResponse(BaseModel):
    """群组响应"""
    id: str = Field(..., description="群组ID")
    group_id: str = Field(..., description="外部系统群组ID")
    group_name: str = Field(..., description="群组名称")
    is_group: bool = Field(..., description="是否群聊")
    requires_trigger: bool = Field(..., description="是否需要触发词")
    is_active: bool = Field(..., description="是否启用")
    roles: List[AIRoleResponse] = Field(default_factory=list, description="关联角色列表")
    trigger_words: List[str] = Field(default_factory=list, description="触发词列表（@角色名称）")
    last_message_time: Optional[datetime] = Field(None, description="最后消息时间")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


# ============ 会话 Schema ============

class AISessionResponse(BaseModel):
    """会话响应"""
    id: str = Field(..., description="会话ID")
    group_id: str = Field(..., description="群组ID")
    group_name: Optional[str] = Field(None, description="群组名称")
    chat_id: str = Field(..., description="外部会话ID")
    session_name: Optional[str] = Field(None, description="会话名称")
    message_count: int = Field(..., description="消息数量")
    status: int = Field(..., description="会话状态")
    start_time: datetime = Field(..., description="开始时间")
    last_message_time: datetime = Field(..., description="最后消息时间")
    is_active: bool = Field(..., description="是否活跃")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class AIMessageResponse(BaseModel):
    """消息响应"""
    id: str = Field(..., description="消息ID")
    session_id: str = Field(..., description="会话ID")
    message_type: int = Field(..., description="消息类型")
    sender_id: str = Field(..., description="发送者ID")
    sender_name: Optional[str] = Field(None, description="发送者名称")
    content: str = Field(..., description="消息内容")
    nanoclaw_message_id: Optional[str] = Field(None, description="NanoClaw消息ID")
    send_time: datetime = Field(..., description="发送时间")
    receive_time: Optional[datetime] = Field(None, description="接收时间")
    is_context_recovery: bool = Field(..., description="是否上下文恢复")

    model_config = ConfigDict(from_attributes=True)


class AISessionDetail(BaseModel):
    """会话详情（含消息列表）"""
    session: AISessionResponse = Field(..., description="会话信息")
    messages: List[AIMessageResponse] = Field(default_factory=list, description="消息列表")
    group_name: Optional[str] = Field(None, description="群组名称")
    trigger_word: Optional[str] = Field(None, description="触发词（AI助手名称）")


# ============ 消息 Schema ============

class AIMessageSend(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容")


# ============ 外部接口 Schema ============

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
    status: str = Field(default="ok", description="响应状态")
    session_id: str = Field(..., description="会话ID")
    chat_id: str = Field(..., description="外部会话ID")
    message_id: str = Field(..., description="消息ID")


class NanoClawCallback(BaseModel):
    """NanoClaw回调消息"""
    chat_id: str = Field(..., description="chat_id")
    message: str = Field(..., description="AI回复内容")
    timestamp: str = Field(..., description="时间戳")


# ============ 分页响应 Schema ============

class AIGroupListResponse(BaseModel):
    """群组列表响应"""
    items: List[AIGroupResponse] = Field(default_factory=list, description="群组列表")
    total: int = Field(..., description="总数")


class AISessionListResponse(BaseModel):
    """会话列表响应"""
    items: List[AISessionResponse] = Field(default_factory=list, description="会话列表")
    total: int = Field(..., description="总数")


class AIRoleListResponse(BaseModel):
    """角色列表响应"""
    items: List[AIRoleResponse] = Field(default_factory=list, description="角色列表")
    total: int = Field(..., description="总数")