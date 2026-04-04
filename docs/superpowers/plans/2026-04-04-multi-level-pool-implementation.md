# 多层级机器池申请机制实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立三级机器池申请机制，支持私有池 → 项目公共池 → 全局公共池的申请流程。

**Architecture:** 通过前缀匹配规则确定池层级，修改分布式锁策略锁住所有涉及的池，新增日志字段记录机器来源池。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Redis

**Spec:** `docs/superpowers/specs/2026-04-04-multi-level-pool-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend-fastapi/alembic/versions/xxx_add_source_pool.py` | 创建 | 数据库迁移脚本 |
| `backend-fastapi/core/env_machine/log_model.py` | 修改 | 新增 source_pool 字段 |
| `backend-fastapi/core/env_machine/log_schema.py` | 修改 | 新增 source_pool 字段定义 |
| `backend-fastapi/core/env_machine/pool_manager.py` | 修改 | 新增 _get_pool_hierarchy，修改 allocate_machines |
| `backend-fastapi/core/env_machine/lock_manager.py` | 修改 | 修改 _get_required_locks |

---

## Task 1: 数据库迁移脚本

**Files:**
- Create: `backend-fastapi/alembic/versions/20260404_add_source_pool_to_env_machine_log.py`

- [ ] **Step 1: 创建迁移脚本文件**

```python
"""add source_pool to env_machine_log

Revision ID: 20260404_source_pool
Revises: a1b2c3d4e5f6
Create Date: 2026-04-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260404_source_pool'
down_revision = 'a1b2c3d4e5f6'  # 上一个迁移版本
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'env_machine_log',
        sa.Column('source_pool', sa.String(64), nullable=True, comment='机器来源池')
    )


def downgrade() -> None:
    op.drop_column('env_machine_log', 'source_pool')
```

- [ ] **Step 2: 执行迁移**

```bash
cd backend-fastapi && alembic upgrade head
```

Expected: 迁移成功，无错误输出

- [ ] **Step 3: 验证字段已添加**

```bash
cd backend-fastapi && python -c "
from sqlalchemy import inspect
from app.database import engine_sync
insp = inspect(engine_sync)
cols = [c['name'] for c in insp.get_columns('env_machine_log')]
print('source_pool' in cols)
"
```

Expected: `True`

- [ ] **Step 4: 提交**

```bash
git add backend-fastapi/alembic/versions/20260404_add_source_pool_to_env_machine_log.py
git commit -m "feat(env_machine): add source_pool migration script"
```

---

## Task 2: 修改日志模型 (log_model.py)

**Files:**
- Modify: `backend-fastapi/core/env_machine/log_model.py`

- [ ] **Step 1: 添加 source_pool 字段**

在 `mark` 字段后添加 `source_pool` 字段（约第 38 行后）：

```python
    # 申请的标签
    mark = Column(String(255), nullable=True, comment="申请的标签")

    # 机器来源池（新增）
    source_pool = Column(String(64), nullable=True, comment="机器来源池")

    # 操作类型：apply/release
    action = Column(String(20), nullable=False, comment="操作类型: apply/release")
```

- [ ] **Step 2: 更新 __str__ 方法**

```python
    def __str__(self):
        source = self.source_pool or "N/A"
        return f"{self.namespace}/{self.ip or self.device_sn} - {self.action} - {self.result} - from:{source}"
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/env_machine/log_model.py
git commit -m "feat(env_machine): add source_pool field to log model"
```

---

## Task 3: 修改日志 Schema (log_schema.py)

**Files:**
- Modify: `backend-fastapi/core/env_machine/log_schema.py`

- [ ] **Step 1: 修改 EnvMachineLogCreate**

在 `mark` 字段后添加（约第 22 行后）：

```python
class EnvMachineLogCreate(BaseModel):
    """创建申请日志请求"""
    namespace: str = Field(..., description="机器分类")
    machine_id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="机器IP")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")
    mark: Optional[str] = Field(None, description="申请的标签")
    source_pool: Optional[str] = Field(None, description="机器来源池")  # 新增
    action: str = Field(..., description="操作类型: apply/release")
    result: str = Field(..., description="结果: success/fail")
    fail_reason: Optional[str] = Field(None, description="失败原因")
    apply_time: Optional[datetime] = Field(None, description="申请时间")
```

- [ ] **Step 2: 修改 EnvMachineLogResponse**

在 `mark` 字段后添加（约第 43 行后）：

```python
class EnvMachineLogResponse(BaseModel):
    """申请日志响应"""
    id: str = Field(..., description="日志ID")
    namespace: str = Field(..., description="机器分类")
    machine_id: str = Field(..., description="机器ID")
    ip: Optional[str] = Field(None, description="机器IP")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")
    mark: Optional[str] = Field(None, description="申请的标签")
    source_pool: Optional[str] = Field(None, description="机器来源池")  # 新增
    action: str = Field(..., description="操作类型")
    result: str = Field(..., description="结果")
    fail_reason: Optional[str] = Field(None, description="失败原因")
    apply_time: Optional[datetime] = Field(None, description="申请时间")
    release_time: Optional[datetime] = Field(None, description="释放时间")
    duration_minutes: Optional[int] = Field(None, description="占用时长（分钟）")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
```

- [ ] **Step 3: 提交**

```bash
git add backend-fastapi/core/env_machine/log_schema.py
git commit -m "feat(env_machine): add source_pool field to log schema"
```

---

## Task 4: 新增池层级函数 (pool_manager.py)

**Files:**
- Modify: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 添加 _get_pool_hierarchy 函数**

在 `validate_mark_field` 函数后添加（约第 122 行后）：

```python
    @classmethod
    def _get_pool_hierarchy(cls, namespace: str) -> list[str]:
        """
        获取 namespace 的机器池查找顺序

        Args:
            namespace: 申请的命名空间

        Returns:
            list: 查找顺序列表 [私有池, 项目公共池(可选), 全局公共池(可选)]
        """
        pools = [namespace]  # Level 1: 私有池

        # 特殊 namespace 处理
        if namespace == cls.MANUAL_NAMESPACE:
            return []  # manual 不参与申请

        if namespace == cls.PUBLIC_NAMESPACE or namespace.endswith("_public"):
            return pools  # public 和 xxx_public 只查自己池

        # Level 2: 项目公共池（前缀匹配）
        prefix = namespace.split("_")[0]
        project_public = f"{prefix}_public"
        if project_public != namespace:
            pools.append(project_public)

        # Level 3: 全局公共池
        pools.append(cls.PUBLIC_NAMESPACE)  # "public"

        return pools
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "feat(env_machine): add _get_pool_hierarchy function"
```

---

## Task 5: 修改申请逻辑 (pool_manager.py)

**Files:**
- Modify: `backend-fastapi/core/env_machine/pool_manager.py`

- [ ] **Step 1: 修改 allocate_machines 函数**

找到 `allocate_machines` 函数（约第 319 行），修改候选池获取逻辑：

**原代码（第 343-378 行）：**
```python
                # 3. 从 Redis 获取候选机器
                namespace_machines = await cls.get_pool_machines(namespace)

                # 如果不是申请 public，则同时获取 public 池机器
                public_machines = {}
                if namespace != cls.PUBLIC_NAMESPACE:
                    public_machines = await cls.get_pool_machines(cls.PUBLIC_NAMESPACE)
```

**替换为：**
```python
                # 3. 获取查找顺序
                pool_hierarchy = cls._get_pool_hierarchy(namespace)

                if not pool_hierarchy:
                    return False, "namespace 不支持申请"

                # 4. 按顺序获取所有候选池
                candidate_pools: list[tuple[str, dict]] = []
                for pool_ns in pool_hierarchy:
                    machines = await cls.get_pool_machines(pool_ns)
                    candidate_pools.append((pool_ns, machines))
```

- [ ] **Step 2: 修改分配循环逻辑**

**原代码（第 362-378 行）：**
```python
                # 5. 按用户分配机器
                for user, request_tag in requests.items():
                    # 先从 namespace 池中查找
                    allocated = cls._allocate_single(
                        namespace_machines,
                        request_tag,
                        occupied_ips,
                        occupied_sns,
                    )

                    # 如果 namespace 池不够，从 public 池补充
                    if not allocated and public_machines:
                        allocated = cls._allocate_single(
                            public_machines,
                            request_tag,
                            occupied_ips,
                            occupied_sns,
                        )
```

**替换为：**
```python
                # 5. 按用户分配机器
                for user, request_tag in requests.items():
                    # 按池层级顺序查找
                    allocated = None
                    for pool_ns, machines in candidate_pools:
                        allocated = cls._allocate_single(
                            machines,
                            request_tag,
                            occupied_ips,
                            occupied_sns,
                        )
                        if allocated:
                            allocated["source_pool"] = pool_ns  # 记录来源池
                            break
```

- [ ] **Step 3: 修改日志记录逻辑**

找到申请成功日志记录部分（约第 417 行），添加 `source_pool`：

```python
                    await EnvMachineLogService.create_log(db, EnvMachineLogCreate(
                        namespace=namespace,
                        machine_id=allocated["id"],
                        ip=allocated.get("ip"),
                        device_type=allocated.get("actual_device_type") or allocated.get("device_type"),
                        device_sn=allocated.get("device_sn"),
                        mark=requests.get(user),
                        source_pool=allocated.get("source_pool"),  # 新增
                        action="apply",
                        result="success",
                        fail_reason=None,
                        apply_time=now
                    ))
```

- [ ] **Step 4: 修改缓存更新逻辑**

找到缓存更新部分（约第 433 行），修改为：

```python
                # 7. 更新 Redis 缓存（移除已分配的机器）
                for machine_id in allocated_machine_ids:
                    # 从所有涉及的池中移除
                    for pool_ns in pool_hierarchy:
                        await cls.remove_machine_from_cache(machine_id, pool_ns)
```

- [ ] **Step 5: 提交**

```bash
git add backend-fastapi/core/env_machine/pool_manager.py
git commit -m "feat(env_machine): modify allocate_machines for multi-level pool"
```

---

## Task 6: 修改分布式锁策略 (lock_manager.py)

**Files:**
- Modify: `backend-fastapi/core/env_machine/lock_manager.py`

- [ ] **Step 1: 修改 _get_required_locks 函数**

找到 `_get_required_locks` 函数（约第 103-119 行），替换为：

```python
    @classmethod
    def _get_required_locks(cls, namespace: str) -> list[str]:
        """
        获取申请指定命名空间机器所需的锁列表

        锁住所有涉及的池，避免并发分配冲突。

        Args:
            namespace: 申请的命名空间

        Returns:
            list[str]: 需要获取的锁 key 列表（已按字母序排序）
        """
        # 调用 pool_manager 的 _get_pool_hierarchy 获取池层级
        from core.env_machine.pool_manager import EnvPoolManager
        pool_hierarchy = EnvPoolManager._get_pool_hierarchy(namespace)

        if not pool_hierarchy:
            return []

        locks = [cls.LOCK_PREFIX + ns for ns in pool_hierarchy]
        locks.sort()  # 字母序排序，避免死锁
        return locks
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/lock_manager.py
git commit -m "feat(env_machine): lock all involved pools in _get_required_locks"
```

---

## Task 7: 验证和测试

**Files:**
- 无新增文件

- [ ] **Step 1: 验证代码语法**

```bash
cd backend-fastapi && python -m py_compile core/env_machine/pool_manager.py core/env_machine/lock_manager.py core/env_machine/log_model.py core/env_machine/log_schema.py
```

Expected: 无输出表示语法正确

- [ ] **Step 2: 验证函数逻辑（单元测试）**

```bash
cd backend-fastapi && python -c "
from core.env_machine.pool_manager import EnvPoolManager

# 测试 _get_pool_hierarchy 函数
test_cases = [
    ('meeting_gamma', ['meeting_gamma', 'meeting_public', 'public']),
    ('meeting_app', ['meeting_app', 'meeting_public', 'public']),
    ('weli_gamma', ['weli_gamma', 'weli_public', 'public']),
    ('meeting_public', ['meeting_public']),
    ('public', ['public']),
    ('meeting_manual', []),
]

all_passed = True
for namespace, expected in test_cases:
    result = EnvPoolManager._get_pool_hierarchy(namespace)
    if result == expected:
        print(f'✓ {namespace}: {result}')
    else:
        print(f'✗ {namespace}: expected {expected}, got {result}')
        all_passed = False

print()
print('All tests passed!' if all_passed else 'Some tests failed!')
"
```

Expected: 所有测试通过

- [ ] **Step 3: 验证锁逻辑**

```bash
cd backend-fastapi && python -c "
from core.env_machine.lock_manager import EnvLockManager

# 测试 _get_required_locks 函数
test_cases = [
    ('meeting_gamma', ['env_lock:meeting_gamma', 'env_lock:meeting_public', 'env_lock:public']),
    ('meeting_app', ['env_lock:meeting_app', 'env_lock:meeting_public', 'env_lock:public']),
    ('weli_gamma', ['env_lock:public', 'env_lock:weli_gamma', 'env_lock:weli_public']),
    ('meeting_public', ['env_lock:meeting_public']),
    ('public', ['env_lock:public']),
]

all_passed = True
for namespace, expected in test_cases:
    result = EnvLockManager._get_required_locks(namespace)
    if result == expected:
        print(f'✓ {namespace}: {result}')
    else:
        print(f'✗ {namespace}: expected {expected}, got {result}')
        all_passed = False

print()
print('All tests passed!' if all_passed else 'Some tests failed!')
"
```

Expected: 所有测试通过

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat(env_machine): complete multi-level pool implementation

- Add _get_pool_hierarchy for pool hierarchy lookup
- Modify allocate_machines for three-level allocation
- Lock all involved pools to prevent concurrent conflicts
- Add source_pool field to log model and schema
- Update migration script"
```

---

## 检查清单

- [ ] 数据库迁移脚本已创建并执行
- [ ] log_model.py 已添加 source_pool 字段
- [ ] log_schema.py 已添加 source_pool 字段定义
- [ ] pool_manager.py 已添加 _get_pool_hierarchy 函数
- [ ] pool_manager.py 已修改 allocate_machines 逻辑
- [ ] lock_manager.py 已修改 _get_required_locks 函数
- [ ] 所有验证测试通过
- [ ] 代码已提交