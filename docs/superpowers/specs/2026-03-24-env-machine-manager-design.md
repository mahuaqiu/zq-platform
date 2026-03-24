# 执行机管理模块设计文档

## 概述

执行机管理模块用于管理自动化测试执行机的注册、申请、释放和状态监控。支持多命名空间隔离、多设备类型（windows/mac/android/ios）、Redis 缓存加速和分布式锁保证并发安全。

---

## 一、数据库模型

### 表名: `env_machine`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | String(21) | 是 | NanoId | 主键 |
| namespace | String(64) | 是 | - | 机器分类，如 meeting_xxx / manual / public |
| ip | String(45) | 是 | - | 机器 IP（支持 IPv6） |
| port | String(10) | 是 | - | 机器端口 |
| mark | String(255) | 否 | - | 机器标签，多个用逗号分隔，如 "windows,web" |
| device_type | String(20) | 是 | - | 机器类型：windows / mac / android / ios |
| device_sn | String(64) | 否 | - | 设备 SN（移动端必填） |
| available | Boolean | 是 | False | 是否启用 |
| status | String(20) | 是 | online | 状态：online / using / offline |
| note | Text | 否 | - | 备注 |
| sync_time | DateTime | 是 | now | 同步时间 |
| extra_message | JSON | 否 | - | 扩展信息，按标签存储 |
| version | String(32) | 否 | - | 机器版本 |
| last_keepusing_time | DateTime | 否 | - | 最后保持使用时间 |

### 继承自 BaseModel 的字段
- sort: Integer, 排序
- is_deleted: Boolean, 软删除标记
- sys_create_datetime: DateTime, 创建时间
- sys_update_datetime: DateTime, 更新时间
- sys_creator_id: String(21), 创建人ID
- sys_modifier_id: String(21), 修改人ID

### 索引
- `(namespace, ip, device_type, device_sn)`: 注册查询复合索引（唯一约束）
- `status`: 状态筛选索引
- `sync_time`: 离线检测索引

---

## 二、机器状态流转

```
                    注册/心跳
    ┌─────────────────────────────────┐
    │                                 ▼
┌─────────┐  申请成功  ┌─────────┐
│ online  │ ────────▶ │  using  │
└─────────┘           └─────────┘
    ▲                     │
    │                     │ 释放 / 超时未 keepusing
    │  离线检测           │
    │  (10分钟无心跳)      ▼
┌──────────┐          ┌─────────┐
│ offline  │ ◀─────── │  using  │
└──────────┘  离线检测 └─────────┘
    │
    │ 注册/心跳
    ▼
┌─────────┐
│ online  │
└─────────┘
```

**状态说明**：
- `online`: 在线可用，可被申请
- `using`: 使用中，不可被申请
- `offline`: 离线，不可被申请

---

## 三、Redis 缓存设计

### 1. 机器池缓存

```
Key: env_pool:{namespace}
Type: Hash
Field: machine_id
Value: JSON {
    "id": "xxx",
    "ip": "192.168.0.1",
    "port": "8088",
    "mark": "windows,web",
    "device_type": "windows",
    "device_sn": null,
    "status": "online",
    "available": true,
    "extra_message": {"windows": {...}, "web": {...}}
}
```

**说明**：
- 每个 namespace 一个 Hash
- `manual` namespace 不加入缓存
- 只缓存 `status=online` 且 `available=true` 的机器
- 缓存无 TTL，通过业务逻辑保证一致性

### 2. 分布式锁

```
Key: env_lock:{namespace}
Type: String
Value: UUID（锁持有者标识）
TTL: 10秒
```

**锁获取规则**：
- 申请 `{namespace}` 机器时，需要同时锁住 `env_lock:{namespace}` 和 `env_lock:public`
- 如果申请的 namespace 就是 `public`，则只需锁住 `env_lock:public`
- 按固定顺序获取锁：先按字母序排序后，再获取（避免死锁）
- 带超时重试：最多等待 3 秒，每 100ms 重试一次
- 超时返回错误，客户端可重试

**示例**：
```
申请 meeting_gamma 命名空间的机器：
1. 先获取 env_lock:meeting_gamma（m 排在 p 前面）
2. 再获取 env_lock:public

申请 alpha 命名空间的机器：
1. 先获取 env_lock:alpha（a 排在 p 前面）
2. 再获取 env_lock:public
```

---

## 四、统一响应格式

所有接口使用统一的响应格式：

**成功响应**:
```json
{
    "status": "success",
    "data": { ... }
}
```

**失败响应**:
```json
{
    "status": "fail",
    "result": "错误描述"
}
```

**错误类型**：
- `env not enough`: 机器数量不足
- `system busy, please retry`: 系统繁忙，请重试
- `invalid request`: 请求参数无效
- `machine not found`: 机器不存在

---

## 五、API 接口设计

### 1. 注册接口

```
POST /env/register
```

**请求**:
```json
{
    "ip": "192.168.0.1",
    "port": "8088",
    "namespace": "meeting_gamma",
    "version": "202603.4",
    "devices": {
        "windows": [],
        "android": ["sn1", "sn2"],
        "ios": ["sn3"]
    }
}
```

**响应**:
```json
{
    "status": "success",
    "data": null
}
```

**逻辑**：
1. 遍历 devices 字典
2. 对于每个 device_type：
   - windows/mac：device_sn 为 null，每个 IP 插入一条记录
   - android/ios：根据 device_sn 列表，每个 sn 插入一条记录
3. 查询条件：`namespace + ip + device_type + device_sn`
4. 不存在则插入：
   - 状态设为 online（机器已在线）
   - available 设为 False（需管理员手动启用，防止未配置账号的机器被申请）
5. 存在则更新 sync_time、status=online
6. 同步更新 Redis 缓存（如果该机器 available=true 且 status=online）

---

### 2. 申请接口

```
POST /env/{namespace}/application
```

**请求**:
```json
{
    "userA": "windows",
    "userB": "web"
}
```

**成功响应**:
```json
{
    "status": "success",
    "data": {
        "userA": {
            "id": "xxx",
            "ip": "10.173.94.49",
            "port": "8088",
            "device_type": "windows",
            "device_sn": null,
            "account": "xxx",
            "name": "自动化001",
            "password": "123456",
            "sip": "125445"
        },
        "userB": {...}
    }
}
```

**失败响应**:
```json
{
    "status": "fail",
    "result": "env not enough"
}
```

**逻辑**：
1. 参数校验：请求体不能为空
2. 获取分布式锁，带 3 秒超时重试
3. 从 Redis 获取候选机器（namespace 池 + public 池）
4. 筛选可用机器：status=online + available=true + 标签匹配
5. 分配机器：
   - 优先从 namespace 池分配
   - 不够时从 public 池补充
   - windows/mac 按 IP 占用（同 IP 不会同时存在 windows 和 mac）
   - 移动端按 device_sn 独立占用
6. 记录已占用的 IP/SN，避免重复分配
7. 分配失败：不修改任何状态，返回错误
8. 分配成功：
   - 更新数据库状态为 using
   - 更新 last_keepusing_time
   - 更新 Redis 缓存（移除或更新状态）
   - 创建 1 分钟后执行的延迟释放任务
   - 合并 extra_message 中对应标签的信息返回
9. 释放分布式锁

**标签匹配规则**：
- 申请标签需完全匹配机器 mark 字段中的某一个标签（按逗号分隔）
- 例如：机器 `mark="windows,web"`，申请标签 `"windows"` 可匹配，`"win"` 不可匹配

**响应字段合并规则**：
- 基础字段：id, ip, port, device_type, device_sn
- 扩展字段：从 `extra_message[申请标签]` 中取所有字段合并到响应
- 例如：申请标签 `"windows"`，则合并 `extra_message["windows"]` 中的 account, name, password, sip 等字段

**边界条件**：
- 请求体为空：返回 `{"status": "fail", "result": "invalid request"}`
- 标签不存在匹配机器：按机器不足处理
- 同一个 user key 重复：后面覆盖前面（正常不应出现）

---

### 3. 保持使用接口

```
POST /env/keepusing
```

**请求**:
```json
[{"id": "xxx"}, {"id": "yyy"}]
```

**响应**:
```json
{
    "status": "success",
    "data": null
}
```

**逻辑**：
1. 遍历请求中的机器 ID
2. 对于每台机器：
   - 更新 last_keepusing_time 为当前时间
   - 延迟对应的释放任务执行时间（+1 分钟）
3. 忽略不存在或非 using 状态的机器（静默处理）

**边界条件**：
- 机器 ID 不存在：忽略
- 机器状态不是 using：忽略（可能已被释放或离线）
- 释放任务不存在：忽略（可能已执行或服务重启后丢失）

---

### 4. 释放接口

```
POST /env/release
```

**请求**:
```json
[{"id": "xxx"}, {"id": "yyy"}]
```

**响应**:
```json
{
    "status": "success",
    "data": null
}
```

**逻辑**：
1. 遍历请求中的机器 ID
2. 对于每台机器：
   - 取消延迟释放任务（如果存在）
   - 如果状态是 using，更新为 online
   - 如果状态是 offline，不变
   - 如果状态是 online，不变
   - 同步更新 Redis 缓存（如果 available=true，重新加入缓存）
3. 忽略不存在的机器

**边界条件**：
- 机器 ID 不存在：忽略
- 重复释放：幂等处理，不报错
- 释放任务不存在：忽略

---

## 六、定时任务设计

### 1. 延迟释放任务（独立任务）

每台占用的机器创建独立的延迟任务。

**任务 ID**: `release_{machine_id}`

**申请时创建**:
```python
scheduler.add_job(
    release_machine_job,
    trigger='date',
    run_date=datetime.now() + timedelta(minutes=1),
    id=f"release_{machine_id}",
    args=[machine_id]
)
```

**keepusing 时延迟**:
```python
scheduler.modify_job(
    f"release_{machine_id}",
    next_run_time=datetime.now() + timedelta(minutes=1)
)
```

**释放时取消**:
```python
scheduler.remove_job(f"release_{machine_id}")
```

**任务执行逻辑**:
1. 检查机器当前状态
2. 如果状态是 using，更新为 online
3. 如果状态是 offline，不变
4. 同步 Redis 缓存状态
5. 任务执行完毕自动删除

### 2. 离线检测任务（周期任务）

**执行频率**: 每 2 分钟

**逻辑**:
```python
@scheduler.scheduled_job('interval', minutes=2)
async def check_offline_job():
    threshold = datetime.now() - timedelta(minutes=10)

    # 查询 sync_time 超过 10 分钟的机器
    machines = await db.execute(
        select(EnvMachine).where(
            EnvMachine.sync_time < threshold,
            EnvMachine.status.in_(['online', 'using']),
            EnvMachine.is_deleted == False
        )
    )

    for machine in machines:
        # 取消延迟释放任务（如果有）
        try:
            scheduler.remove_job(f"release_{machine.id}")
        except JobLookupError:
            logger.debug(f"Job not found: release_{machine.id}")

        # 更新状态
        machine.status = 'offline'

    await db.commit()

    # 同步 Redis 缓存
    await sync_cache_for_machines(machines)
```

---

## 七、服务启动与恢复

### 启动流程

```python
async def on_startup():
    # 1. 重置异常状态
    # 将所有 using 状态的机器重置为 online（服务重启后定时任务丢失）
    await db.execute(
        update(EnvMachine)
        .where(EnvMachine.status == 'using')
        .values(status='online')
    )
    await db.commit()

    # 2. 加载机器池到 Redis
    await load_machine_pool()

    # 3. 启动定时任务
    scheduler.start()
    scheduler.add_job(check_offline_job, 'interval', minutes=2)
```

### 加载机器池

```python
async def load_machine_pool():
    """服务启动时加载机器池到 Redis"""
    # 清空现有缓存
    await cache.delete_pattern("env_pool:*")

    # 查询所有 online + 启用的机器
    machines = await db.execute(
        select(EnvMachine).where(
            EnvMachine.status == 'online',
            EnvMachine.available == True,
            EnvMachine.is_deleted == False,
            EnvMachine.namespace != 'manual'
        )
    )

    for machine in machines:
        await cache.hset(
            f"env_pool:{machine.namespace}",
            machine.id,
            machine_to_json(machine)
        )
```

---

## 八、缓存与数据库一致性策略

### 策略：先数据库后缓存

1. **更新操作**：先更新数据库，再更新缓存
2. **缓存更新失败**：记录日志，不回滚数据库（允许短暂不一致）
3. **恢复机制**：
   - 服务重启时重新加载缓存
   - 离线检测任务会同步缓存状态
   - 注册接口会同步缓存状态

### 一致性保障点

| 操作 | 数据库 | 缓存 | 说明 |
|------|--------|------|------|
| 注册 | ✅ | ✅ | 同步更新 |
| 申请 | ✅ | ✅ | 同步更新 |
| 释放 | ✅ | ✅ | 同步更新 |
| 离线检测 | ✅ | ✅ | 同步更新 |
| keepusing | ✅ | - | 只更新数据库时间字段 |

---

## 九、机器池维护逻辑

### 1. 注册时同步

注册接口更新机器状态后，同步更新 Redis 缓存：
- 如果 available=true 且 status=online：加入缓存
- 否则：从缓存移除

### 2. 申请时更新

分配成功后，从缓存中移除或更新状态。

### 3. 释放时更新

释放后，如果 available=true，将机器重新加入缓存。

### 4. 手动启用/停用（管理接口，后续设计）

管理页面修改 available 字段时，同步更新缓存：
- 启用且 online：加入缓存
- 停用：从缓存移除

### 5. Special Namespaces

- `manual`: 不加入机器池缓存，不可申请
- `public`: 当 namespace 机器不够时，可借用 public 机器

---

## 十、extra_message 格式

统一使用按标签存储格式：

```json
{
    "windows": {
        "account": "xxx",
        "name": "自动化001",
        "password": "123456",
        "sip": "125445"
    },
    "web": {
        "account": "xxx",
        "name": "自动化002",
        "password": "654321",
        "sip": "125446"
    }
}
```

**申请返回时**：根据申请的标签，返回对应的扩展信息并合并到响应中。

**示例**：
- 申请标签 "windows"：返回 `extra_message["windows"]` 的内容合并到响应
- 申请标签 "web"：返回 `extra_message["web"]` 的内容合并到响应

---

## 十一、模块文件结构

```
core/env_machine/
├── __init__.py
├── model.py           # EnvMachine 数据模型
├── schema.py          # 请求/响应 Schema
├── service.py         # 基础 CRUD 操作
├── pool_manager.py    # 机器池管理（缓存、申请、释放）
├── lock_manager.py    # Redis 分布式锁
├── scheduler.py       # 定时任务管理
└── api.py             # 路由接口
```

---

## 十二、操作流程汇总

| 场景 | 数据库操作 | Redis 操作 | 定时任务 |
|------|-----------|-----------|---------|
| 服务启动 | 重置 using → online | 加载 online+启用 的机器到缓存 | 启动离线检测任务 |
| 注册 /env/register | 插入/更新机器记录 | 同步缓存状态 | - |
| 申请 /application | 更新状态为 using | 更新缓存状态 | 创建延迟释放任务 |
| 保持使用 /keepusing | 更新 last_keepusing_time | - | 延迟释放任务 1 分钟 |
| 释放 /release | 更新状态为 online | 更新缓存状态 | 取消延迟释放任务 |
| 延迟释放触发 | 更新状态为 online | 更新缓存状态 | 任务执行完毕 |
| 离线检测 | 更新状态为 offline | 更新缓存状态 | 每 2 分钟执行 |
| 手动启用/停用 | 更新 available | 加入/移除缓存 | - |

---

## 十三、IP 占用规则说明

**Windows/Mac**：
- 同一 IP 的机器要么是 windows 要么是 mac，不会同时存在
- 申请时按 IP 占用，该 IP 的机器不可再被申请

**Android/iOS**：
- 同一 IP 可能有多个移动端设备（不同 device_sn）
- 申请时按 device_sn 独立占用，不影响同 IP 的其他设备

---

## 十四、后续待设计

1. 管理接口：
   - 机器列表查询
   - 机器详情
   - 机器信息更新
   - 启用/停用
   - 删除

2. Namespace 管理：
   - 创建/删除 namespace
   - 权限控制

---

## 十五、部署说明

### 数据库迁移

模块实现完成后，需要执行以下数据库迁移命令：

```bash
# 进入后端目录
cd backend-fastapi

# 生成迁移文件（根据 model.py 自动生成）
alembic revision --autogenerate -m "add env_machine table"

# 执行迁移
alembic upgrade head
```

### 服务启动

服务启动时会自动执行以下初始化操作：

1. 重置所有 `using` 状态的机器为 `online`（服务重启后恢复）
2. 加载机器池到 Redis 缓存
3. 启动离线检测定时任务（每 2 分钟执行一次）