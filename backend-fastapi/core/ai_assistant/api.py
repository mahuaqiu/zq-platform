#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Time: 2026-04-12
@File: api.py
@Desc: AI助手管理接口 API - 群组管理、会话管理
"""
import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_schema import PaginatedResponse
from app.config import settings
from app.database import get_db
from core.ai_assistant.model import SessionStatus, AIGroup, AIRole
from core.ai_assistant.schema import (
    AIGroupCreate,
    AIGroupUpdate,
    AIGroupResponse,
    AISessionCreate,
    AISessionResponse,
    AIMessageResponse,
    AISessionDetail,
    AIMessageSend,
    AIGroupListResponse,
    AISessionListResponse,
    AIRoleCreate,
    AIRoleUpdate,
    AIRoleResponse,
    AISkillCreate,
    AISkillUpdate,
    AISkillResponse,
    AISkillListResponse,
    SkillAssignment,
    SkillAssignmentRemove,
)
from core.ai_assistant.service import (
    AIGroupService,
    AISessionService,
    AIMessageService,
    AIRoleService,
    AISkillService,
)
from core.ai_assistant.context_manager import ContextManager
from core.ai_assistant.nanoclaw_client import nanoclaw_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI助手管理"])


# ==================== 保底轮询任务管理 ====================

# 存储正在等待的保底轮询任务，用于在回调收到时取消
_pending_poll_tasks: dict[str, asyncio.Task] = {}


async def _poll_fallback_task(chat_id: str, session_id: str):
    """
    保底轮询任务：等待2分钟后开始轮询

    如果回调未收到响应，启动轮询机制获取 AI 回复。

    Args:
        chat_id: NanoClaw chat_id
        session_id: 本系统会话 ID
    """
    # 使用 chat_id 作为任务标识（一个群组只需要一个轮询任务）
    task_key = chat_id

    # 等待 2 分钟（等待回调响应）
    await asyncio.sleep(120)

    # 检查任务是否已被取消（回调已收到）
    if task_key not in _pending_poll_tasks:
        logger.info(f"保底轮询任务已取消: chat_id={chat_id}，回调已收到")
        return

    logger.info(f"[NanoClaw] 开始保底轮询: chat_id={chat_id}, session_id={session_id}, attempts=5")

    # 开始轮询（5次，间隔60秒）
    reply = await nanoclaw_client.poll_for_reply(
        chat_id=chat_id,
        session_id=session_id,
        max_attempts=5,
        interval_seconds=60,
    )

    if reply:
        logger.info(f"保底轮询成功获取回复: chat_id={chat_id}")
        # 这里可以触发通知或更新状态
        # 回复会通过 /api/public/callback/message 正常处理
    else:
        logger.warning(f"保底轮询未获取到回复: chat_id={chat_id}")

    # 清理任务记录
    if task_key in _pending_poll_tasks:
        del _pending_poll_tasks[task_key]


def _start_poll_fallback_task(chat_id: str, session_id: str):
    """
    启动保底轮询任务（如果不存在）

    Args:
        chat_id: NanoClaw chat_id
        session_id: 本系统会话 ID
    """
    task_key = chat_id

    # 如果该群组已有等待的轮询任务，不再创建新的
    if task_key in _pending_poll_tasks:
        logger.info(f"群组已有保底轮询任务等待中: chat_id={chat_id}")
        return

    # 创建新任务
    task = asyncio.create_task(_poll_fallback_task(chat_id, session_id))
    _pending_poll_tasks[task_key] = task
    logger.info(f"已启动保底轮询任务: chat_id={chat_id}, session_id={session_id}")


def _cancel_poll_fallback_task(chat_id: str):
    """
    取消保底轮询任务（回调收到时调用）

    Args:
        chat_id: NanoClaw chat_id
    """
    task_key = chat_id

    if task_key in _pending_poll_tasks:
        task = _pending_poll_tasks[task_key]
        task.cancel()
        del _pending_poll_tasks[task_key]
        logger.info(f"已取消保底轮询任务: chat_id={chat_id}，回调已收到")


# ==================== 角色管理接口 ====================

@router.get("/role", response_model=PaginatedResponse[AIRoleResponse], summary="角色列表")
async def list_roles(
    name: Optional[str] = None,
    role_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[AIRoleResponse]:
    """
    角色列表（分页）

    支持按 name、role_id、is_active 筛选。

    Args:
        name: 角色名称（模糊查询）
        role_id: 角色ID（模糊查询）
        is_active: 是否启用
        page: 页码
        page_size: 每页数量
    """
    roles, total = await AIRoleService.get_list_with_filters(
        db,
        name=name,
        role_id=role_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[AIRoleResponse.model_validate(r) for r in roles],
        total=total,
    )


@router.get("/role/all", response_model=List[AIRoleResponse], summary="所有启用角色")
async def get_all_active_roles(db: AsyncSession = Depends(get_db)):
    """
    获取所有启用的角色（用于角色选择器）
    """
    roles = await AIRoleService.get_active_roles(db)
    return [AIRoleResponse.model_validate(r) for r in roles]


@router.get("/role/{role_id}", response_model=AIRoleResponse, summary="角色详情")
async def get_role_detail(
    role_id: str,
    db: AsyncSession = Depends(get_db)
) -> AIRoleResponse:
    """
    角色详情

    Args:
        role_id: 角色ID（UUID）
    """
    role = await AIRoleService.get_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    return AIRoleResponse.model_validate(role)


@router.post("/role", response_model=AIRoleResponse, summary="创建角色")
async def create_role(
    data: AIRoleCreate,
    db: AsyncSession = Depends(get_db)
) -> AIRoleResponse:
    """
    创建角色

    Args:
        data: 角色创建数据
    """
    # 检查 name 是否已存在
    existing_name = await AIRoleService.get_by_name(db, data.name)
    if existing_name:
        raise HTTPException(status_code=400, detail=f"角色名称已存在: {data.name}")

    # 如果指定了 role_id，检查是否已存在
    if data.role_id:
        existing_role_id = await AIRoleService.get_by_role_id(db, data.role_id)
        if existing_role_id:
            raise HTTPException(status_code=400, detail=f"角色ID已存在: {data.role_id}")

    role = await AIRoleService.create(db, data)
    logger.info(f"创建角色成功: name={data.name}, role_id={data.role_id}")

    return AIRoleResponse.model_validate(role)


@router.put("/role/{role_id}", response_model=AIRoleResponse, summary="更新角色")
async def update_role(
    role_id: str,
    data: AIRoleUpdate,
    db: AsyncSession = Depends(get_db)
) -> AIRoleResponse:
    """
    更新角色

    Args:
        role_id: 角色ID（UUID）
        data: 角色更新数据
    """
    role = await AIRoleService.get_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 如果更新名称，检查是否重复
    if data.name and data.name != role.name:
        existing = await AIRoleService.get_by_name(db, data.name)
        if existing:
            raise HTTPException(status_code=400, detail=f"角色名称已存在: {data.name}")

    role = await AIRoleService.update(db, role_id, data)
    logger.info(f"更新角色成功: role_id={role_id}")

    return AIRoleResponse.model_validate(role)


@router.delete("/role/{role_id}", summary="删除角色")
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除角色（软删除）

    Args:
        role_id: 角色ID（UUID）
    """
    role = await AIRoleService.get_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    await AIRoleService.delete(db, role_id)
    logger.info(f"删除角色成功: role_id={role_id}")

    return {"status": "success", "message": "删除成功"}


@router.post("/role/by-ids", response_model=List[AIRoleResponse], summary="按ID批量获取角色")
async def get_roles_by_ids(
    ids: List[str] = Body(..., description="角色ID列表"),
    db: AsyncSession = Depends(get_db)
):
    """
    根据ID列表批量获取角色信息
    """
    roles = await AIRoleService.get_roles_by_ids(db, ids)
    return [AIRoleResponse.model_validate(r) for r in roles]


# ==================== 群组管理接口 ====================

def _build_group_response(group: AIGroup) -> AIGroupResponse:
    """
    构建群组响应，包含 roles 和 trigger_words
    """
    roles = [AIRoleResponse.model_validate(r) for r in group.roles if r.is_active]
    trigger_words = AIGroupService.get_trigger_words(group)

    return AIGroupResponse(
        id=str(group.id),
        group_id=group.group_id,
        group_name=group.group_name,
        is_group=group.is_group,
        trigger_word=group.trigger_word,
        requires_trigger=group.requires_trigger,
        is_active=group.is_active,
        roles=roles,
        trigger_words=trigger_words,
        last_message_time=group.last_message_time,
        sys_create_datetime=group.sys_create_datetime,
        sys_update_datetime=group.sys_update_datetime,
    )


@router.get("/group", response_model=PaginatedResponse[AIGroupResponse], summary="群组列表")
async def list_groups(
    group_id: Optional[str] = None,
    group_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=1000, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[AIGroupResponse]:
    """
    群组列表（分页）

    支持按 group_id、group_name、is_active 筛选。

    Args:
        group_id: 外部系统群组ID（模糊查询）
        group_name: 群组名称（模糊查询）
        is_active: 是否启用
        page: 页码
        page_size: 每页数量
    """
    groups, total = await AIGroupService.get_list_with_filters(
        db,
        group_id=group_id,
        group_name=group_name,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[_build_group_response(g) for g in groups],
        total=total,
    )


@router.get("/group/{group_id}", response_model=AIGroupResponse, summary="群组详情")
async def get_group_detail(
    group_id: str,
    db: AsyncSession = Depends(get_db)
) -> AIGroupResponse:
    """
    群组详情

    根据 group_id（数据库主键 UUID）获取群组详情。

    Args:
        group_id: 群组ID（UUID）
    """
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    return _build_group_response(group)


@router.post("/group", response_model=AIGroupResponse, summary="创建群组")
async def create_group(
    data: AIGroupCreate,
    db: AsyncSession = Depends(get_db)
) -> AIGroupResponse:
    """
    创建群组

    创建新的 AI 助手群组配置，并注册到 NanoClaw。

    Args:
        data: 群组创建数据（包含 role_ids）
    """
    # 检查 group_id 是否已存在
    existing = await AIGroupService.get_by_group_id(db, data.group_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"群组ID已存在: {data.group_id}")

    # 创建群组（不包含 role_ids）
    group_data = data.model_dump(exclude={'role_ids'})
    group = AIGroup(**group_data)
    db.add(group)
    await db.flush()
    await db.refresh(group)

    # 如果有 role_ids，设置角色关联
    if data.role_ids:
        roles = await AIRoleService.get_roles_by_ids(db, data.role_ids)
        group.roles = roles
        await db.flush()
        await db.refresh(group)

    await db.commit()
    await db.refresh(group)

    # 注册到 NanoClaw（使用多角色格式）
    profiles = []
    for role in group.roles:
        profiles.append({
            "id": role.role_id or str(role.id),
            "name": role.name,
            "trigger": f"@{role.name}",
            "description": role.description
        })

    if profiles:
        register_result = await nanoclaw_client.register_group(
            chat_id=group.group_id,
            folder=f"group_{group.group_id}",
            profiles=profiles,
            is_group=group.is_group,
            requires_trigger=group.requires_trigger
        )
        if "error" in register_result:
            logger.warning(f"NanoClaw 注册群组失败: {register_result}")
        else:
            logger.info(f"NanoClaw 注册群组成功: group_id={group.group_id}, profiles={len(profiles)}")

    logger.info(f"创建群组成功: group_id={data.group_id}, group_name={data.group_name}, role_ids={data.role_ids}")

    return _build_group_response(group)


@router.put("/group/{group_id}", response_model=AIGroupResponse, summary="更新群组")
async def update_group(
    group_id: str,
    data: AIGroupUpdate,
    db: AsyncSession = Depends(get_db)
) -> AIGroupResponse:
    """
    更新群组

    更新群组配置信息，并同步到 NanoClaw。

    Args:
        group_id: 群组ID（UUID）
        data: 群组更新数据（包含 role_ids）
    """
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 更新群组基础信息（不包含 role_ids）
    update_data = data.model_dump(exclude={'role_ids'}, exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    # 如果有 role_ids，更新角色关联
    if data.role_ids is not None:
        roles = await AIRoleService.get_roles_by_ids(db, data.role_ids)
        group.roles = roles

    await db.commit()
    await db.refresh(group)

    # 同步到 NanoClaw（更新群组配置）
    profiles = []
    for role in group.roles:
        profiles.append({
            "id": role.role_id or str(role.id),
            "name": role.name,
            "trigger": f"@{role.name}",
            "description": role.description
        })

    if profiles:
        update_result = await nanoclaw_client.update_group(
            chat_id=group.group_id,
            profiles=profiles,
            requires_trigger=group.requires_trigger
        )
        if "error" in update_result:
            logger.warning(f"NanoClaw 更新群组失败: {update_result}")
        else:
            logger.info(f"NanoClaw 更新群组成功: group_id={group.group_id}, profiles={len(profiles)}")

    logger.info(f"更新群组成功: group_id={group_id}, role_ids={data.role_ids}")

    return _build_group_response(group)


@router.delete("/group/{group_id}", summary="删除群组")
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除群组（软删除）

    Args:
        group_id: 群组ID（UUID）
    """
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 先从 NanoClaw 删除
    delete_result = await nanoclaw_client.delete_group(group.group_id)
    if "error" in delete_result:
        logger.warning(f"NanoClaw 删除群组失败: {delete_result}")
    else:
        logger.info(f"NanoClaw 删除群组成功: group_id={group.group_id}")

    await AIGroupService.delete(db, group_id)
    logger.info(f"删除群组成功: group_id={group_id}")

    return {"status": "success", "message": "删除成功"}


@router.put("/group/{group_id}/roles", response_model=AIGroupResponse, summary="更新群组角色关联")
async def update_group_roles(
    group_id: str,
    role_ids: List[str] = Body(..., description="角色ID列表"),
    db: AsyncSession = Depends(get_db)
) -> AIGroupResponse:
    """
    更新群组关联的角色

    Args:
        group_id: 群组ID（UUID）
        role_ids: 角色ID列表
    """
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    group = await AIGroupService.update_group_roles(db, group_id, role_ids)
    logger.info(f"更新群组角色关联成功: group_id={group_id}, role_ids={role_ids}")

    return AIGroupResponse.model_validate(group)


@router.get("/group/{group_id}/trigger-words", summary="获取群组触发词列表")
async def get_group_trigger_words(
    group_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取群组的触发词列表（@角色名称）

    Args:
        group_id: 群组ID（UUID）
    """
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    trigger_words = AIGroupService.get_trigger_words(group)
    return {"trigger_words": trigger_words}


@router.get("/group/{group_id}/sessions", response_model=PaginatedResponse[AISessionResponse], summary="群组的会话列表")
async def get_group_sessions(
    group_id: str,
    status: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[AISessionResponse]:
    """
    获取群组的会话列表

    Args:
        group_id: 群组ID（UUID）
        status: 会话状态筛选
        is_active: 是否活跃筛选
        page: 页码
        page_size: 每页数量
    """
    # 先获取群组，确保存在
    group = await AIGroupService.get_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    sessions, total = await AISessionService.get_list_with_filters(
        db,
        group_id=group.group_id,  # 使用外部 group_id
        status=status,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[AISessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


# ==================== 会话管理接口 ====================

@router.get("/session", response_model=PaginatedResponse[AISessionResponse], summary="会话列表")
async def list_sessions(
    group_id: Optional[str] = None,
    status: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[AISessionResponse]:
    """
    会话列表（分页）

    支持按 group_id、status、is_active 筛选。

    Args:
        group_id: 外部系统群组ID
        status: 会话状态（0-活跃, 1-已关闭, 2-已清除）
        is_active: 是否活跃
        page: 页码
        page_size: 每页数量
    """
    sessions, total = await AISessionService.get_list_with_filters(
        db,
        group_id=group_id,
        status=status,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    # 关联查询群组名称
    from sqlalchemy import select
    from core.ai_assistant.model import AIGroup

    items = []
    for s in sessions:
        # 查询群组名称
        group_result = await db.execute(
            select(AIGroup.group_name).where(AIGroup.group_id == s.group_id)
        )
        group_name = group_result.scalar_one_or_none()

        items.append(AISessionResponse(
            id=str(s.id),
            group_id=s.group_id,
            group_name=group_name,
            chat_id=s.chat_id,
            session_name=s.session_name,
            message_count=s.message_count,
            status=s.status,
            start_time=s.start_time,
            last_message_time=s.last_message_time,
            is_active=s.is_active,
            sys_create_datetime=s.sys_create_datetime,
        ))

    return PaginatedResponse(
        items=items,
        total=total,
    )


@router.get("/session/{session_id}", response_model=AISessionDetail, summary="会话详情")
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> AISessionDetail:
    """
    会话详情（含消息列表）

    获取会话详情及所有消息记录。

    Args:
        session_id: 会话ID（UUID）
    """
    session_data = await AISessionService.get_session_with_messages(db, session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = session_data["session"]
    messages = session_data["messages"]
    group_name = session_data["group_name"]
    trigger_words = session_data["trigger_words"]

    return AISessionDetail(
        session=AISessionResponse.model_validate(session),
        messages=[AIMessageResponse.model_validate(m) for m in messages],
        group_name=group_name,
        trigger_words=trigger_words,
    )


@router.post("/session/{session_id}/send", response_model=AIMessageResponse, summary="发送消息")
async def send_message(
    session_id: str,
    data: AIMessageSend,
    db: AsyncSession = Depends(get_db)
) -> AIMessageResponse:
    """
    在会话中发送消息

    向指定会话发送消息，并转发给 NanoClaw。

    Args:
        session_id: 会话ID（UUID）
        data: 消息发送数据
    """
    # 获取会话
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="会话已关闭或已清除，无法发送消息")

    # 获取群组信息
    group = await AIGroupService.get_by_group_id(db, session.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="关联群组不存在")

    # 检查消息数量上限
    should_clear = await ContextManager.should_clear_context(session)
    if should_clear:
        # 达到上限，清除上下文并创建新会话
        new_session, _ = await ContextManager.handle_message_limit(db, session)
        session = new_session
        logger.info(f"达到消息上限，已创建新会话: new_chat_id={session.chat_id}")

    # 发送消息到 NanoClaw（支持回调模式）
    # 使用 group.group_id 作为 chat_id，而不是 session.chat_id
    # 这样同一群组的所有会话共享 NanoClaw 的上下文
    callback_url = settings.NANOCLAW_CALLBACK_URL
    try:
        result = await nanoclaw_client.send_message(
            chat_id=group.group_id,  # 使用群组 ID，保持上下文共享
            sender="admin",  # 管理端发送，使用 admin 作为 sender
            content=data.content,
            sender_name="管理员",
            is_group=group.is_group,
            callback_url=callback_url,  # 传递回调 URL
        )

        if "error" in result:
            logger.error(f"NanoClaw 发送消息失败: {result}")
            raise HTTPException(status_code=500, detail="NanoClaw 发送消息失败")

        nanoclaw_message_id = result.get("message_id")
        logger.info(f"NanoClaw 发送消息成功: chat_id={group.group_id}, session_id={session.id}, callback_mode={bool(callback_url)}")

        # 如果使用回调模式，启动保底轮询任务
        if callback_url:
            _start_poll_fallback_task(
                chat_id=group.group_id,  # 使用群组 ID
                session_id=str(session.id),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NanoClaw 发送消息异常: {str(e)}")
        raise HTTPException(status_code=500, detail="NanoClaw 发送消息异常")

    # 创建用户消息记录
    message = await AIMessageService.create_user_message(
        db,
        session_id=str(session.id),
        sender_id="admin",
        content=data.content,
        sender_name="管理员",
        nanoclaw_message_id=nanoclaw_message_id,
        auto_commit=False,  # 不自动提交，统一事务处理
    )

    # 更新会话活跃时间
    await AISessionService.update_session_activity(db, str(session.id), auto_commit=False)

    # 更新群组最后消息时间
    await AIGroupService.update_last_message_time(db, session.group_id, auto_commit=False)

    # 统一提交事务
    await db.commit()
    await db.refresh(message)

    return AIMessageResponse.model_validate(message)


@router.post("/session/{session_id}/clear", summary="清除上下文")
async def clear_session_context(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    清除会话上下文

    手动清除会话上下文，保留最近 N 条消息并创建新会话。

    Args:
        session_id: 会话ID（UUID）
    """
    # 获取会话
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="会话已关闭，无法清除上下文")

    # 获取群组信息
    group = await AIGroupService.get_by_group_id(db, session.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="关联群组不存在")

    # 执行清除上下文
    new_session, recovery_messages = await ContextManager.handle_message_limit(db, session)

    logger.info(
        f"清除上下文成功: "
        f"old_session={session.chat_id}, "
        f"new_session={new_session.chat_id}, "
        f"recovered={len(recovery_messages)} messages"
    )

    return {
        "status": "success",
        "message": "清除上下文成功",
        "new_session_id": str(new_session.id),
        "new_chat_id": new_session.chat_id,
        "recovered_count": len(recovery_messages),
    }


@router.post("/session/{session_id}/close", summary="关闭会话")
async def close_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    关闭会话

    将会话标记为关闭状态。

    Args:
        session_id: 会话ID（UUID）
    """
    # 获取会话
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="会话已关闭或已清除")

    # 关闭会话
    session = await AISessionService.close_session(db, session_id)
    logger.info(f"关闭会话成功: session_id={session_id}, chat_id={session.chat_id}")

    return {
        "status": "success",
        "message": "关闭会话成功",
    }


@router.post("/session", response_model=AISessionResponse, summary="手动创建会话")
async def create_session(
    data: AISessionCreate,
    db: AsyncSession = Depends(get_db)
) -> AISessionResponse:
    """
    为指定群组手动创建新会话

    群组必须已存在。

    Args:
        data: 包含 group_id 的创建参数
    """
    # 获取群组（群组必须已存在）
    group = await AIGroupService.get_by_group_id(db, data.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在，请先在群组管理中创建")

    # 创建新会话
    new_session = await ContextManager.create_new_session(db, group)

    await db.commit()
    await db.refresh(new_session)

    logger.info(f"手动创建会话成功: group_id={group.group_id}, chat_id={new_session.chat_id}")

    return AISessionResponse.model_validate(new_session)


@router.delete("/session/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除会话（软删除）

    同时删除该会话的所有消息记录。
    """
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 删除会话的消息记录
    await AIMessageService.delete_messages_by_session(db, session_id, auto_commit=False)

    # 删除会话
    await AISessionService.delete(db, session_id)

    logger.info(f"删除会话成功: session_id={session_id}, chat_id={session.chat_id}")

    return {"status": "success", "message": "删除成功"}
async def create_new_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> AISessionResponse:
    """
    为群组创建新会话

    根据现有会话的群组信息创建新的活跃会话。

    Args:
        session_id: 当前会话ID（UUID）
    """
    # 获取当前会话
    session = await AISessionService.get_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 获取群组信息
    group = await AIGroupService.get_by_group_id(db, session.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="关联群组不存在")

    # 关闭当前会话（如果活跃）
    if session.status == SessionStatus.ACTIVE:
        await AISessionService.close_session(db, session_id, auto_commit=False)

    # 创建新会话（不自动提交）
    new_session = await ContextManager.create_new_session(db, group, auto_commit=False)

    # 统一提交事务
    await db.commit()
    await db.refresh(new_session)

    logger.info(
        f"创建新会话成功: "
        f"old_session={session.chat_id}, "
        f"new_session={new_session.chat_id}"
    )

    return AISessionResponse.model_validate(new_session)


# ==================== Skill 管理接口 ====================

@router.get("/skill", response_model=AISkillListResponse, summary="Skill 列表")
async def list_skills(
    db: AsyncSession = Depends(get_db),
    search_keyword: Optional[str] = Query(None, description="搜索关键词"),
    filter_type: Optional[str] = Query(None, description="筛选类型: assigned/unassigned"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
):
    """
    Skill 列表

    从 NanoClaw 获取所有 Skill，并查询分配位置。支持搜索和分页。
    """
    skills = await AISkillService.get_skill_list()

    # 为每个 Skill 查询分配位置
    skills_with_assignments = []
    for skill in skills:
        skill_id = skill.get("id")
        assignments = await AISkillService.get_skill_assignments(skill_id, db)
        skill["assigned_locations"] = assignments
        skills_with_assignments.append(AISkillResponse(**skill))

    # 搜索过滤
    if search_keyword:
        keywords = search_keyword.lower()
        skills_with_assignments = [
            s for s in skills_with_assignments
            if keywords in s.id.lower() or (s.name and keywords in s.name.lower())
        ]

    # 状态过滤
    if filter_type == "assigned":
        skills_with_assignments = [
            s for s in skills_with_assignments if s.assigned_locations
        ]
    elif filter_type == "unassigned":
        skills_with_assignments = [
            s for s in skills_with_assignments if not s.assigned_locations
        ]

    # 分页
    total = len(skills_with_assignments)
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = skills_with_assignments[start:end]

    return AISkillListResponse(
        items=paged_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/skill/{skill_id}", response_model=AISkillResponse, summary="Skill 详情")
async def get_skill_detail(skill_id: str, db: AsyncSession = Depends(get_db)) -> AISkillResponse:
    """
    Skill 详情

    Args:
        skill_id: Skill ID
    """
    skill = await AISkillService.get_skill_detail(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    # 查询分配位置
    assignments = await AISkillService.get_skill_assignments(skill_id, db)
    skill["assigned_locations"] = assignments

    return AISkillResponse(**skill)


@router.post("/skill", response_model=AISkillResponse, summary="创建 Skill")
async def create_skill(data: AISkillCreate, db: AsyncSession = Depends(get_db)) -> AISkillResponse:
    """
    创建 Skill

    Args:
        data: Skill 创建数据（含 id 和 content）
    """
    # 验证 Skill ID 格式
    import re
    if not re.match(r'^[a-zA-Z0-9\-]+$', data.id):
        raise HTTPException(
            status_code=400,
            detail="Skill ID 格式错误：只允许字母、数字、短横线"
        )

    # 验证 frontmatter 格式
    parsed = AISkillService.parse_frontmatter(data.content)
    if not parsed:
        raise HTTPException(
            status_code=400,
            detail="SKILL.md 格式错误：缺少有效的 YAML frontmatter"
        )

    skill = await AISkillService.create_skill(data.id, data.content)
    if not skill:
        raise HTTPException(status_code=500, detail="NanoClaw 创建 Skill 失败")

    logger.info(f"创建 Skill 成功: id={data.id}")
    return AISkillResponse(**skill)


@router.put("/skill/{skill_id}", response_model=AISkillResponse, summary="更新 Skill")
async def update_skill(
    skill_id: str,
    data: AISkillUpdate,
    db: AsyncSession = Depends(get_db)
) -> AISkillResponse:
    """
    更新 Skill

    Args:
        skill_id: Skill ID
        data: Skill 更新数据（含 content）
    """
    skill = await AISkillService.update_skill(skill_id, data.content)
    if not skill:
        raise HTTPException(status_code=500, detail="NanoClaw 更新 Skill 失败")

    # 查询分配位置
    assignments = await AISkillService.get_skill_assignments(skill_id, db)
    skill["assigned_locations"] = assignments

    logger.info(f"更新 Skill 成功: id={skill_id}")
    return AISkillResponse(**skill)


@router.delete("/skill/{skill_id}", summary="删除 Skill")
async def delete_skill(skill_id: str):
    """
    删除 Skill

    Args:
        skill_id: Skill ID
    """
    success = await AISkillService.delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=500, detail="NanoClaw 删除 Skill 失败")

    logger.info(f"删除 Skill 成功: id={skill_id}")
    return {"status": "success", "message": "删除成功"}


@router.get("/skill/{skill_id}/assignments", summary="查询 Skill 分配位置")
async def get_skill_assignments(skill_id: str, db: AsyncSession = Depends(get_db)):
    """
    查询 Skill 已分配的群组角色列表

    Args:
        skill_id: Skill ID
    """
    skill = await AISkillService.get_skill_detail(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    assignments = await AISkillService.get_skill_assignments(skill_id, db)

    return {
        "skill_id": skill_id,
        "assignments": assignments,
        "count": len(assignments),
    }


@router.post("/skill/{skill_id}/assign", summary="分配 Skill 到群组角色")
async def assign_skill(skill_id: str, data: SkillAssignment):
    """
    分配 Skill 到指定群组的指定角色

    Args:
        skill_id: Skill ID
        data: 分配请求（含 jid 和 profile_id）
    """
    success = await AISkillService.assign_skill(skill_id, data.jid, data.profile_id)
    if not success:
        raise HTTPException(status_code=500, detail="NanoClaw 分配 Skill 失败")

    logger.info(f"分配 Skill 成功: skill={skill_id} -> jid={data.jid}, profile={data.profile_id}")
    return {"status": "success", "message": "分配成功"}


@router.delete("/skill/{skill_id}/assign", summary="移除 Skill 分配")
async def remove_skill_assignment(skill_id: str, data: SkillAssignmentRemove):
    """
    移除指定群组角色的 Skill

    Args:
        skill_id: Skill ID
        data: 移除请求（含 jid 和 profile_id）
    """
    success = await AISkillService.remove_skill_assignment(
        skill_id, data.jid, data.profile_id
    )
    if not success:
        raise HTTPException(status_code=500, detail="NanoClaw 移除 Skill 分配失败")

    logger.info(f"移除 Skill 分配成功: skill={skill_id} from jid={data.jid}, profile={data.profile_id}")
    return {"status": "success", "message": "移除成功"}