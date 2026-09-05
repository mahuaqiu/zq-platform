#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2025-03-25
@File: service.py
@Desc: 执行机基础服务层 - CRUD 操作
"""
import json
import logging
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, Alignment
from pydantic import BaseModel
from sqlalchemy import case, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime

from fastapi import HTTPException

from app.base_service import BaseService
from app.config import get_settings
from core.env_machine.model import EnvMachine
from core.env_machine.lock_manager import EnvLockManager
from core.env_machine.pool_manager import EnvPoolManager
from core.env_machine.schema import EnvRegisterRequest, EnvSuccessResponse

settings = get_settings()

logger = logging.getLogger(__name__)


class EnvMachineCreateSchema(BaseModel):
    """
    创建 Schema 占位类

    由于执行机的创建主要通过注册接口（EnvRegisterRequest）完成，
    这里使用占位类以满足 BaseService 的泛型要求。
    """
    pass


class EnvMachineUpdateSchema(BaseModel):
    """
    更新 Schema 占位类

    执行机的更新主要通过特定的业务接口完成，
    这里使用占位类以满足 BaseService 的泛型要求。
    """
    pass


class EnvMachineService(BaseService[EnvMachine, EnvMachineCreateSchema, EnvMachineUpdateSchema]):
    """
    执行机服务层

    继承 BaseService，自动获得以下基础功能：
    - create(): 创建记录
    - get_by_id(): 根据 ID 获取单条记录
    - get_list(): 获取分页列表
    - update(): 更新记录
    - delete(): 删除记录（支持软删除）
    - batch_delete(): 批量删除
    - export_to_excel(): 导出 Excel
    - import_from_excel(): 导入 Excel
    - check_unique(): 检查字段唯一性
    - get_by_field(): 根据字段获取单条记录
    - exists(): 检查记录是否存在
    """

    model = EnvMachine

    # Excel 导入导出配置
    excel_columns = {
        "namespace": "机器分类",
        "ip": "机器IP",
        "port": "端口",
        "asset_number": "资产编号",
        "device_type": "机器类型",
        "device_sn": "设备SN",
        "mark": "标签",
        "available": "是否启用",
        "status": "状态",
        "version": "版本",
        "note": "备注",
    }
    excel_sheet_name = "执行机列表"

    # 虚拟设备 Excel 导入导出配置
    VIRTUAL_EXCEL_COLUMNS = {
        "namespace": "命名空间",
        "device_type": "机器类型",
        "ip": "机器信息",
        "mark": "标签",
        "extra_message": "扩展信息(JSON)",
        "note": "备注",
    }

    @classmethod
    def _export_converter(cls, item: EnvMachine) -> Dict[str, Any]:
        """导出数据转换器"""
        return {
            "namespace": item.namespace or "",
            "ip": item.ip or "",
            "port": item.port or "",
            "asset_number": item.asset_number or "",
            "device_type": item.device_type or "",
            "device_sn": item.device_sn or "",
            "mark": item.mark or "",
            "available": "是" if item.available else "否",
            "status": item.get_status_display(),
            "version": item.version or "",
            "note": item.note or "",
        }

    @classmethod
    def _import_processor(cls, row: Dict[str, Any]) -> Optional[EnvMachine]:
        """导入数据处理器"""
        namespace = row.get("namespace")
        ip = row.get("ip")
        port = row.get("port")
        device_type = row.get("device_type")

        # 必填字段校验
        if not all([namespace, ip, port, device_type]):
            return None

        available_str = row.get("available", "是")
        available = available_str in ("是", "true", "True", "1", True)

        status_str = row.get("status", "在线")
        status_map = {"在线": "online", "使用中": "using", "离线": "offline"}
        status = status_map.get(status_str, "online")

        return EnvMachine(
            namespace=str(namespace),
            ip=str(ip),
            port=str(port),
            asset_number=str(row.get("asset_number")) if row.get("asset_number") else None,
            device_type=str(device_type),
            device_sn=str(row.get("device_sn")) if row.get("device_sn") else None,
            mark=str(row.get("mark")) if row.get("mark") else None,
            available=available,
            status=status,
            version=str(row.get("version")) if row.get("version") else None,
            note=str(row.get("note")) if row.get("note") else None,
        )

    @classmethod
    def _virtual_import_processor(cls, row: Dict[str, Any]) -> Tuple[Optional[EnvMachine], Optional[str]]:
        """虚拟设备导入处理器，返回 (machine, error_reason)"""
        namespace = row.get("namespace")
        device_type = row.get("device_type")
        ip = row.get("ip")
        mark = row.get("mark")
        extra_message_str = row.get("extra_message")

        if not all([namespace, device_type, ip]):
            return None, "必填字段缺失（namespace, device_type, ip）"

        # Linux 设备：特殊处理
        if device_type == 'linux':
            # Linux 设备必须有 extra_message（SSH 认证信息）
            if not extra_message_str:
                return None, "Linux 设备必须提供 extra_message（SSH 认证信息）"

            try:
                extra_message = json.loads(extra_message_str)
                if not isinstance(extra_message, dict):
                    return None, "扩展信息必须是JSON对象格式"
            except json.JSONDecodeError:
                return None, "扩展信息JSON格式错误"

            # 验证 Linux 认证信息格式
            account = extra_message.get('account', 'root')
            password = extra_message.get('password')
            port = extra_message.get('port', 22)

            if not password:
                return None, "Linux 设备必须提供 SSH 密码（extra_message.password）"

            return EnvMachine(
                namespace=str(namespace),
                device_type='linux',
                asset_number=None,
                ip=str(ip),
                port=None,  # SSH 端口存储在 extra_message.port
                device_sn=None,
                mark=None,  # Linux 设备无标签
                available=False,  # Linux 设备不支持启用
                status='online',  # Linux 设备为真实设备，默认在线，可进行性能采集
                is_virtual=False,
                extra_message={
                    "account": account,
                    "password": password,
                    "port": port,
                },
                note=str(row.get("note")) if row.get("note") else None,
            ), None

        # 其他虚拟设备：原有逻辑
        if not all([mark, extra_message_str]):
            return None, "虚拟设备必填字段缺失（mark, extra_message）"

        try:
            extra_message = json.loads(extra_message_str)
            if not isinstance(extra_message, dict):
                return None, "扩展信息必须是JSON对象格式"
        except json.JSONDecodeError:
            return None, "扩展信息JSON格式错误"

        # 验证标签格式（与编辑时一致）
        mark_str = str(mark).strip()
        tags = [t.strip() for t in mark_str.split(',') if t.strip()]
        for tag in tags:
            # 验证标签格式：小写、合法前缀、下划线后有内容
            is_valid, error_msg = EnvPoolManager.validate_single_tag(tag)
            if not is_valid:
                return None, f"标签 '{tag}' 不合法：{error_msg}"
            # 验证标签在扩展信息中有对应配置
            if not extra_message.get(tag):
                return None, f"标签 '{tag}' 在扩展信息中缺少对应配置"
            if not isinstance(extra_message.get(tag), dict):
                return None, f"标签 '{tag}' 的配置必须是JSON对象格式"

        return EnvMachine(
            namespace=str(namespace),
            device_type=str(device_type),
            asset_number=None,
            ip=str(ip),
            port=None,
            device_sn=None,
            mark=str(mark),
            available=False,
            status="online",
            is_virtual=True,
            extra_message=extra_message,
            note=str(row.get("note")) if row.get("note") else None,
        ), None

    @classmethod
    async def export_to_excel(
        cls,
        db: AsyncSession,
        data_converter: Any = None
    ) -> BytesIO:
        """导出到 Excel"""
        return await super().export_to_excel(db, cls._export_converter)

    @classmethod
    async def import_from_excel(
        cls,
        db: AsyncSession,
        file_content: bytes,
        row_processor: Any = None
    ) -> Tuple[int, int]:
        """从 Excel 导入"""
        return await super().import_from_excel(db, file_content, cls._import_processor)

    @classmethod
    async def import_virtual_from_excel(
        cls,
        db: AsyncSession,
        file_content: bytes,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """从 Excel 导入虚拟设备"""
        wb = openpyxl.load_workbook(BytesIO(file_content))
        ws = wb.active

        success_count = 0
        failed_items = []

        headers = [cell.value for cell in ws[1]]
        column_map = {}
        for key, cn_name in cls.VIRTUAL_EXCEL_COLUMNS.items():
            for idx, header in enumerate(headers):
                if header == cn_name:
                    column_map[key] = idx
                    break

        required_keys = ["namespace", "device_type", "ip", "mark", "extra_message"]
        missing_keys = [k for k in required_keys if k not in column_map]
        if missing_keys:
            missing_cols = [cls.VIRTUAL_EXCEL_COLUMNS[k] for k in missing_keys]
            return 0, [{"row": 0, "reason": f"缺少必填列: {','.join(missing_cols)}"}]

        # 用于检测 Excel 内部重复的集合
        seen_keys = set()

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row):
                continue

            row_dict = {}
            for key, idx in column_map.items():
                row_dict[key] = row[idx] if idx < len(row) else None

            # 检查重复（namespace + ip 组合）
            namespace = row_dict.get("namespace")
            ip = row_dict.get("ip")
            device_type = row_dict.get("device_type")
            if namespace and ip:
                # Linux 设备不拦截（PostgreSQL 唯一约束对 NULL 不生效）
                if device_type != 'linux':
                    # 构建唯一键用于检测 Excel 内部重复
                    unique_key = (namespace, ip, device_type or "")

                    # 检查 Excel 文件内部重复
                    if unique_key in seen_keys:
                        failed_items.append({
                            "row": row_idx,
                            "reason": f"Excel 内部重复：命名空间 '{namespace}'、IP '{ip}' 已在文件中出现"
                        })
                        continue
                    seen_keys.add(unique_key)

                    # 检查数据库中已存在的记录
                    existing = await cls.get_by_ip(db, ip, namespace)
                    if existing:
                        failed_items.append({
                            "row": row_idx,
                            "reason": f"数据库已存在：命名空间 '{namespace}' 下已存在 IP '{ip}'"
                        })
                        continue

            machine, error_reason = cls._virtual_import_processor(row_dict)
            if machine:
                db.add(machine)
                success_count += 1
            else:
                failed_items.append({
                    "row": row_idx,
                    "reason": error_reason or "数据验证失败"
                })

        if success_count > 0:
            await db.commit()

        return success_count, failed_items

    @classmethod
    async def get_by_namespace(
        cls,
        db: AsyncSession,
        namespace: str,
        page: int = 1,
        page_size: int = 100
    ) -> Tuple[List[EnvMachine], int]:
        """
        根据 namespace 获取机器列表

        :param db: 数据库会话
        :param namespace: 机器分类
        :param page: 页码
        :param page_size: 每页数量
        :return: (机器列表, 总数)
        """
        filters = [EnvMachine.namespace == namespace]
        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def get_list_with_filters(
        cls,
        db: AsyncSession,
        namespace: Optional[str] = None,  # 改为 Optional
        device_type: Optional[str] = None,
        ip: Optional[str] = None,
        asset_number: Optional[str] = None,
        mark: Optional[str] = None,
        available: Optional[bool] = None,
        note: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[EnvMachine], int]:
        """
        多条件查询执行机列表

        :param db: 数据库会话
        :param namespace: 机器分类（可选，None表示查询全部）
        :param device_type: 机器类型
        :param ip: IP地址（模糊查询）
        :param asset_number: 资产编号（模糊查询）
        :param mark: 标签（模糊查询）
        :param available: 是否启用
        :param note: 备注（模糊查询）
        :param page: 页码
        :param page_size: 每页数量
        :return: (机器列表, 总数)
        """
        # 定义有效的命名空间列表（排除手工使用，从配置动态获取）
        VALID_NAMESPACES = list(settings.namespace_map.keys())

        filters = [EnvMachine.is_deleted == False]

        if namespace:
            filters.append(EnvMachine.namespace == namespace)
        else:
            # namespace 为 None 时，查询所有4个命名空间
            filters.append(EnvMachine.namespace.in_(VALID_NAMESPACES))

        if device_type:
            filters.append(EnvMachine.device_type == device_type)

        if ip:
            escaped_ip = ip.replace("%", r"\%").replace("_", r"\_")
            filters.append(EnvMachine.ip.ilike(f"%{escaped_ip}%"))

        if asset_number:
            escaped_asset_number = asset_number.replace("%", r"\%").replace("_", r"\_")
            filters.append(EnvMachine.asset_number.ilike(f"%{escaped_asset_number}%"))

        if mark:
            escaped_mark = mark.replace("%", r"\%").replace("_", r"\_")
            filters.append(EnvMachine.mark.ilike(f"%{escaped_mark}%"))

        if available is not None:
            filters.append(EnvMachine.available == available)

        if note:
            escaped_note = note.replace("%", r"\%").replace("_", r"\_")
            filters.append(EnvMachine.note.ilike(f"%{escaped_note}%"))

        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def get_online_machines(
        cls,
        db: AsyncSession,
        namespace: Optional[str] = None,
        device_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Tuple[List[EnvMachine], int]:
        """
        获取在线机器列表

        :param db: 数据库会话
        :param namespace: 可选，按分类筛选
        :param device_type: 可选，按设备类型筛选
        :param page: 页码
        :param page_size: 每页数量
        :return: (机器列表, 总数)
        """
        filters = [
            EnvMachine.status == "online",
            EnvMachine.available == True,  # noqa: E712
        ]

        if namespace:
            filters.append(EnvMachine.namespace == namespace)

        if device_type:
            filters.append(EnvMachine.device_type == device_type)

        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def get_by_ip(
        cls,
        db: AsyncSession,
        ip: str,
        namespace: Optional[str] = None
    ) -> Optional[EnvMachine]:
        """
        根据 IP 获取机器

        :param db: 数据库会话
        :param ip: 机器 IP
        :param namespace: 可选，同时按分类筛选
        :return: 机器记录或 None
        """
        query = select(EnvMachine).where(
            EnvMachine.ip == ip,
            EnvMachine.is_deleted == False  # noqa: E712
        )

        if namespace:
            query = query.where(EnvMachine.namespace == namespace)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_ids(cls, db: AsyncSession, ids: List[str]) -> List[EnvMachine]:
        """
        根据 ID 列表批量获取设备

        Args:
            db: 数据库会话
            ids: 设备 ID 列表

        Returns:
            设备列表
        """
        if not ids:
            return []
        stmt = select(cls.model).where(
            cls.model.id.in_(ids),
            cls.model.is_deleted == False  # noqa: E712
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_by_device_sn(
        cls,
        db: AsyncSession,
        device_sn: str,
        namespace: Optional[str] = None
    ) -> Optional[EnvMachine]:
        """
        根据设备 SN 获取机器

        :param db: 数据库会话
        :param device_sn: 设备序列号
        :param namespace: 可选，同时按分类筛选
        :return: 机器记录或 None
        """
        query = select(EnvMachine).where(
            EnvMachine.device_sn == device_sn,
            EnvMachine.is_deleted == False  # noqa: E712
        )

        if namespace:
            query = query.where(EnvMachine.namespace == namespace)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_device_identity(
        cls,
        db: AsyncSession,
        ip: str,
        device_type: str,
        device_sn: Optional[str] = None
    ) -> List[EnvMachine]:
        """
        根据物理身份获取机器。

        namespace 是机器池归属，可由 Worker 配置切换，不属于物理设备身份。
        宿主机使用 IP + 设备类型，移动设备使用 IP + 设备类型 + SN。

        :param db: 数据库会话
        :param ip: 机器 IP
        :param device_type: 设备类型
        :param device_sn: 设备 SN（移动端必填）
        :return: 按配置完整度排序的匹配记录列表
        """
        query = select(EnvMachine).where(
            EnvMachine.ip == ip,
            EnvMachine.device_type == device_type,
            EnvMachine.is_virtual == False,  # noqa: E712
            EnvMachine.is_deleted == False  # noqa: E712
        )

        if device_sn is not None:
            query = query.where(EnvMachine.device_sn == device_sn)
        else:
            # Windows/Mac 注册上报 null；历史编辑接口可能保存成空字符串，按同一身份处理。
            query = query.where(
                or_(EnvMachine.device_sn.is_(None), EnvMachine.device_sn == "")
            )

        result = await db.execute(
            query.order_by(
                case((EnvMachine.extra_message.is_not(None), 1), else_=0).desc(),
                EnvMachine.available.desc(),
                EnvMachine.sys_update_datetime.desc(),
            )
        )
        return list(result.scalars().all())

    @classmethod
    async def get_by_host_device_type(
        cls,
        db: AsyncSession,
        ip: str,
        device_type: str,
    ) -> List[EnvMachine]:
        """按宿主机和设备类型查询注册候选，用于兼容人工修改过的 SN。"""
        result = await db.execute(
            select(EnvMachine)
            .where(
                EnvMachine.ip == ip,
                EnvMachine.device_type == device_type,
                EnvMachine.is_virtual == False,  # noqa: E712
                EnvMachine.is_deleted == False,  # noqa: E712
            )
            .order_by(
                case((EnvMachine.extra_message.is_not(None), 1), else_=0).desc(),
                EnvMachine.available.desc(),
                EnvMachine.sys_update_datetime.desc(),
            )
        )
        return list(result.scalars().all())

    @classmethod
    async def search(
        cls,
        db: AsyncSession,
        keyword: str,
        namespace: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[EnvMachine], int]:
        """
        搜索执行机（模糊匹配 IP、标签或备注）

        :param db: 数据库会话
        :param keyword: 搜索关键词
        :param namespace: 可选，按分类筛选
        :param page: 页码
        :param page_size: 每页数量
        :return: (机器列表, 总数)
        """
        # 转义 SQL LIKE 特殊字符，防止用户输入的 % 和 _ 被当作通配符
        escaped_keyword = keyword.replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped_keyword}%"

        filters = [
            or_(
                EnvMachine.ip.ilike(pattern),
                EnvMachine.mark.ilike(pattern),
                EnvMachine.note.ilike(pattern),
            )
        ]

        if namespace:
            filters.append(EnvMachine.namespace == namespace)

        return await cls.get_list(db, page=page, page_size=page_size, filters=filters)

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        machine_id: str,
        status: str,
        auto_commit: bool = True
    ) -> Optional[EnvMachine]:
        """
        更新机器状态

        :param db: 数据库会话
        :param machine_id: 机器 ID
        :param status: 新状态（online/using/offline）
        :param auto_commit: 是否自动提交
        :return: 更新后的机器或 None
        """
        valid_statuses = ["online", "using", "offline"]
        if status not in valid_statuses:
            raise ValueError(f"无效的状态值: {status}，有效值为: {valid_statuses}")

        machine = await cls.get_by_id(db, machine_id)
        if not machine:
            return None

        machine.status = status

        if auto_commit:
            await db.commit()
            await db.refresh(machine)
        else:
            await db.flush()
            await db.refresh(machine)

        return machine

    @classmethod
    async def update_available(
        cls,
        db: AsyncSession,
        machine_id: str,
        available: bool,
        auto_commit: bool = True
    ) -> Optional[EnvMachine]:
        """
        更新机器启用状态

        :param db: 数据库会话
        :param machine_id: 机器 ID
        :param available: 是否启用
        :param auto_commit: 是否自动提交
        :return: 更新后的机器或 None
        """
        machine = await cls.get_by_id(db, machine_id)
        if not machine:
            return None

        machine.available = available

        if auto_commit:
            await db.commit()
            await db.refresh(machine)
        else:
            await db.flush()
            await db.refresh(machine)

        return machine

    @classmethod
    async def batch_update_status(
        cls,
        db: AsyncSession,
        ids: List[str],
        status: str
    ) -> Tuple[int, List[str]]:
        """
        批量更新机器状态

        :param db: 数据库会话
        :param ids: 机器 ID 列表
        :param status: 新状态
        :return: (成功数量, 失败的 ID 列表)
        """
        valid_statuses = ["online", "using", "offline"]
        if status not in valid_statuses:
            raise ValueError(f"无效的状态值: {status}，有效值为: {valid_statuses}")

        success_count = 0
        failed_ids = []

        for machine_id in ids:
            machine = await cls.get_by_id(db, machine_id)
            if machine:
                machine.status = status
                success_count += 1
            else:
                failed_ids.append(machine_id)

        if success_count > 0:
            await db.commit()

        return success_count, failed_ids

    @classmethod
    async def batch_update_available(
        cls,
        db: AsyncSession,
        ids: List[str],
        available: bool
    ) -> Tuple[int, List[str]]:
        """
        批量更新机器启用状态

        :param db: 数据库会话
        :param ids: 机器 ID 列表
        :param available: 是否启用
        :return: (成功数量, 失败的 ID 列表)
        """
        success_count = 0
        failed_ids = []

        for machine_id in ids:
            machine = await cls.get_by_id(db, machine_id)
            if machine:
                machine.available = available
                success_count += 1
            else:
                failed_ids.append(machine_id)

        if success_count > 0:
            await db.commit()

        return success_count, failed_ids

    @classmethod
    async def get_stats(cls, db: AsyncSession, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        获取执行机统计信息

        :param db: 数据库会话
        :param namespace: 可选，按分类筛选
        :return: 统计信息字典
        """
        from sqlalchemy import func

        base_filter = [EnvMachine.is_deleted == False]  # noqa: E712
        if namespace:
            base_filter.append(EnvMachine.namespace == namespace)

        # 总数
        total_query = select(func.count(EnvMachine.id)).where(*base_filter)
        total_result = await db.execute(total_query)
        total_count = total_result.scalar() or 0

        # 按状态统计
        status_stats = {}
        for status in ["online", "using", "offline"]:
            status_query = select(func.count(EnvMachine.id)).where(
                *base_filter,
                EnvMachine.status == status
            )
            status_result = await db.execute(status_query)
            status_stats[status] = status_result.scalar() or 0

        # 按设备类型统计
        type_stats = {}
        for device_type in ["windows", "mac", "android", "ios", "harmony_mobile", "harmony_pc", "linux"]:
            type_query = select(func.count(EnvMachine.id)).where(
                *base_filter,
                EnvMachine.device_type == device_type
            )
            type_result = await db.execute(type_query)
            type_stats[device_type] = type_result.scalar() or 0

        # 启用/禁用统计
        available_query = select(func.count(EnvMachine.id)).where(
            *base_filter,
            EnvMachine.available == True  # noqa: E712
        )
        available_result = await db.execute(available_query)
        available_count = available_result.scalar() or 0

        return {
            "total_count": total_count,
            "available_count": available_count,
            "unavailable_count": total_count - available_count,
            "status_stats": status_stats,
            "type_stats": type_stats,
        }

    @classmethod
    async def get_namespaces(cls, db: AsyncSession) -> List[str]:
        """
        获取所有机器分类（去重，排除包含 manual 的分类）

        :param db: 数据库会话
        :return: 分类列表
        """
        from sqlalchemy import distinct

        result = await db.execute(
            select(distinct(EnvMachine.namespace)).where(
                EnvMachine.is_deleted == False,  # noqa: E712
                EnvMachine.namespace.notlike('%manual%')  # 排除包含 manual 的 namespace
            ).order_by(EnvMachine.namespace)
        )
        return [row[0] for row in result.all()]

    @classmethod
    async def get_device_types(cls, db: AsyncSession, namespace: Optional[str] = None) -> List[str]:
        """
        获取所有设备类型（去重）

        :param db: 数据库会话
        :param namespace: 可选，按分类筛选
        :return: 设备类型列表
        """
        from sqlalchemy import distinct

        query = select(distinct(EnvMachine.device_type)).where(
            EnvMachine.is_deleted == False  # noqa: E712
        )

        if namespace:
            query = query.where(EnvMachine.namespace == namespace)

        query = query.order_by(EnvMachine.device_type)

        result = await db.execute(query)
        return [row[0] for row in result.all()]

    @classmethod
    async def generate_virtual_import_template(cls) -> BytesIO:
        """生成虚拟设备导入 Excel 模板"""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "虚拟设备导入模板"

        headers = list(cls.VIRTUAL_EXCEL_COLUMNS.values())
        ws.append(headers)

        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        # 示例行 1: Windows 设备（使用默认配置中的命名空间）
        ws.append([
            "meeting_gamma",
            "windows",
            "192.168.1.100",
            "api",
            '{"api": {"account": "test", "password": "xxx"}}',
            "性能测试账号",
        ])

        # 示例行 2: Linux 设备（SSH 采集，使用默认配置中的命名空间）
        ws.append([
            "meeting_gamma",
            "linux",
            "192.168.1.101",
            "",  # Linux 设备无标签
            '{"account": "root", "password": "your_password", "port": 22}',
            "Linux 性能采集设备",
        ])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @classmethod
    async def batch_enable_with_validation(
        cls,
        db: AsyncSession,
        ids: List[str]
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        批量启用设备（带校验）

        校验规则：
        1. mark 字段必须存在且不为空
        2. extra_message 字段必须存在且为有效 dict
        3. 对于 mark 中的每个标签，extra_message[tag] 必须存在且为 dict

        Args:
            db: 数据库会话
            ids: 设备 ID 列表

        Returns:
            (success_count, skipped_items)
        """
        success_count = 0
        skipped_items = []

        machines = await cls.get_by_ids(db, ids)

        for machine in machines:
            # 校验 1: 标签字段
            mark = machine.mark
            if not mark or not mark.strip():
                skipped_items.append({
                    "id": str(machine.id),
                    "ip": machine.ip or "",
                    "reason": "缺少标签"
                })
                continue

            # 校验 2: 扩展信息字段
            extra_message = machine.extra_message
            if not extra_message or not isinstance(extra_message, dict):
                skipped_items.append({
                    "id": str(machine.id),
                    "ip": machine.ip or "",
                    "reason": "缺少扩展信息"
                })
                continue

            # 校验 3: 标签与扩展信息匹配
            mark_str = str(mark).strip()
            tags = [t.strip() for t in mark_str.split(',') if t.strip()]
            validation_failed = False
            for tag in tags:
                if not extra_message.get(tag):
                    skipped_items.append({
                        "id": str(machine.id),
                        "ip": machine.ip or "",
                        "reason": f"标签 '{tag}' 在扩展信息中缺少对应配置"
                    })
                    validation_failed = True
                    break
                if not isinstance(extra_message.get(tag), dict):
                    skipped_items.append({
                        "id": str(machine.id),
                        "ip": machine.ip or "",
                        "reason": f"标签 '{tag}' 的配置必须是对象格式"
                    })
                    validation_failed = True
                    break

            if validation_failed:
                continue

            # 校验通过，启用设备
            machine.available = True
            success_count += 1

        if success_count > 0:
            await db.commit()

        return success_count, skipped_items


# ==================== 执行机注册编排（自 api.py 原样迁移） ====================

_HOST_REGISTRATION_TYPES = {"windows", "mac"}


def _allows_host_registration_fallback(
    device_type: str,
    device_sn: Optional[str],
) -> bool:
    """判断是否允许从物理身份回退到宿主机身份。"""
    return device_type in _HOST_REGISTRATION_TYPES and not device_sn


def _get_registration_identities(
    data: EnvRegisterRequest,
) -> list[tuple[str, str, Optional[str]]]:
    """提取注册请求中的物理设备身份。"""
    identities: list[tuple[str, str, Optional[str]]] = []
    for device_type, device_sns in data.devices.items():
        if device_type in ("windows", "mac"):
            identities.append((data.ip, device_type, None))
            continue
        if device_type not in ("android", "ios", "harmony_mobile", "harmony_pc"):
            continue
        for device_item in device_sns:
            if isinstance(device_item, dict):
                device_sn = device_item.get("udid")
            elif isinstance(device_item, str):
                device_sn = device_item
            else:
                continue
            if device_sn:
                identities.append((data.ip, device_type, device_sn))
    return identities


async def _get_registration_lock_matches(
    db: AsyncSession,
    ip: str,
    device_type: str,
    device_sn: Optional[str],
) -> List[EnvMachine]:
    """返回注册可能更新到的记录，确保旧命名空间也被加锁。

    带 SN 的设备必须按完整物理身份匹配，不能因为同一 IP 和设备类型
    下恰好只有一条记录就锁定并复用另一台设备。
    """
    matches = await EnvMachineService.get_by_device_identity(
        db, ip=ip, device_type=device_type, device_sn=device_sn
    )
    if matches or not _allows_host_registration_fallback(device_type, device_sn):
        return matches

    candidates = await EnvMachineService.get_by_host_device_type(
        db, ip=ip, device_type=device_type
    )
    return candidates if len(candidates) == 1 else []


async def _get_registration_machine(
    db: AsyncSession,
    ip: str,
    device_type: str,
    device_sn: Optional[str],
) -> Optional[EnvMachine]:
    """获取注册主记录，并合并切换命名空间产生的历史重复记录。

    Windows/Mac 不带 SN 时允许按 IP + 设备类型复用历史记录；移动设备
    和鸿蒙设备带有 SN/UDID，必须按完整物理身份匹配，避免多台设备注册
    时互相覆盖。
    """
    matches = await EnvMachineService.get_by_device_identity(
        db,
        ip=ip,
        device_type=device_type,
        device_sn=device_sn,
    )
    if not matches and _allows_host_registration_fallback(device_type, device_sn):
        candidates = await EnvMachineService.get_by_host_device_type(
            db, ip=ip, device_type=device_type
        )
        if len(candidates) == 1:
            matches = candidates
            old_device_sn = matches[0].device_sn
            if matches[0].device_sn != device_sn:
                matches[0].device_sn = device_sn
            logger.warning(
                "注册 SN 与历史记录不一致，按唯一宿主机记录更新: id=%s, ip=%s, "
                "device_type=%s, old_device_sn=%s, new_device_sn=%s",
                matches[0].id,
                ip,
                device_type,
                old_device_sn,
                device_sn,
            )
    if not matches:
        return None

    primary = next(
        (machine for machine in matches if machine.extra_message),
        matches[0],
    )
    if device_sn is None and primary.device_sn == "":
        primary.device_sn = None
    has_duplicates = len(matches) > 1
    for duplicate in matches:
        if duplicate is primary:
            continue
        if not primary.extra_message and duplicate.extra_message:
            primary.extra_message = duplicate.extra_message
        if not primary.mark and duplicate.mark:
            primary.mark = duplicate.mark
        if not primary.note and duplicate.note:
            primary.note = duplicate.note
        if not primary.asset_number and duplicate.asset_number:
            primary.asset_number = duplicate.asset_number
        primary.available = primary.available or duplicate.available
        if duplicate.status == "using":
            primary.status = "using"
        await EnvPoolManager.remove_machine_from_cache(
            str(duplicate.id), duplicate.namespace
        )
        await db.delete(duplicate)
        logger.warning(
            "合并重复执行机记录: primary_id=%s, duplicate_id=%s, ip=%s, device_type=%s",
            primary.id,
            duplicate.id,
            ip,
            device_type,
        )
    if has_duplicates:
        # 先删除冲突行，再由调用方更新 namespace，避免旧唯一约束在 flush 时冲突。
        await db.flush()
    return primary


async def register_env_machine(
    data: EnvRegisterRequest,
    db: AsyncSession,
) -> EnvSuccessResponse:
    """锁住注册涉及的旧、新机器池后执行注册。"""
    async with EnvLockManager.env_registration_lock_or_raise():
        namespaces = {data.namespace}
        for ip, device_type, device_sn in _get_registration_identities(data):
            matches = await _get_registration_lock_matches(
                db, ip=ip, device_type=device_type, device_sn=device_sn
            )
            namespaces.update(machine.namespace for machine in matches if machine.namespace)

        async with EnvLockManager.env_locks_or_raise(namespaces):
            return await _register_env_machine(data, db)


async def _register_env_machine(
    data: EnvRegisterRequest,
    db: AsyncSession,
) -> EnvSuccessResponse:
    """
    执行机注册接口

    执行机启动时调用此接口注册自身信息。

    逻辑：
    1. 遍历 devices 字典
    2. 对于每个 device_type：
       - windows/mac：device_sn 为 null，每个 IP 插入一条记录
       - android/ios/harmony_mobile/harmony_pc：根据 device_sn 列表，每个 sn 插入一条记录
       - 带 SN 的设备只按完整物理身份匹配，不回退到 IP + device_type
    3. 查询条件：ip + device_type + device_sn（namespace 变更时更新原记录）
    4. 不存在则插入：状态设为 online，available 设为 False
    5. 存在则更新 sync_time、status=online
    6. 同步更新 Redis 缓存
    7. 如果从 upgrading 状态变为 online，触发队列中的升级任务
    """
    now = datetime.now()
    has_upgrading_machine = False  # 标记是否有从 upgrading 变为 online 的机器

    try:
        # 遍历 devices 字典
        for device_type, device_sns in data.devices.items():
            if device_type in ("windows", "mac"):
                # Windows/Mac：device_sn 为 null，每个 IP 插入一条记录
                existing_machine = await _get_registration_machine(
                    db,
                    ip=data.ip,
                    device_type=device_type,
                    device_sn=None
                )

                if existing_machine:
                    # 存在则更新 sync_time
                    old_status = existing_machine.status
                    old_namespace = existing_machine.namespace
                    existing_machine.namespace = data.namespace
                    existing_machine.sync_time = now
                    existing_machine.port = data.port
                    if data.version:
                        existing_machine.version = data.version
                    if data.config_version:
                        existing_machine.config_version = data.config_version
                    if data.scripts:
                        existing_machine.scripts = data.scripts

                    # 状态更新规则：
                    # - using: 保持不变，只更新心跳时间（机器正在被使用）
                    # - upgrading: 变为 online（升级完成）
                    # - offline/online: 变为 online（正常心跳）
                    if existing_machine.status != "using":
                        existing_machine.status = "online"
                        # 标记是否有从 upgrading 变为 online 的机器
                        if old_status == "upgrading":
                            has_upgrading_machine = True
                    else:
                        # using 状态保持不变，记录日志
                        logger.info(f"机器正在使用中，保持状态: id={existing_machine.id}, ip={data.ip}, device_type={device_type}")
                    if old_namespace != data.namespace:
                        await EnvPoolManager.remove_machine_from_cache(
                            str(existing_machine.id), old_namespace
                        )
                else:
                    # 不存在则插入
                    new_machine = EnvMachine(
                        namespace=data.namespace,
                        ip=data.ip,
                        port=data.port,
                        device_type=device_type,
                        device_sn=None,
                        status="online",
                        available=False,
                        sync_time=now,
                        version=data.version,
                        config_version=data.config_version,
                        scripts=data.scripts,
                    )
                    db.add(new_machine)

            elif device_type in ("android", "ios", "harmony_mobile", "harmony_pc"):
                # 移动设备和鸿蒙 PC：根据 UDID/SN 列表，每个设备插入一条记录
                # 支持两种格式：字符串列表 ["udid1"] 或对象列表 [{"udid": "udid1"}]
                for device_item in device_sns:
                    if not device_item:
                        continue

                    # 提取 device_sn
                    if isinstance(device_item, dict):
                        device_sn = device_item.get("udid")
                    elif isinstance(device_item, str):
                        device_sn = device_item
                    else:
                        continue

                    if not device_sn:
                        continue

                    existing_machine = await _get_registration_machine(
                        db,
                        ip=data.ip,
                        device_type=device_type,
                        device_sn=device_sn
                    )

                    if existing_machine:
                        # 存在则更新 sync_time
                        old_status = existing_machine.status
                        old_namespace = existing_machine.namespace
                        existing_machine.namespace = data.namespace
                        existing_machine.sync_time = now
                        existing_machine.port = data.port
                        if data.version:
                            existing_machine.version = data.version
                        if data.config_version:
                            existing_machine.config_version = data.config_version
                        if data.scripts:
                            existing_machine.scripts = data.scripts

                        # 状态更新规则：
                        # - using: 保持不变，只更新心跳时间（机器正在被使用）
                        # - upgrading: 变为 online（升级完成）
                        # - offline/online: 变为 online（正常心跳）
                        if existing_machine.status != "using":
                            existing_machine.status = "online"
                            # 标记是否有从 upgrading 变为 online 的机器
                            if old_status == "upgrading":
                                has_upgrading_machine = True
                        else:
                            # using 状态保持不变，记录日志
                            logger.info(f"机器正在使用中，保持状态: id={existing_machine.id}, ip={data.ip}, device_type={device_type}, device_sn={device_sn}")
                        if old_namespace != data.namespace:
                            await EnvPoolManager.remove_machine_from_cache(
                                str(existing_machine.id), old_namespace
                            )
                    else:
                        # 不存在则插入
                        new_machine = EnvMachine(
                            namespace=data.namespace,
                            ip=data.ip,
                            port=data.port,
                            device_type=device_type,
                            device_sn=device_sn,
                            status="online",
                            available=False,
                            sync_time=now,
                            version=data.version,
                            config_version=data.config_version,
                            scripts=data.scripts,
                        )
                        db.add(new_machine)

        # 提交数据库更改
        await db.commit()

        # 如果有从 upgrading 变为 online 的机器，触发队列处理
        if has_upgrading_machine:
            from core.env_machine.upgrade_service import UpgradeConcurrencyService
            processed_count = await UpgradeConcurrencyService.process_queue_batch(db)
            if processed_count > 0:
                logger.info(f"注册后触发队列升级: count={processed_count}")

        # 同步更新 Redis 缓存（查询所有相关的机器）
        # 注意：注册时 available=False，所以不会加入缓存，但如果之前 available=True，需要从缓存移除
        # 这里统一刷新缓存状态
        machines, _ = await EnvMachineService.get_by_namespace(db, data.namespace, page=1, page_size=1000)
        for machine in machines:
            if machine.ip == data.ip:
                await EnvPoolManager.sync_machine_to_cache(machine)

        logger.info(f"执行机注册成功: namespace={data.namespace}, ip={data.ip}")

        return EnvSuccessResponse(status="success", data=None)
    except Exception as e:
        await db.rollback()
        logger.error(f"执行机注册失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")
