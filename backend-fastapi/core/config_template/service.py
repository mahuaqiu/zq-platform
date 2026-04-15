#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: service.py
@Desc: ConfigTemplate Service - 配置模板服务层
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.base_service import BaseService
from core.config_template.model import ConfigTemplate
from core.config_template.schema import (
    ConfigTemplateCreate,
    ConfigTemplateUpdate,
    ConfigPreviewMachine,
    ConfigPreviewResponse,
    DeployDetail,
    DeployResponse,
)
from core.env_machine.model import EnvMachine

logger = logging.getLogger(__name__)

# Worker 配置接口超时时间（秒）
WORKER_CONFIG_TIMEOUT = 10


class ConfigTemplateService(BaseService[ConfigTemplate, ConfigTemplateCreate, ConfigTemplateUpdate]):
    """
    配置模板服务层

    继承 BaseService，自动获得以下基础功能：
    - create(): 创建记录
    - get_by_id(): 根据 ID 获取单条记录
    - get_list(): 获取分页列表
    - update(): 更新记录
    - delete(): 删除记录（支持软删除）
    - batch_delete(): 批量删除
    - check_unique(): 检查字段唯一性
    """

    model = ConfigTemplate

    @staticmethod
    def _generate_version() -> str:
        """
        生成版本号（YYYYMMDD-HHMMSS）

        :return: 版本号字符串
        """
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @classmethod
    async def create_with_version(
        cls,
        db: AsyncSession,
        data: ConfigTemplateCreate,
        auto_commit: bool = True
    ) -> ConfigTemplate:
        """
        创建模板并自动生成版本号

        :param db: 数据库会话
        :param data: 创建数据
        :param auto_commit: 是否自动提交
        :return: 创建的模板
        """
        # 生成版本号
        version = cls._generate_version()

        # 创建模板对象
        template_data = data.model_dump()
        template_data["version"] = version

        db_obj = ConfigTemplate(**template_data)
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
        data: ConfigTemplateUpdate,
        auto_commit: bool = True
    ) -> Optional[ConfigTemplate]:
        """
        更新模板并自动生成新版本号

        :param db: 数据库会话
        :param template_id: 模板 ID
        :param data: 更新数据
        :param auto_commit: 是否自动提交
        :return: 更新后的模板或 None
        """
        template = await cls.get_by_id(db, template_id)
        if not template:
            return None

        # 生成新版本号
        version = cls._generate_version()

        # 更新字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)

        # 更新版本号
        template.version = version

        if auto_commit:
            await db.commit()
            await db.refresh(template)
        else:
            await db.flush()
            await db.refresh(template)

        return template

    @classmethod
    async def get_all(cls, db: AsyncSession) -> List[ConfigTemplate]:
        """
        获取所有模板（排除已删除）

        :param db: 数据库会话
        :return: 模板列表
        """
        result = await db.execute(
            select(ConfigTemplate)
            .where(ConfigTemplate.is_deleted == False)  # noqa: E712
            .order_by(ConfigTemplate.sys_create_datetime.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def check_name_unique(
        cls,
        db: AsyncSession,
        name: str,
        exclude_id: Optional[str] = None
    ) -> bool:
        """
        检查名称是否唯一

        :param db: 数据库会话
        :param name: 模板名称
        :param exclude_id: 排除的模板 ID（用于更新时排除自身）
        :return: True 表示唯一，False 表示已存在
        """
        return await cls.check_unique(db, "name", name, exclude_id)

    @classmethod
    async def get_preview(
        cls,
        db: AsyncSession,
        template_id: str,
        namespace: Optional[str] = None,
        device_type: Optional[str] = None,
        machine_ids: Optional[List[str]] = None
    ) -> ConfigPreviewResponse:
        """
        获取配置下发预览

        :param db: 数据库会话
        :param template_id: 模板 ID
        :param namespace: 可选，按命名空间筛选
        :param device_type: 可选，按设备类型筛选
        :param machine_ids: 可选，指定机器 ID 列表
        :return: 配置预览响应
        """
        # 获取模板
        template = await cls.get_by_id(db, template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        template_version = template.version

        # 构建查询条件
        conditions = [
            EnvMachine.is_deleted == False,  # noqa: E712
            EnvMachine.available == True,  # noqa: E712
        ]

        # 命名空间筛选
        if namespace:
            conditions.append(EnvMachine.namespace == namespace)
        elif template.namespace:
            # 如果模板指定了命名空间，使用模板的命名空间
            conditions.append(EnvMachine.namespace == template.namespace)

        # 设备类型筛选
        if device_type:
            conditions.append(EnvMachine.device_type == device_type)

        # 指定机器 ID
        if machine_ids:
            conditions.append(EnvMachine.id.in_(machine_ids))

        # 查询机器
        result = await db.execute(select(EnvMachine).where(and_(*conditions)))
        machines = result.scalars().all()

        # 统计各类机器数量
        deployable_count = 0
        updating_count = 0
        offline_count = 0
        preview_machines: List[ConfigPreviewMachine] = []

        for machine in machines:
            # 计算配置状态
            config_status = cls._calculate_config_status(machine, template_version)

            machine_preview = ConfigPreviewMachine(
                id=machine.id,
                ip=machine.ip,
                namespace=machine.namespace,
                device_type=machine.device_type,
                status=machine.status,
                config_status=config_status,
                config_version=machine.config_version if hasattr(machine, 'config_version') else None,
            )
            preview_machines.append(machine_preview)

            # 统计数量
            if config_status == "synced":
                # 已同步的机器也计入可下发（可以重新下发）
                deployable_count += 1
            elif config_status == "pending":
                deployable_count += 1
            elif config_status == "updating":
                updating_count += 1
            elif config_status == "offline":
                offline_count += 1

        return ConfigPreviewResponse(
            template_version=template_version,
            deployable_count=deployable_count,
            updating_count=updating_count,
            offline_count=offline_count,
            machines=preview_machines,
        )

    @staticmethod
    def _calculate_config_status(machine: EnvMachine, template_version: str) -> str:
        """
        计算机器的配置状态

        :param machine: 机器对象
        :param template_version: 模板版本号
        :return: 配置状态（synced/pending/updating/offline）
        """
        # 离线状态
        if machine.status == "offline":
            return "offline"

        # 配置更新中
        if hasattr(machine, 'config_status') and machine.config_status == "updating":
            return "updating"

        # 检查配置版本
        machine_config_version = machine.config_version if hasattr(machine, 'config_version') else None

        # 已同步
        if machine_config_version == template_version:
            return "synced"

        # 待更新
        return "pending"

    @classmethod
    async def deploy_config(
        cls,
        db: AsyncSession,
        template_id: str,
        machine_ids: List[str],
    ) -> DeployResponse:
        """
        下发配置到机器

        :param db: 数据库会话
        :param template_id: 模板 ID
        :param machine_ids: 机器 ID 列表
        :return: 下发响应
        """
        # 获取模板
        template = await cls.get_by_id(db, template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        # 查询机器
        result = await db.execute(
            select(EnvMachine).where(
                and_(
                    EnvMachine.id.in_(machine_ids),
                    EnvMachine.is_deleted == False,  # noqa: E712
                    EnvMachine.available == True,  # noqa: E712
                )
            )
        )
        machines = result.scalars().all()

        response = DeployResponse(success_count=0, failed_count=0, details=[])

        # 收集并发任务
        deploy_tasks = []
        deploy_machine_map = {}

        for machine in machines:
            # 跳过离线机器
            if machine.status == "offline":
                response.failed_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="failed",
                    error_message="机器离线"
                ))
                continue

            # 跳过正在更新配置的机器
            if hasattr(machine, 'config_status') and machine.config_status == "updating":
                response.failed_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="failed",
                    error_message="配置正在更新中"
                ))
                continue

            # 收集并发任务
            deploy_tasks.append(cls._send_config_to_worker(machine, template))
            deploy_machine_map[machine.id] = machine

        # 并发下发
        if deploy_tasks:
            logger.info(f"并发下发配置到 {len(deploy_tasks)} 台机器")
            results = await asyncio.gather(*deploy_tasks, return_exceptions=True)

            # 处理结果
            for task_result in results:
                if isinstance(task_result, Exception):
                    logger.error(f"并发任务异常: {task_result}")
                    response.failed_count += 1
                    continue

                success, error_message, machine_id = task_result
                machine = deploy_machine_map[machine_id]

                if success:
                    # 更新机器配置状态
                    if hasattr(machine, 'config_status'):
                        machine.config_status = "updating"
                    if hasattr(machine, 'config_version'):
                        machine.config_version = template.version

                    response.success_count += 1
                    response.details.append(DeployDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="success",
                        error_message=None
                    ))
                else:
                    response.failed_count += 1
                    response.details.append(DeployDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="failed",
                        error_message=error_message
                    ))

        await db.commit()
        return response

    @staticmethod
    async def _send_config_to_worker(
        machine: EnvMachine,
        template: ConfigTemplate
    ) -> Tuple[bool, Optional[str], str]:
        """
        调用 Worker 配置接口

        :param machine: 机器对象
        :param template: 配置模板
        :return: (是否成功, 错误信息, machine_id)
        """
        url = f"http://{machine.ip}:{machine.port}/worker/config"
        payload = {
            "version": template.version,
            "config_content": template.config_content,
            "namespace": template.namespace,
        }

        try:
            async with httpx.AsyncClient(
                timeout=WORKER_CONFIG_TIMEOUT,
                trust_env=True,
                verify=False
            ) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "updating":
                        return True, None, machine.id
                    else:
                        return False, f"Worker 返回异常状态: {data.get('status')}", machine.id
                else:
                    return False, f"Worker 返回错误状态码: {response.status_code}", machine.id

        except httpx.TimeoutException:
            return False, "Worker 响应超时", machine.id
        except httpx.ConnectError:
            return False, "无法连接到 Worker", machine.id
        except Exception as e:
            logger.error(f"调用 Worker 配置接口失败: {e}")
            return False, f"网络错误: {str(e)}", machine.id