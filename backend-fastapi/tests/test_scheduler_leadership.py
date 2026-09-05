"""调度器领导权租约接入测试（不真正启动 APScheduler，只测租约门控）。"""
from unittest.mock import AsyncMock

import pytest

from core.scheduler.service import scheduler_service


@pytest.fixture(autouse=True)
def _reset_singleton():
    scheduler_service._running = False
    scheduler_service._scheduler = None
    scheduler_service._lease = None
    yield
    scheduler_service._running = False
    scheduler_service._scheduler = None
    scheduler_service._lease = None


@pytest.mark.asyncio
async def test_init_scheduler_skipped_when_lease_taken(monkeypatch):
    async def _taken(key, on_lost=None):
        return None

    monkeypatch.setattr(
        "core.env_machine.lock_manager.EnvLockManager.try_acquire_lease", _taken
    )
    assert await scheduler_service.init_scheduler() is False
    assert scheduler_service._scheduler is None
    assert scheduler_service._running is False


@pytest.mark.asyncio
async def test_init_scheduler_idempotent_when_running():
    scheduler_service._running = True
    assert await scheduler_service.init_scheduler() is True
    assert scheduler_service._scheduler is None  # 未走到创建分支


@pytest.mark.asyncio
async def test_shutdown_releases_lease():
    class _FakeLease:
        def __init__(self):
            self.released = False

        async def release(self):
            self.released = True

    lease = _FakeLease()
    scheduler_service._lease = lease
    scheduler_service._scheduler = AsyncMock()
    scheduler_service._running = True
    await scheduler_service.shutdown()
    assert lease.released is True
    assert scheduler_service._lease is None
