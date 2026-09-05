#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""机器状态唯一写入口。

EnvMachine.status 的全部变更必须经过 MachineStateService.transition：
先校验状态转移合法性，再写 DB 属性，最后统一走 sync_machine_to_cache
（其幂等准入规则：available && online && !deleted && !manual 才入池）。

刻意不加分布式锁：并发语义与历史行为完全一致（见 2026-09-05 重构方案），
本模块消除的是"忘同步缓存/非法转移"的约定漂移，不是并发竞争。
"""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.env_machine.pool_manager import EnvPoolManager
from utils.logging_config import get_logger

logger = get_logger("env_machine.state")

# 合法状态转移表：from -> 允许的 to 集合（同状态幂等写恒合法）
MACHINE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "online": {"using", "upgrading", "offline"},
    "using": {"online", "upgrading", "offline"},   # using->upgrading: 释放后触发延迟升级
    "upgrading": {"online", "offline"},
    "offline": {"online", "using", "upgrading"},
}


@dataclass
class TransitionResult:
    ok: bool
    previous_status: str
    new_status: str
    reason: str = ""


def validate_transition(current: Optional[str], new_status: str) -> bool:
    """校验状态转移合法性；同状态视为合法（心跳/重载的幂等写）。"""
    if current == new_status:
        return True
    return new_status in MACHINE_STATUS_TRANSITIONS.get(current or "", set())


class MachineStateService:
    """EnvMachine.status 的唯一写入口。"""

    @classmethod
    async def transition(
        cls,
        db: AsyncSession,
        machine,
        new_status: str,
        *,
        source: str,
    ) -> TransitionResult:
        """机器状态唯一写入口。失败不抛异常，由调用方按原分支语义处理。

        Args:
            db: 数据库会话（提交时机仍由调用方控制，本函数不 commit）
            machine: EnvMachine ORM 对象
            new_status: 目标状态
            source: 触发来源标识（allocate/release/register/offline_check 等），用于日志追踪
        """
        previous = machine.status
        if not validate_transition(previous, new_status):
            logger.error(
                "拒绝非法状态转移: machine_id=%s, %s -> %s, source=%s",
                machine.id, previous, new_status, source,
            )
            return TransitionResult(False, previous, new_status, "非法状态转移")

        machine.status = new_status
        logger.info(
            "机器状态转移: machine_id=%s, %s -> %s, source=%s",
            machine.id, previous, new_status, source,
        )
        # 统一缓存收尾：sync_machine_to_cache 自带幂等准入规则，
        # 等价于原先各写点自行调用的 sync/remove 两种收尾
        await EnvPoolManager.sync_machine_to_cache(machine)
        return TransitionResult(True, previous, new_status)
