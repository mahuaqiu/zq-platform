# 多层级机器池申请机制设计

## 概述

### 背景

当前执行机申请机制采用"私有池 + 全局公共池"模式，每个 namespace 有自己的机器池，不足时从 `public` 池借用。随着业务扩展，需要支持多个项目系列各自独立管理公共池。

### 目标

建立三级机器池申请机制：

```
申请层级结构：

┌─────────────────────────────────────────────────────────────────┐
│  Level 1: 私有池        namespace 本身的机器池                   │
│  Level 2: 项目公共池     同前缀的 _public 池                     │
│  Level 3: 全局公共池     public 池（所有项目共用）               │
└─────────────────────────────────────────────────────────────────┘

示例：
meeting_gamma  → meeting_gamma池 → meeting_public池 → public池
meeting_app    → meeting_app池   → meeting_public池 → public池
weli_gamma     → weli_gamma池    → weli_public池    → public池
public         → public池        （不借用其他）
meeting_public → meeting_public池（不借用其他）
meeting_manual → 不参与申请
```

### 约束

- 前端页面暂不增加菜单
- 现有 `meeting_public` 数据无需迁移
- 新增 `public` namespace 通过 worker 注册产生
- 机器释放后回到原池，归属不变

---

## 核心设计

### 1. Namespace 分类规则

| Namespace 类型 | 示例 | 加入缓存 | 可申请 | 借用规则 |
|---------------|------|---------|-------|---------|
| 私有池 | `meeting_gamma`, `weli_app` | ✅ | ✅ | 私有池 → 项目公共池 → 全局公共池 |
| 项目公共池 | `meeting_public`, `weli_public` | ✅ | ✅ | 只查自己池，不借用其他 |
| 全局公共池 | `public` | ✅ | ✅ | 只查自己池，不借用其他 |
| 手工使用 | `meeting_manual` | ❌ | ❌ | 不参与申请 |

### 2. 查找顺序规则（前缀匹配）

```python
def _get_pool_hierarchy(namespace: str) -> list[str]:
    """
    获取 namespace 的机器池查找顺序
    
    规则：
    1. 私有池（自己）
    2. 项目公共池（前缀 + _public）
    3. 全局公共池（public）
    
    特殊处理：
    - manual 不参与申请
    - public 和 xxx_public 只查自己池
    """
```

**查找顺序示例**：

| 申请方 | 查找顺序 |
|-------|---------|
| `meeting_gamma` | `[meeting_gamma, meeting_public, public]` |
| `meeting_app` | `[meeting_app, meeting_public, public]` |
| `weli_gamma` | `[weli_gamma, weli_public, public]` |
| `meeting_public` | `[meeting_public]` |
| `public` | `[public]` |
| `meeting_manual` | `[]` |

### 3. 释放规则

机器释放后回到原池（`machine.namespace`），归属不变。

申请时只借用机器，不修改机器的 `namespace` 字段，因此释放时 `sync_machine_to_cache` 会自动将机器加入原池。

### 4. 分布式锁设计

#### 问题分析

申请多层级池时，需要锁住所有涉及的池，避免并发分配冲突。

**风险场景**：如果只锁住 `[meeting_gamma, public]`，不锁住 `meeting_public`：
```
T1: 用户A 申请 meeting_gamma  → 锁住 [meeting_gamma, public]
T2: 用户B 申请 meeting_app    → 锁住 [meeting_app, public]
T3: 用户A 从 meeting_public 分配机器 M1
T4: 用户B 也从 meeting_public 分配机器 M1（冲突！）
```

#### 锁策略：锁住所有涉及的池

```python
# lock_manager.py 修改 _get_required_locks 函数

@classmethod
def _get_required_locks(cls, namespace: str) -> list[str]:
    """
    获取申请指定命名空间机器所需的锁列表
    
    Args:
        namespace: 申请的命名空间
        
    Returns:
        list[str]: 需要获取的锁 key 列表（已按字母序排序）
    """
    pool_hierarchy = cls._get_pool_hierarchy(namespace)
    if not pool_hierarchy:
        return []
    locks = [cls.LOCK_PREFIX + ns for ns in pool_hierarchy]
    locks.sort()  # 字母序排序，避免死锁
    return locks
```

#### 锁持有时间估算

几百条机器数据的申请流程：

| 操作 | 预估耗时 |
|------|---------|
| 从 Redis 获取候选池数据 | 1-5 ms |
| 遍历匹配机器 | 1-10 ms |
| 更新数据库状态 | 5-20 ms |
| 记录申请日志 | 5-10 ms |
| 更新 Redis 缓存 | 1-5 ms |
| **总计** | **10-50 ms** |

锁 TTL 为 10 秒，实际持有时间约 10-50 ms，远小于 TTL。

#### 并发影响分析

假设锁持有时间 50ms：

| 场景 | 等待时间 |
|------|---------|
| 同 namespace 申请（meeting_gamma → meeting_gamma） | 0-50ms（串行） |
| 不同 namespace 同系列（meeting_gamma → meeting_app） | 0-50ms（共用 meeting_public 锁） |
| 不同系列（meeting_gamma → weli_gamma） | 0ms（锁不冲突） |

#### 锁列表示例

| 申请方 | 锁住的所有池 | 锁列表（字母序） |
|-------|-------------|----------------|
| `meeting_gamma` | meeting_gamma, meeting_public, public | `[env_lock:meeting_gamma, env_lock:meeting_public, env_lock:public]` |
| `meeting_app` | meeting_app, meeting_public, public | `[env_lock:meeting_app, env_lock:meeting_public, env_lock:public]` |
| `weli_gamma` | weli_gamma, weli_public, public | `[env_lock:public, env_lock:weli_gamma, env_lock:weli_public]` |
| `meeting_public` | meeting_public | `[env_lock:meeting_public]` |
| `public` | public | `[env_lock:public]` |

---

## 详细设计

### 文件修改清单

| 文件 | 修改内容 |
|------|---------|
| `lock_manager.py` | 修改 `_get_required_locks` 函数，锁住所有涉及的池 |
| `pool_manager.py` | 新增 `_get_pool_hierarchy` 函数，修改 `allocate_machines` |
| `log_model.py` | 新增 `source_pool` 字段 |
| `log_schema.py` | 新增 `source_pool` 字段定义 |
| `alembic/versions/xxx.py` | 数据库迁移脚本 |

### pool_manager.py 修改

#### 新增函数

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

### lock_manager.py 修改

#### 修改 _get_required_locks

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

#### 修改 allocate_machines

```python
async def allocate_machines(cls, db, namespace, requests):
    # ... 参数校验和分布式锁 ...
    
    # 获取查找顺序
    pool_hierarchy = cls._get_pool_hierarchy(namespace)
    
    if not pool_hierarchy:
        return False, "namespace 不支持申请"
    
    # 按顺序获取所有候选池
    candidate_pools = []
    for pool_ns in pool_hierarchy:
        machines = await cls.get_pool_machines(pool_ns)
        candidate_pools.append((pool_ns, machines))
    
    # 分配时按顺序查找
    for user, request_tag in requests.items():
        allocated = None
        for pool_ns, machines in candidate_pools:
            allocated = cls._allocate_single(machines, request_tag, occupied_ips, occupied_sns)
            if allocated:
                allocated["source_pool"] = pool_ns  # 记录来源池
                break
        
        if not allocated:
            # 记录失败日志
            await EnvMachineLogService.create_log(...)
            return False, "env not enough"
        
        allocations[user] = allocated
        allocated_machine_ids.append(allocated["id"])
    
    # ... 更新数据库、记录成功日志（含 source_pool）、更新缓存 ...
```

### 日志表修改

#### log_model.py

```python
# 新增字段
source_pool = Column(String(64), nullable=True, comment="机器来源池")
```

#### log_schema.py

```python
class EnvMachineLogCreate(BaseModel):
    # 新增字段
    source_pool: Optional[str] = Field(None, description="机器来源池")

class EnvMachineLogResponse(BaseModel):
    # 新增字段
    source_pool: Optional[str] = Field(None, description="机器来源池")
```

### 数据库迁移脚本

```python
"""add source_pool to env_machine_log

Revision ID: xxx
"""

def upgrade():
    op.add_column(
        'env_machine_log',
        sa.Column('source_pool', sa.String(64), nullable=True, comment='机器来源池')
    )

def downgrade():
    op.drop_column('env_machine_log', 'source_pool')
```

---

## 兼容性分析

### API 接口

- 申请接口签名不变，调用方无需修改
- 新增 `public` namespace 自动生效

### 现有数据

- `meeting_public` 数据无需迁移
- 日志表新增字段不影响现有数据（nullable）

### 扩展性

- 新增项目系列（如 `weli_xxx`）无需修改代码
- 前缀匹配规则自动生效

---

## 测试要点

1. **申请流程测试**
   - 私有池足够时，不从公共池借用
   - 私有池不足时，从项目公共池借用
   - 项目公共池不足时，从全局公共池借用
   - 全局公共池不足时，返回失败

2. **释放流程测试**
   - 释放后机器回到原池（验证 namespace 不变）

3. **边界情况测试**
   - `public` namespace 申请时只查自己池
   - `meeting_public` namespace 申请时只查自己池
   - `meeting_manual` namespace 申请时返回错误

4. **日志验证**
   - 申请成功日志记录正确的 `source_pool`

5. **并发锁测试**
   - 同系列并发申请（meeting_gamma 和 meeting_app 同时申请）验证锁等待
   - 不同系列并发申请（meeting_gamma 和 weli_gamma 同时申请）验证不阻塞
   - 锁持有时间监控（确保 < 100ms）