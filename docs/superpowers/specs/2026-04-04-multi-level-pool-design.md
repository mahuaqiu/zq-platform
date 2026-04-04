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

---

## 详细设计

### 文件修改清单

| 文件 | 修改内容 |
|------|---------|
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