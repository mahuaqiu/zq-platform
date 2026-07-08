#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: Codex
@Time: 2026-07-05
@File: machine_selection_template_service.py
@Desc: MachineSelectionTemplate Service - 机器选择模板服务层
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.config_template.machine_selection_template_model import MachineSelectionTemplate
from core.config_template.schema import (
    MachineSelectionTemplateCreate,
    MachineSelectionTemplateUpdate,
    MachineSelectionTemplateResponse,
    MachineSelectionTemplateStatsResponse,
    MachineDetailResponse,
    MachineSelectionTemplateDetailResponse,
)
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)


class MachineSelectionTemplateService(BaseService):
    """
    机器选择模板服务层
    """

    model = MachineSelectionTemplate

    @staticmethod
    def _generate_version() -> str:
        """生成版本号"""
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @classmethod
    async def create_with_version(
        cls,
        db: AsyncSession,
        data: MachineSelectionTemplateCreate,
        auto_commit: bool = True
    ) -> MachineSelectionTemplate:
        """创建模板并自动生成版本号"""
        version = cls._generate_version()
        template_data = data.model_dump()
        template_data["version"] = version

        db_obj = MachineSelectionTemplate(**template_data)
        db.add(db_obj)

        if auto_commit:
            await db.commit()
            await db.refresh(db_obj)
        else:
            await db.flush()
            await db.refresh(db_obj)

        return db_obj

    @classmethod
    async def update_with_version(
        cls,
        db: AsyncSession,
        template_id: str,
        data: MachineSelectionTemplateUpdate,
        auto_commit: bool = True
    ) -> Optional[MachineSelectionTemplate]:
        """更新模板并自动生成新版本号"""
        template = await cls.get_by_id(db, template_id)
        if not template:
            return None

        version = cls._generate_version()
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)

        template.version = version

        if auto_commit:
            await db.commit()
            await db.refresh(template)
        else:
            await db.flush()
            await db.refresh(template)

        return template

    @classmethod
    async def get_all(cls, db: AsyncSession) -> List[MachineSelectionTemplate]:
        """获取所有模板（排除已删除）"""
        result = await db.execute(
            select(MachineSelectionTemplate)
            .where(MachineSelectionTemplate.is_deleted == False)
            .order_by(MachineSelectionTemplate.sys_create_datetime.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def check_name_unique(
        cls,
        db: AsyncSession,
        name: str,
        exclude_id: Optional[str] = None
    ) -> bool:
        """检查名称是否唯一"""
        return await cls.check_unique(db, "name", name, exclude_id)

    @classmethod
    async def resolve_stats(
        cls,
        db: AsyncSession,
        template: MachineSelectionTemplate
    ) -> MachineSelectionTemplateStatsResponse:
        """解析单条模板的机器统计：total/available/online/offline/lost。

        - total: 模板 machine_ids 总数
        - available: 在 EnvMachine 中且 is_deleted=false 且 is_virtual=false 的数量
        - online: available 中 status="online" 的数量
        - offline: available 中 status!="online" 的数量
        - lost: machine_ids 中不在 EnvMachine（已删除/虚拟）的数量
        空 machine_ids 全 0。
        """
        machine_ids = template.machine_ids or []
        total = len(machine_ids)
        if total == 0:
            return MachineSelectionTemplateStatsResponse()

        # 批量查询存在的机器（未删除、非虚拟）
        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
            )
        )
        existing = list(result.scalars().all())

        available = len(existing)
        online = sum(1 for m in existing if m.status == "online")
        offline = available - online
        lost = total - available

        return MachineSelectionTemplateStatsResponse(
            total=total,
            available=available,
            online=online,
            offline=offline,
            lost=lost,
        )

    @classmethod
    async def get_machines_detail(
        cls,
        db: AsyncSession,
        template_id: str
    ) -> Optional[MachineSelectionTemplateDetailResponse]:
        """获取某模板全部 machine_ids 的明细。

        对每个 id 回填：存在的机器填 ip/device_type/status 且 exists=true；
        不存在的 id 填 null 且 exists=false。明细不含 config_status/config_version。
        模板不存在时返回 None。
        """
        template = await cls.get_by_id(db, template_id)
        if not template:
            return None

        machine_ids = template.machine_ids or []

        if not machine_ids:
            return MachineSelectionTemplateDetailResponse(
                template_id=str(template.id),
                machines=[],
            )

        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
            )
        )
        existing_map = {str(m.id): m for m in result.scalars().all()}

        machines: List[MachineDetailResponse] = []
        for mid in machine_ids:
            m = existing_map.get(str(mid))
            if m is not None:
                machines.append(MachineDetailResponse(
                    id=str(m.id),
                    ip=m.ip,
                    device_type=m.device_type,
                    status=m.status,
                    exists=True,
                ))
            else:
                machines.append(MachineDetailResponse(
                    id=str(mid),
                    ip=None,
                    device_type=None,
                    status=None,
                    exists=False,
                ))

        return MachineSelectionTemplateDetailResponse(
            template_id=str(template.id),
            machines=machines,
        )
