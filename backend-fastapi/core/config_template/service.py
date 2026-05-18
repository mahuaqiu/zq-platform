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
from sqlalchemy.orm.attributes import flag_modified

from app.base_service import BaseService
from app.config import get_settings
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

settings = get_settings()

# Worker 配置接口超时时间（秒）
WORKER_CONFIG_TIMEOUT = 10

# 合法的命名空间列表（用于配置下发筛选，从配置动态获取）
VALID_NAMESPACE_LIST = list(settings.namespace_map.keys())

# 最大并发配置下发数量
MAX_CONCURRENT_CONFIG_DEPLOY = 20


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
        ]

        # 命名空间筛选
        # 前端传了特定 namespace 参数时按参数筛选
        # 前端没传时（全部），只查询合法命名空间的机器
        if namespace:
            conditions.append(EnvMachine.namespace == namespace)
        else:
            conditions.append(EnvMachine.namespace.in_(VALID_NAMESPACE_LIST))

        # 设备类型筛选
        # 脚本类型：根据扩展名自动过滤设备类型，忽略前端传入的 device_type
        if template.type == 'script':
            target_os = cls._get_target_os_from_extension(template.script_name)
            if target_os:
                conditions.append(EnvMachine.device_type == target_os)
        elif device_type:
            # 配置类型：使用前端传入的筛选条件
            conditions.append(EnvMachine.device_type == device_type)
        else:
            # 配置类型、未指定设备类型时：默认只查询 windows 和 mac 设备
            # android/ios 设备不支持配置下发
            conditions.append(EnvMachine.device_type.in_(['windows', 'mac']))

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

    @staticmethod
    def _get_target_os_from_extension(script_name: str) -> str:
        """
        根据脚本扩展名返回目标操作系统

        :param script_name: 脚本名称
        :return: 'windows' 或 'mac' 或 ''
        """
        if not script_name:
            return ''
        ext = script_name.lower().split('.')[-1] if '.' in script_name else ''
        if ext in ('ps1', 'bat'):
            return 'windows'
        elif ext == 'sh':
            return 'mac'
        return ''

    @staticmethod
    def _should_deploy(machine: EnvMachine, template: ConfigTemplate) -> Tuple[bool, Optional[str]]:
        """
        判断是否需要下发配置

        Args:
            machine: 机器对象
            template: 配置模板

        Returns:
            (是否需要下发, 跳过原因)
        """
        # 状态校验
        if machine.status != "online":
            return False, f"机器状态为 {machine.status}"

        # 配置更新中校验
        if machine.config_status == "updating":
            return False, "配置正在更新中"

        # 设备类型校验（脚本类型）
        if template.type == "script":
            target_os = ConfigTemplateService._get_target_os_from_extension(template.script_name)
            if target_os == "windows" and machine.device_type != "windows":
                return False, "脚本仅支持 Windows 设备"
            elif target_os == "mac" and machine.device_type != "mac":
                return False, "脚本仅支持 Mac 设备"

            # 脚本版本校验
            machine_script_version = machine.scripts.get(template.script_name) if machine.scripts else None
            if machine_script_version == template.version:
                return False, "脚本已是最新版本"
        else:
            # 配置类型版本校验
            if machine.config_version == template.version:
                return False, "配置已是最新版本"

        return True, None

    @staticmethod
    async def _deploy_batch(
        tasks: List[Tuple[EnvMachine, ConfigTemplate]],
        batch_size: int = MAX_CONCURRENT_CONFIG_DEPLOY
    ) -> List[Tuple[bool, Optional[str], str]]:
        """
        分批并发下发配置

        Args:
            tasks: 待下发的任务列表（machine, template）
            batch_size: 每批最大并发数

        Returns:
            List[Tuple[是否成功, 错误信息, machine_id]]
        """
        results = []
        total = len(tasks)

        for i in range(0, total, batch_size):
            batch = tasks[i:i + batch_size]
            logger.info(f"下发第 {i//batch_size + 1} 批，共 {len(batch)} 台")

            # 批次内并发执行
            batch_tasks = [
                ConfigTemplateService._send_config_to_worker(m, t) if t.type != "script"
                else ConfigTemplateService._send_script_to_worker(m, t)
                for m, t in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 处理批次结果（使用批次内索引）
            for idx, task_result in enumerate(batch_results):
                if isinstance(task_result, Exception):
                    results.append((False, str(task_result), batch[idx][0].id))
                else:
                    results.append(task_result)

            logger.info(f"第 {i//batch_size + 1} 批完成，成功 {sum(1 for r in batch_results if not isinstance(r, Exception) and r[0])} 台")

        return results

    @classmethod
    async def deploy_config(
        cls,
        db: AsyncSession,
        template_id: str,
        machine_ids: List[str],
    ) -> DeployResponse:
        """
        下发配置到机器（带并发控制和校验）
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
                    EnvMachine.is_deleted == False,
                )
            )
        )
        machines = result.scalars().all()

        response = DeployResponse()
        deploy_tasks = []
        deploy_machine_map = {}

        # 遍历校验
        for machine in machines:
            should_deploy, skip_reason = cls._should_deploy(machine, template)

            if not should_deploy:
                response.skipped_count += 1
                response.details.append(DeployDetail(
                    machine_id=machine.id,
                    ip=machine.ip,
                    status="skipped",
                    error_message=None,
                    skip_reason=skip_reason,
                ))
                continue

            # 设置 config_status 为 updating
            machine.config_status = "updating"

            # 收集待下发任务
            deploy_tasks.append((machine, template))
            deploy_machine_map[machine.id] = machine

        # 分批下发
        if deploy_tasks:
            logger.info(f"开始下发配置到 {len(deploy_tasks)} 台机器，类型: {template.type}")
            results = await cls._deploy_batch(deploy_tasks)

            # 处理结果
            for success, error_msg, machine_id in results:
                machine = deploy_machine_map[machine_id]

                if success:
                    # 更新版本字段
                    if template.type == "config":
                        machine.config_version = template.version
                    else:
                        if machine.scripts is None:
                            machine.scripts = {}
                        machine.scripts[template.script_name] = template.version
                        flag_modified(machine, "scripts")

                    # 清除 config_status
                    machine.config_status = None

                    response.success_count += 1
                    response.details.append(DeployDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="success",
                        error_message=None,
                        skip_reason=None,
                    ))
                else:
                    # 下发失败，清除 config_status
                    machine.config_status = None

                    response.failed_count += 1
                    response.details.append(DeployDetail(
                        machine_id=machine.id,
                        ip=machine.ip,
                        status="failed",
                        error_message=error_msg,
                        skip_reason=None,
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
            "config_version": template.version,
            "config_content": template.config_content,
            "namespace": template.namespace,
        }

        try:
            async with httpx.AsyncClient(
                timeout=WORKER_CONFIG_TIMEOUT,
                trust_env=False,
                verify=False
            ) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
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

    @staticmethod
    async def _send_script_to_worker(
        machine: EnvMachine,
        template: ConfigTemplate
    ) -> Tuple[bool, Optional[str], str]:
        """
        调用 Worker scripts 接口下发脚本

        :param machine: 机器对象
        :param template: 配置模板（脚本类型）
        :return: (是否成功, 错误信息, machine_id)
        """
        url = f"http://{machine.ip}:{machine.port}/worker/scripts"
        payload = {
            "name": template.script_name,
            "content": template.config_content,
            "version": template.version,
            "overwrite": True
        }

        try:
            async with httpx.AsyncClient(
                timeout=WORKER_CONFIG_TIMEOUT,
                trust_env=False,
                verify=False
            ) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        return True, None, machine.id
                    else:
                        return False, f"Worker 返回异常状态: {data.get('status')}", machine.id
                elif response.status_code == 409:
                    return False, "脚本更新进行中或已存在", machine.id
                elif response.status_code == 503:
                    return False, "Worker 未初始化", machine.id
                else:
                    return False, f"Worker 返回错误状态码: {response.status_code}", machine.id

        except httpx.TimeoutException:
            return False, "Worker 响应超时", machine.id
        except httpx.ConnectError:
            return False, "无法连接到 Worker", machine.id
        except Exception as e:
            logger.error(f"调用 Worker scripts 接口失败: {e}")
            return False, f"网络错误: {str(e)}", machine.id