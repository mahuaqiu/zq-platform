"""调度器领导权租约回归测试。"""
import asyncio

import pytest

from core.env_machine.lock_manager import EnvLockManager, Lease


@pytest.mark.asyncio
async def test_try_acquire_lease_success(monkeypatch):
    async def _ok(lock_key, holder_id):
        return True
    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _ok)
    lease = await EnvLockManager.try_acquire_lease("env_lock:test_lease")
    assert isinstance(lease, Lease)
    assert lease.lock_keys == ["env_lock:test_lease"]
    assert lease.holder_id


@pytest.mark.asyncio
async def test_try_acquire_lease_conflict_returns_none(monkeypatch):
    async def _conflict(lock_key, holder_id):
        return False
    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _conflict)
    assert await EnvLockManager.try_acquire_lease("env_lock:test_lease") is None


@pytest.mark.asyncio
async def test_lease_release_releases_lock(monkeypatch):
    async def _ok(lock_key, holder_id):
        return True
    released = []

    async def _release(lock_key, holder_id):
        released.append((lock_key, holder_id))
        return True

    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _ok)
    monkeypatch.setattr(EnvLockManager, "_release_single_lock", _release)
    lease = await EnvLockManager.try_acquire_lease("env_lock:test_lease")
    lease.start_renewal()
    await lease.release()
    assert released == [("env_lock:test_lease", lease.holder_id)]


@pytest.mark.asyncio
async def test_lease_loss_invokes_on_lost(monkeypatch):
    lost = []

    async def _ok(lock_key, holder_id):
        return True

    async def _renew_fail(lock_key, holder_id):
        return False

    monkeypatch.setattr(EnvLockManager, "_acquire_single_lock", _ok)
    monkeypatch.setattr(EnvLockManager, "_renew_single_lock", _renew_fail)
    monkeypatch.setattr(EnvLockManager, "RENEW_INTERVAL", 0.01)

    async def _on_lost():
        lost.append(True)

    lease = await EnvLockManager.try_acquire_lease("env_lock:test_lease", on_lost=_on_lost)
    lease.start_renewal()
    await asyncio.sleep(0.2)
    assert lost == [True]
    await lease.release()
