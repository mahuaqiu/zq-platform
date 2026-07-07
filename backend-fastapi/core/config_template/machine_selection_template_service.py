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
)

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
