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

from sqlalchemy import and_, or_, select
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
        machine_ids = template_data.get("machine_ids") or []
        if machine_ids and not template_data.get("machine_targets"):
            template_data["machine_targets"] = await cls._snapshot_targets(
                db, machine_ids
            )
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
        machine_ids = update_data.get("machine_ids") or []
        if "machine_ids" in update_data and "machine_targets" not in update_data:
            update_data["machine_targets"] = await cls._snapshot_targets(
                db, machine_ids
            )
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
    async def _snapshot_targets(
        cls,
        db: AsyncSession,
        machine_ids: List[str],
    ) -> List[dict]:
        """把前端选择的机器 ID 固化为稳定的物理设备身份。"""
        if not machine_ids:
            return []
        result = await db.execute(
            select(EnvMachine).where(
                EnvMachine.id.in_(machine_ids),
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
            )
        )
        machine_map = {str(machine.id): machine for machine in result.scalars().all()}
        return [
            {
                "machine_id": str(machine_id),
                "ip": machine_map[str(machine_id)].ip,
                "device_type": machine_map[str(machine_id)].device_type,
                "device_sn": machine_map[str(machine_id)].device_sn,
            }
            for machine_id in machine_ids
            if str(machine_id) in machine_map
        ]

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
        """解析单条模板的机器统计：total/available/online/using/offline/lost。

        - total: 模板 machine_ids 总数
        - available: 在 EnvMachine 中且 is_deleted=false 且 is_virtual=false 的数量
        - online: available 中 status="online" 的数量
        - using: available 中 status="using" 的数量（使用中不等于离线）
        - offline: available 中其余状态的数量
        - lost: machine_ids 中不在 EnvMachine（已删除/虚拟）的数量
        空 machine_ids 全 0。
        """
        resolved = await cls.resolve_machines(db, template)
        total = len(resolved)
        if total == 0:
            return MachineSelectionTemplateStatsResponse()

        existing = [machine for _, machine in resolved if machine is not None]

        available = len(existing)
        online = sum(1 for m in existing if m.status == "online")
        using = sum(1 for m in existing if m.status == "using")
        offline = available - online - using
        lost = total - available

        return MachineSelectionTemplateStatsResponse(
            total=total,
            available=available,
            online=online,
            using=using,
            offline=offline,
            lost=lost,
        )

    @classmethod
    async def resolve_machines(
        cls,
        db: AsyncSession,
        template: MachineSelectionTemplate,
    ) -> List[tuple[dict, Optional[EnvMachine]]]:
        """按物理设备身份解析模板当前对应的机器。"""
        raw_targets = getattr(template, "machine_targets", None)
        targets = raw_targets if isinstance(raw_targets, list) else []

        # 兼容尚未回填 machine_targets 的旧记录。
        if not targets:
            raw_machine_ids = getattr(template, "machine_ids", None)
            machine_ids = raw_machine_ids if isinstance(raw_machine_ids, list) else []
            if not machine_ids:
                return []
            result = await db.execute(
                select(EnvMachine).where(
                    EnvMachine.id.in_(machine_ids),
                    EnvMachine.is_deleted == False,  # noqa: E712
                    EnvMachine.is_virtual == False,  # noqa: E712
                )
            )
            machine_map = {str(machine.id): machine for machine in result.scalars().all()}
            return [
                ({"machine_id": str(machine_id)}, machine_map.get(str(machine_id)))
                for machine_id in machine_ids
            ]

        valid_targets = [
            target
            for target in targets
            if target.get("ip") and target.get("device_type")
        ]
        conditions = []
        for target in valid_targets:
            physical_condition = and_(
                EnvMachine.ip == target["ip"],
                EnvMachine.device_type == target["device_type"],
            )
            if "device_sn" in target:
                device_sn = target["device_sn"]
                physical_condition = and_(
                    physical_condition,
                    EnvMachine.device_sn == device_sn
                    if device_sn is not None
                    else EnvMachine.device_sn.is_(None),
                )
            machine_id = target.get("machine_id")
            conditions.append(
                or_(
                    EnvMachine.id == machine_id,
                    physical_condition,
                )
                if machine_id
                else physical_condition
            )
        if not conditions:
            return [(target, None) for target in targets]

        result = await db.execute(
            select(EnvMachine)
            .where(
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.is_virtual == False,  # noqa: E712
                or_(*conditions),
            )
            .order_by(EnvMachine.sys_update_datetime.desc())
        )
        machine_map = {}
        machine_id_map = {}
        host_machine_map = {}
        for machine in result.scalars().all():
            identity = (machine.ip, machine.device_type, machine.device_sn)
            machine_map.setdefault(identity, machine)
            machine_id_map[str(machine.id)] = machine
            host_machine_map.setdefault((machine.ip, machine.device_type), []).append(machine)

        resolved = []
        for target in targets:
            ip = target.get("ip")
            device_type = target.get("device_type")
            machine = machine_id_map.get(str(target["machine_id"])) if target.get("machine_id") else None
            if machine is None and "device_sn" in target:
                machine = machine_map.get((ip, device_type, target["device_sn"]))
            elif machine is None:
                candidates = host_machine_map.get((ip, device_type), [])
                machine = candidates[0] if len(candidates) == 1 else None
            resolved.append((target, machine))
        return resolved

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

        resolved = await cls.resolve_machines(db, template)
        if not resolved:
            return MachineSelectionTemplateDetailResponse(
                template_id=str(template.id),
                machines=[],
            )

        machines: List[MachineDetailResponse] = []
        for target, m in resolved:
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
                    id=str(target.get("machine_id") or f"{target.get('ip')}:{target.get('device_type')}"),
                    ip=target.get("ip"),
                    device_type=target.get("device_type"),
                    status=None,
                    exists=False,
                ))

        return MachineSelectionTemplateDetailResponse(
            template_id=str(template.id),
            machines=machines,
        )
