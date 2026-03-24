# 执行机管理模块设计文档

## 概述

执行机管理模块用于管理自动化测试执行机的注册、申请、释放和状态监控。支持多命名空间隔离、多设备类型（windows/mac/android/ios）、Redis 缓存加速和分布式锁保证并发安全。

---

## 一、数据库模型

### 表名: `env_machine`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | String(21) | 是 | 主键 (NanoId) |
| namespace | String(64) | 是 | 机器分类，如 meeting_xxx / manual / public |
| ip | String(45) | 是 | 机器 IP（支持 IPv6） |
| port | String(10) | 是 | 机器端口 |
| mark | String(255) | 否 | 机器标签，多个用逗号分隔，如 "windows,web" |
| device_type | String(20) | 是 | 机器类型：windows / mac / android / ios |
| device_sn | String(64) | 否 | 设备 SN（移动端必填） |
| available | Boolean | 是 | 是否启用，默认 False |
| status | String(20) | 是 | 状态：online / using / offline，默认 offline |
| note | Text | 否 | 备注 |
| sync_time | DateTime | 是 | 同步时间 |
| extra_message | JSON | 否 | 扩展信息，按标签存储 |
| version | String(32) | 否 | 机器版本 |
| last_keepusing_time | DateTime | 否 | 最后保持使用时间 |

### 继承自 BaseModel 的字段
- sort: Integer, 排序
- is_deleted: Boolean, 软删除标记
- sys_create_datetime: DateTime, 创建时间
- sys_update_datetime: DateTime, 更新时间
- sys_creator_id: String(21), 创建人ID
- sys_modifier_id: String(21), 修改人ID

### 索引
- `(namespace, ip, device_type, device_sn)`: 注册查询复合索引
- `status`: 状态筛选索引
- `sync_time`: 离线检测索引

---

## 二、Redis 缓存设计

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

### 2. 分布式锁

```
Key: env_lock:{namespace}
Type: String
Value: UUID（锁持有者标识）
TTL: 10秒
```

**锁获取规则**：
- 申请 `{namespace}` 机器时，同时锁住 `env_lock:{namespace}` 和 `env_lock:public`
- 按固定顺序获取锁：先 namespace，再 public（避免死锁）
- 带超时重试：最多等待 3 秒，每 100ms 重试一次
- 超时返回：`{"status": "fail", "result": "system busy, please retry"}`

---

## 三、API 接口设计

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
{"status": "success"}
```

**逻辑**：
1. 遍历 devices 字典
2. 对于每个 device_type：
   - windows/mac：device_sn 为 null，每个 IP 插入一条记录
   - android/ios：根据 device_sn 列表，每个 sn 插入一条记录
3. 查询条件：`namespace + ip + device_type + device_sn`
4. 不存在则插入（状态 online，启用 False）
5. 存在则更新 sync_time、status=online
6. 同步更新 Redis 缓存

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
```

**失败响应**:
```json
{"status": "fail", "result": "env not enough"}
```
或
```json
{"status": "fail", "result": "system busy, please retry"}
```

**逻辑**：
1. 获取分布式锁（namespace + public），带 3 秒超时重试
2. 从 Redis 获取候选机器（namespace 池 + public 池）
3. 筛选可用机器：status=online + available=true + 标签匹配
4. 分配机器：
   - 优先从 namespace 池分配
   - 不够时从 public 池补充
   - 同 IP 的 windows/mac 整体占用
   - 移动端按 device_sn 独立占用
5. 记录已占用的 IP/SN，避免重复分配
6. 分配失败：不修改任何状态，返回 "env not enough"
7. 分配成功：
   - 更新数据库状态为 using
   - 更新 Redis 缓存状态
   - 创建 1 分钟后执行的延迟释放任务
   - 合并 extra_message 中对应标签的信息返回
8. 释放分布式锁

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
{"status": "success"}
```

**逻辑**：
1. 更新 last_keepusing_time 为当前时间
2. 延迟对应的释放任务执行时间（+1 分钟）

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
{"status": "success"}
```

**逻辑**：
1. 取消延迟释放任务
2. 更新数据库状态为 online（如果当前是 offline 则不变）
3. 同步更新 Redis 缓存

---

## 四、定时任务设计

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
1. 更新数据库状态为 online
2. 同步 Redis 缓存状态

### 2. 离线检测任务（周期任务）

**执行频率**: 每 2 分钟

**逻辑**:
```python
@scheduler.scheduled_job('interval', minutes=2)
async def check_offline_job():
    # 查询 sync_time 超过 10 分钟的机器
    threshold = datetime.now() - timedelta(minutes=10)
    machines = await db.execute(
        select(EnvMachine).where(
            EnvMachine.sync_time < threshold,
            EnvMachine.status != 'offline',
            EnvMachine.is_deleted == False
        )
    )

    for machine in machines:
        # 取消延迟释放任务（如果有）
        try:
            scheduler.remove_job(f"release_{machine.id}")
        except:
            pass

        # 更新状态
        machine.status = 'offline'

    await db.commit()

    # 同步 Redis 缓存
    await sync_cache_for_machines(machines)
```

---

## 五、机器池维护逻辑

### 1. 启动时加载

```python
async def load_machine_pool():
    """服务启动时加载机器池到 Redis"""
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

### 2. 注册时同步

注册接口更新机器状态后，同步更新 Redis 缓存。

### 3. 申请时更新

分配成功后，从缓存中移除或更新状态。

### 4. 释放时更新

释放后，将机器重新加入缓存或更新状态。

### 5. 手动启用/停用

管理页面修改 available 字段时，同步更新缓存：
- 启用且 online：加入缓存
- 停用：从缓存移除

### 6. special namespaces

- `manual`: 不加入机器池缓存，不可申请
- `public`: 当 namespace 机器不够时，可借用 public 机器

---

## 六、extra_message 格式

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

---

## 七、模块文件结构

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

## 八、操作流程汇总

| 场景 | 数据库操作 | Redis 操作 | 定时任务 |
|------|-----------|-----------|---------|
| 服务启动 | - | 加载 online+启用 的机器到缓存 | 启动离线检测任务 |
| 注册 /env/register | 插入/更新机器记录 | 同步缓存状态 | - |
| 申请 /application | 更新状态为 using | 更新缓存状态 | 创建延迟释放任务 |
| 保持使用 /keepusing | 更新 last_keepusing_time | - | 延迟释放任务 1 分钟 |
| 释放 /release | 更新状态为 online | 更新缓存状态 | 取消延迟释放任务 |
| 延迟释放触发 | 更新状态为 online | 更新缓存状态 | 任务执行完毕 |
| 离线检测 | 更新状态为 offline | 更新缓存状态 | 每 2 分钟执行 |
| 手动启用/停用 | 更新 available | 加入/移除缓存 | - |