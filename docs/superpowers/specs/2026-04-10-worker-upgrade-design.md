# Worker 升级管理功能设计文档

**文档编号**: 2026-04-10-worker-upgrade-design  
**创建日期**: 2026-04-10  
**作者**: Claude Code  

---

## 一、需求概述

### 1.1 背景

企业级后台管理系统的执行机（Worker）需要版本升级管理功能，支持：
- 平台批量下发升级指令
- Worker 手动触发升级
- 升级状态追踪和队列管理

### 1.2 核心功能

| 功能 | 说明 |
|------|------|
| 版本配置管理 | 管理 Windows/Mac 两个平台的最新版本和安装包地址 |
| 批量升级 | 按 namespace + device_type 组合筛选，批量下发升级指令 |
| 延迟升级队列 | 使用中的机器释放后自动触发升级 |
| Worker 手动升级 | Worker 调用接口获取版本并手动触发升级 |
| 状态管理 | 新增 upgrading 状态，升级中不可被申请 |

---

## 二、数据库设计

### 2.1 WorkerUpgradeConfig 表（版本配置）

存储各平台最新版本信息。

```python
class WorkerUpgradeConfig(BaseModel):
    """Worker 升级配置表"""
    __tablename__ = "worker_upgrade_config"

    device_type = Column(String(20), nullable=False, unique=True, comment="设备类型: windows/mac")
    version = Column(String(32), nullable=False, comment="目标版本号(时间戳格式)")
    download_url = Column(String(512), nullable=False, comment="安装包下载地址")
    note = Column(Text, nullable=True, comment="备注")
```

**初始数据**:
- Windows 配置（device_type=windows）
- Mac 配置（device_type=mac）

### 2.2 WorkerUpgradeQueue 表（升级队列）

记录等待升级的机器（延迟升级机制）。

```python
class WorkerUpgradeQueue(BaseModel):
    """Worker 升级队列"""
    __tablename__ = "worker_upgrade_queue"

    machine_id = Column(String(36), nullable=False, index=True, comment="机器ID")
    target_version = Column(String(32), nullable=False, comment="目标版本号")
    status = Column(String(20), nullable=False, default="waiting", comment="状态: waiting/completed")
    device_type = Column(String(20), nullable=False, comment="设备类型")
    namespace = Column(String(64), nullable=False, comment="机器分类")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="入队时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
```

### 2.3 EnvMachine 表状态扩展

在 STATUS_DISPLAY 中新增：

```python
STATUS_DISPLAY = {
    "online": "在线",
    "using": "使用中",
    "offline": "离线",
    "upgrading": "升级中",  # 新增
}
```

---

## 三、后端 API 设计

### 3.1 Worker 获取升级信息

```
GET /api/core/env/get_worker_upgrade
```

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| device_type | string | 是 | 设备类型: windows/mac |

**响应示例**:
```json
{
  "version": "20260410150000",
  "download_url": "http://192.168.0.102:8000/downloads/win-worker.exe"
}
```

---

### 3.2 Worker 手动触发升级

```
POST /api/core/env/start_upgrade
```

**请求参数**:
```json
{
  "machine_id": "uuid-string",
  "version": "20260410150000"
}
```

**响应示例**:
```json
{
  "status": "success",
  "message": "状态已更新为升级中"
}
```

**逻辑**:
1. 验证 machine_id 存在且状态为 online
2. 将状态置为 upgrading
3. 更新 Redis 缓存（标记不可申请）
4. 返回成功响应

---

### 3.3 批量升级（平台下发）

```
POST /api/core/env/batch_upgrade
```

**请求参数**:
```json
{
  "machine_ids": ["uuid1", "uuid2"],  // 可选，指定机器ID列表
  "namespace": "meeting_gamma",       // 可选，默认全部（与 machine_ids 互斥）
  "device_type": "windows"            // 可选，默认全部（与 machine_ids 互斥）
}
```

**响应示例（成功）**:
```json
{
  "status": "success",
  "data": {
    "upgraded_count": 5,
    "waiting_count": 2,
    "skipped_count": 3,
    "failed_count": 0,
    "details": [
      {
        "machine_id": "xxx",
        "ip": "10.173.94.49",
        "status": "upgraded",
        "message": "升级指令已下发"
      },
      {
        "machine_id": "yyy",
        "ip": "10.173.94.50",
        "status": "waiting",
        "message": "机器使用中，已加入升级队列"
      },
      {
        "machine_id": "zzz",
        "ip": "10.173.94.51",
        "status": "failed",
        "message": "Worker 响应超时，升级指令下发失败"
      }
    ]
  }
}
```

**错误处理**:
- HTTP 状态码：200（部分成功也返回 200，通过响应体中的 failed_count 和 details 区分）
- 调用 Worker 超时（10秒）或响应错误：记录日志，该机器标记为 failed
- 失败机器保持原有状态（不置为 upgrading），可在 details 中查看具体失败原因
- 前端根据 failed_count > 0 弹出警告提示

**逻辑**:
1. 获取对应 device_type 的版本配置
2. 查询符合条件的机器（machine_ids 或 namespace + device_type 筛选）
3. 过滤条件：
   - status=online 且 version < target_version → 直接升级
   - status=using 且 version < target_version → 加入队列
   - status=offline/upgrading 或 version >= target_version → 跳过
4. 对 online 机器：调用 Worker 升级接口（详见 5.5 Worker 升级接口契约）
5. 调用成功后状态置为 upgrading
6. 调用失败：记录日志，该机器在 details 中标记为 failed

---

### 3.4 升级配置管理

```
GET    /api/core/env/upgrade_config          # 获取配置列表
PUT    /api/core/env/upgrade_config/{id}     # 更新配置
```

**GET 响应示例**:
```json
{
  "items": [
    {
      "id": "uuid-1",
      "device_type": "windows",
      "version": "20260410150000",
      "download_url": "http://192.168.0.102:8000/downloads/win-worker.exe",
      "note": "v2.1.0 正式版"
    },
    {
      "id": "uuid-2",
      "device_type": "mac",
      "version": "20260410150000",
      "download_url": "http://192.168.0.102:8000/downloads/mac-worker.dmg",
      "note": "v2.1.0 正式版"
    }
  ],
  "total": 2
}
```

---

### 3.5 升级队列查询

```
GET /api/core/env/upgrade_queue
```

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| namespace | string | 否 | 筛选 namespace |
| status | string | 否 | 筛选状态: waiting/completed |

**响应示例**:
```json
{
  "items": [
    {
      "id": "queue-uuid",
      "machine_id": "xxx",
      "ip": "10.173.94.51",
      "device_type": "mac",
      "target_version": "20260410150000",
      "status": "waiting",
      "created_at": "2026-04-10T14:30:00"
    }
  ],
  "total": 1
}
```

---

### 3.6 升级队列移除

```
DELETE /api/core/env/upgrade_queue/{queue_id}
```

**逻辑**:
1. 验证队列项存在且状态为 waiting
2. 删除队列项
3. 返回成功响应

---

### 3.7 升级预览接口

```
GET /api/core/env/upgrade_preview
```

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| namespace | string | 否 | 设备类别筛选 |
| device_type | string | 否 | 设备类型筛选 |

**响应示例**:
```json
{
  "upgradable_count": 5,
  "waiting_count": 2,
  "latest_count": 3,
  "offline_count": 1,
  "machines": [
    {
      "id": "xxx",
      "ip": "10.173.94.49",
      "device_type": "windows",
      "version": "20260405120000",
      "status": "online",
      "upgrade_status": "待升级"
    }
  ]
}
```

---

## 四、前端页面设计

### 4.1 升级管理页面

**路由路径**: `/env-machine/upgrade`

**页面布局**: 上下分区

#### 4.1.1 版本配置区

- Windows 配置卡片
  - 目标版本（输入框）
  - 下载地址（输入框）
  - 备注（输入框）
  - 保存配置按钮

- Mac 配置卡片
  - 目标版本（输入框）
  - 下载地址（输入框）
  - 备注（输入框）
  - 保存配置按钮

#### 4.1.2 批量升级区

**筛选条件**:
- 设备类别（下拉选择）
  - 全部（默认）
  - 集成验证 (meeting_gamma)
  - APP (meeting_app)
  - 音视频 (meeting_av)
  - 公共设备 (meeting_public)
- 设备类型（下拉选择）
  - 全部（默认）
  - Windows
  - Mac
- 查询预览按钮

**统计信息**:
- 可升级: X台
- 使用中(待队列): X台
- 已最新: X台
- 离线: X台

**机器列表预览表格**:
| 列 | 说明 |
|------|------|
| 全选checkbox | 表头全选，每行可勾选 |
| IP地址 | 显示机器IP |
| 设备类型 | Windows/Mac |
| 当前版本 | 时间戳格式 |
| 状态 | 在线/使用中/离线/升级中 |
| 升级状态 | 待升级/已最新/待队列/离线/升级中 |

**操作按钮**:
- 批量升级选中的机器 (显示勾选数量)
- 重置筛选

**确认弹窗**:
- 显示立即升级数量和使用中待队列数量
- 提示升级期间机器不可用
- 取消/确认升级按钮

#### 4.1.3 升级队列区

**显示**: 等待数量标签

**表格列**:
| 列 | 说明 |
|------|------|
| IP地址 | 机器IP |
| 设备类型 | Windows/Mac |
| 目标版本 | 升级目标版本 |
| 入队时间 | 加入队列时间 |
| 状态 | waiting |
| 操作 | 移除队列 |

### 4.2 设备管理页面改动（标准页面）

在表格操作列新增"升级"按钮：

**显示条件**:
- 状态为 online
- 当前版本低于目标版本

**点击逻辑**:
- 弹出确认弹窗
- 确认后调用 POST /batch_upgrade，传入 machine_ids 参数（单台机器）

---

## 五、核心流程设计

### 5.1 Worker 升级完整流程

```
触发方式一：平台批量下发升级
──────────────────────────────────────────────────────────
平台升级管理页面 → 点击批量升级 → POST /batch_upgrade
                                    ↓
                    查询 online 状态机器，调用 Worker 升级接口
                                    ↓
                    将机器状态置为 upgrading

触发方式二：Worker 手动触发升级
──────────────────────────────────────────────────────────
Worker 获取版本 → GET /get_worker_upgrade → 返回版本信息
                                    ↓
                    Worker 决定升级 → POST /start_upgrade
                                    ↓
                    平台将机器状态置为 upgrading

升级执行
──────────────────────────────────────────────────────────
Worker 收到升级指令 → 下载安装包 → 执行升级 → 重启注册
                                    ↓
                    POST /register → 状态恢复为 online

延迟升级机制
──────────────────────────────────────────────────────────
批量升级时遇到 using 状态机器：
                                    ↓
                    加入 WorkerUpgradeQueue (status=waiting)
                                    ↓
                    机器释放时 (POST /release)
                                    ↓
                    检查队列 → 发送升级指令 → 状态置为 upgrading
```

### 5.2 机器申请逻辑改动

**文件**: `backend-fastapi/core/env_machine/pool_manager.py`

**改动**: 在 `allocate_machines` 方法中增加过滤

```python
# 从缓存获取机器时，排除 upgrading 状态
if machine.status == "upgrading":
    continue  # 跳过升级中的机器
```

### 5.3 释放机器时触发延迟升级

**文件**: `backend-fastapi/core/env_machine/pool_manager.py`

**改动**: 在 `release_machine` 方法中新增

```python
async def release_machine(db, machine_id, namespace):
    # ... 现有释放逻辑 ...
    
    # 检查升级队列
    queue_item = await WorkerUpgradeQueueService.get_waiting_by_machine_id(db, machine_id)
    if queue_item:
        # 发送升级指令
        success = await send_upgrade_to_worker(machine, queue_item.target_version)
        if success:
            # 更新状态
            machine.status = "upgrading"
            # 更新队列状态
            queue_item.status = "completed"
            queue_item.completed_at = datetime.now()
        # 发送失败时保持 online 状态，等待定时任务处理
```

### 5.4 定时任务处理超时机器

**改动**: 在现有定时任务中新增

```python
# upgrading 状态超时也置为 offline
if machine.status == "upgrading" and is_timeout(machine.sync_time):
    machine.status = "offline"
```

### 5.5 Worker 升级接口契约

平台调用 Worker 的升级接口时，需遵循以下契约：

**接口地址**: `http://{ip}:{port}/worker/upgrade`

**请求方式**: POST

**请求体格式**:
```json
{
  "version": "20260410150000",
  "download_url": "http://192.168.0.102:8000/downloads/win-worker.exe"
}
```

**响应体格式**:
```json
{
  "status": "upgrading",
  "message": "Worker 正在升级，预计 30 秒后恢复",
  "current_version": "20260405120000"
}
```

**超时设置**: 10秒（平台调用 Worker 的 HTTP 请求超时时间）

**错误处理**:
- 超时或网络错误：平台记录日志，该机器标记为 failed
- Worker 返回非 200 状态码：平台记录日志，该机器标记为 failed
- Worker 返回 status != "upgrading"：视为异常响应，记录日志

**Worker 实现要求**:
1. 收到请求后立即响应（不等待升级完成）
2. 异步执行升级流程（下载、安装、重启）
3. 升级完成后调用平台注册接口恢复状态

### 5.6 升级队列清理策略

**清理规则**:
- completed 状态的队列项：保留 7 天后自动清理
- waiting 状态超过 24 小时：标记为 failed 并清理（机器可能已离线）

**实现方式**: 在定时任务中新增队列清理逻辑

```python
# 清理 7 天前的 completed 记录
await WorkerUpgradeQueueService.delete_completed_before(db, days=7)

# 清理超时的 waiting 记录
timeout_items = await WorkerUpgradeQueueService.get_waiting_timeout(db, hours=24)
for item in timeout_items:
    item.status = "failed"
    await db.commit()
```

---

## 六、文件清单

### 6.1 后端新增文件

| 文件 | 说明 |
|------|------|
| `core/env_machine/upgrade_model.py` | WorkerUpgradeConfig、WorkerUpgradeQueue 模型 |
| `core/env_machine/upgrade_schema.py` | 升级相关 Schema 定义 |
| `core/env_machine/upgrade_service.py` | 升级服务层逻辑 |
| `core/env_machine/upgrade_api.py` | 升级相关 API 路由 |

### 6.2 后端修改文件

| 文件 | 改动 |
|------|------|
| `core/env_machine/model.py` | 新增 upgrading 状态 |
| `core/env_machine/schema.py` | 新增升级状态显示 |
| `core/env_machine/api.py` | 注册路由导入升级路由 |
| `core/env_machine/pool_manager.py` | 申请/释放逻辑改动 |
| `core/router.py` | 注册升级路由 |
| `alembic/versions/xxx_add_upgrade_tables.py` | 数据库迁移脚本 |

### 6.3 前端新增文件

| 文件 | 说明 |
|------|------|
| `apps/web-ele/src/views/env-machine/upgrade.vue` | 升级管理页面 |
| `apps/web-ele/src/api/core/env-machine-upgrade.ts` | 升级相关 API 接口 |
| `apps/web-ele/src/router/routes/modules/env-machine-upgrade.ts` | 升级管理路由配置 |

### 6.4 前端修改文件

| 文件 | 改动 |
|------|------|
| `apps/web-ele/src/views/env-machine/index.vue` | 新增升级按钮 |
| `apps/web-ele/src/views/env-machine/types.ts` | 新增 upgrading 状态显示 |

---

## 七、实现优先级

1. **P0 - 核心功能**
   - 数据库表创建和迁移
   - Worker 获取升级信息接口 (GET /get_worker_upgrade)
   - Worker 手动触发升级接口 (POST /start_upgrade)
   - 批量升级接口 (POST /batch_upgrade)
   - 升级配置管理接口
   - 申请/释放逻辑改动

2. **P1 - 前端页面**
   - 升级管理页面（版本配置区 + 批量升级区）
   - 设备管理页面升级按钮

3. **P2 - 辅助功能**
   - 升级队列查询/移除接口
   - 升级队列区显示
   - 升级预览接口

---

## 八、验收标准

1. Worker 可通过 GET /get_worker_upgrade 获取最新版本信息
2. Worker 可通过 POST /start_upgrade 手动触发升级
3. 平台可批量下发升级指令，online 机器立即升级
4. using 机器释放后自动触发升级（延迟升级队列）
5. upgrading 状态机器不可被申请使用
6. 升级完成后机器注册，状态恢复为 online
7. 前端升级管理页面可配置版本、批量升级、查看队列
8. 设备管理页面可单机升级