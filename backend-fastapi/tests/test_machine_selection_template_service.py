#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-07-08
@File: test_machine_selection_template_service.py
@Desc: IP 模板 Service 统计与明细单测
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.config_template.machine_selection_template_service import (
    MachineSelectionTemplateService,
)
from core.config_template.schema import (
    MachineSelectionTemplateDetailResponse,
)


def _machine(mid, status="online", device_type="windows", ip="10.0.0.1"):
    """构造一个 EnvMachine mock 对象"""
    m = MagicMock()
    m.id = mid
    m.status = status
    m.device_type = device_type
    m.ip = ip
    return m


def _template(machine_ids):
    """构造一个 MachineSelectionTemplate mock 对象"""
    t = MagicMock()
    t.id = "tpl-1"
    t.machine_ids = machine_ids
    return t


class TestResolveStats:
    """resolve_stats 五种 case"""

    @pytest.mark.asyncio
    async def test_empty_ids(self):
        """空 machine_ids 全 0"""
        db = MagicMock()
        stats = await MachineSelectionTemplateService.resolve_stats(db, _template([]))
        assert stats.total == 0
        assert stats.available == 0
        assert stats.online == 0
        assert stats.offline == 0
        assert stats.lost == 0

    @pytest.mark.asyncio
    async def test_all_online(self):
        """全部在线"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="online"),
            _machine("b", status="online"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(db, _template(["a", "b"]))
        assert stats.total == 2
        assert stats.available == 2
        assert stats.online == 2
        assert stats.offline == 0
        assert stats.lost == 0

    @pytest.mark.asyncio
    async def test_all_offline(self):
        """全部离线（status != online）"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="offline"),
            _machine("b", status="using"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(db, _template(["a", "b"]))
        assert stats.available == 2
        assert stats.online == 0
        assert stats.offline == 2

    @pytest.mark.asyncio
    async def test_all_lost(self):
        """全部已删除（EnvMachine 查不到）"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(db, _template(["x", "y", "z"]))
        assert stats.total == 3
        assert stats.available == 0
        assert stats.online == 0
        assert stats.offline == 0
        assert stats.lost == 3

    @pytest.mark.asyncio
    async def test_mixed(self):
        """混合：3 在线 + 1 离线 + 2 已删除"""
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="online"),
            _machine("b", status="online"),
            _machine("c", status="online"),
            _machine("d", status="offline"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        stats = await MachineSelectionTemplateService.resolve_stats(
            db, _template(["a", "b", "c", "d", "gone1", "gone2"])
        )
        assert stats.total == 6
        assert stats.available == 4
        assert stats.online == 3
        assert stats.offline == 1
        assert stats.lost == 2


class TestGetMachinesDetail:
    """get_machines_detail 明细"""

    @pytest.mark.asyncio
    async def test_template_not_found(self):
        """模板不存在返回 None"""
        db = MagicMock()
        with patch.object(
            MachineSelectionTemplateService, "get_by_id", new=AsyncMock(return_value=None)
        ):
            result = await MachineSelectionTemplateService.get_machines_detail(db, "no-such-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_list(self):
        """空 machine_ids 返回空 machines 列表"""
        db = MagicMock()
        tpl = _template([])
        with patch.object(
            MachineSelectionTemplateService, "get_by_id", new=AsyncMock(return_value=tpl)
        ):
            result = await MachineSelectionTemplateService.get_machines_detail(db, "tpl-1")
        assert result is not None
        assert result.template_id == "tpl-1"
        assert result.machines == []

    @pytest.mark.asyncio
    async def test_mixed_exists_and_lost(self):
        """混合：存在 + 已删除，明细按 machine_ids 顺序回填"""
        db = MagicMock()
        tpl = _template(["a", "gone", "b"])
        mock_result = MagicMock()
        # 数据库只返回 a、b
        mock_result.scalars.return_value.all.return_value = [
            _machine("a", status="online", device_type="windows", ip="10.0.0.1"),
            _machine("b", status="offline", device_type="mac", ip="10.0.0.2"),
        ]
        db.execute = AsyncMock(return_value=mock_result)

        with patch.object(
            MachineSelectionTemplateService, "get_by_id", new=AsyncMock(return_value=tpl)
        ):
            result = await MachineSelectionTemplateService.get_machines_detail(db, "tpl-1")

        assert isinstance(result, MachineSelectionTemplateDetailResponse)
        assert len(result.machines) == 3

        m0, m1, m2 = result.machines
        assert m0.id == "a" and m0.exists is True and m0.ip == "10.0.0.1" and m0.status == "online"
        assert m1.id == "gone" and m1.exists is False and m1.ip is None and m1.status is None
        assert m2.id == "b" and m2.exists is True and m2.ip == "10.0.0.2" and m2.status == "offline"
