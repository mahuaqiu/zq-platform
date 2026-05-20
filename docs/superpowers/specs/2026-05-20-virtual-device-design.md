---
name: virtual-device-feature
description: 虚拟设备功能设计 - 用于性能测试场景的账号申请，无需真实 worker 连接
---

# 虚拟设备功能设计文档

## 背景

性能测试用例场景下，需要申请账号执行测试，但只调用 API 不需要连接真实 worker。现有设备管理系统依赖 worker 心跳注册，无法管理这类虚拟设备。

## 目标

- 支持创建虚拟设备，用于性能测试账号申请
- 虚拟设备无需真实 worker 连接，不参与离线检测
- 支持批量导入和批量删除虚拟设备
- 申请/释放流程与真实设备一致

## 设计方案

### 1. 数据库模型改动

**EnvMachine 模型新增字段**：

文件：`backend-fastapi/core/env_machine/model.py`

```python
# 是否为虚拟设备（虚拟设备不参与离线检测和重启重载）
is_virtual = Column(Boolean, nullable=False, default=False, comment="是否为虚拟设备")
```

**现有字段修改**：

```python
# port 字段改为 nullable=True（虚拟设备不需要端口）
port = Column(String(10), nullable=True, comment="机器端口")
```

**索引调整**：
- 新增索引：`ix_env_machine_is_virtual`（便于筛选虚拟设备）

**字段约束**：
- `ip` 字段唯一约束保持：`namespace + ip + device_type + device_sn`
- 虚拟设备 `device_sn` 为空（null），通过 `ip` 字段保证唯一性（如 `perf001`, `perf002`）
- **注意**：PostgreSQL 中 null 值不参与唯一约束比较，因此同一 namespace + device_type 下可以有多个 `device_sn=null` 的虚拟设备，只要 `ip` 不同即可

**to_cache_dict() 方法更新**：

文件：`backend-fastapi/core/env_machine/model.py` (约 line 110-131)

新增 `is_virtual` 字段到缓存字典：

```python
def to_cache_dict(self) -> dict:
    return {
        # ...existing fields...
        "is_virtual": self.is_virtual,  # 新增
    }
```

**数据库迁移**：

```bash
alembic revision --autogenerate -m "add is_virtual field and make port nullable for virtual devices"
alembic upgrade head
```

### 2. 后端 API 改动

#### 2.1 新增 API

**批量导入虚拟设备**：
- `POST /api/core/env/batch-import-virtual`
- 参数：Excel 文件
- 返回：`{ success_count: int, failed_items: [{row: int, reason: string}] }`

**批量删除设备**：
- `POST /api/core/env/batch-delete`
- 参数：`{ ids: [string] }`
- 返回：`{ success_count: int, failed_ids: [string] }`

**下载导入模板**：
- `GET /api/core/env/import-template`
- 返回：Excel 模板文件

#### 2.2 修改现有 API

**创建设备**：
- `POST /api/core/env` - 新增 `is_virtual` 参数，默认为 `true`
- 文件：`backend-fastapi/core/env_machine/schema.py`
- 修改 `EnvMachineCreateRequest`：
```python
class EnvMachineCreateRequest(BaseModel):
    """新增执行机请求 Schema"""
    namespace: str = Field(..., description="机器分类")
    device_type: str = Field(..., description="机器类型：windows/mac/ios/android")
    asset_number: str = Field(..., description="资产编号（必填）")
    ip: Optional[str] = Field(None, description="IP地址（Windows/Mac）")
    device_sn: Optional[str] = Field(None, description="设备SN（iOS/Android）")
    note: Optional[str] = Field(None, description="备注")
    is_virtual: bool = Field(default=True, description="是否为虚拟设备")  # 新增
```
- Worker 注册设备通过 `/register` 接口，`is_virtual=false`（默认值）

**设备列表查询**：
- `GET /api/core/env` - 返回数据包含 `is_virtual` 字段
- 文件：`backend-fastapi/core/env_machine/schema.py`
- 修改 `EnvMachineResponse`：新增 `is_virtual: bool = Field(default=False, description="是否为虚拟设备")`

**升级管理列表查询**：
- 文件：`backend-fastapi/core/env_machine/upgrade_service.py`
- 过滤 `is_virtual=false` 的设备 (lines 263, 386, 520)
- 升级 API 文件：`backend-fastapi/core/env_machine/upgrade_api.py`

**配置下发列表查询**：
- 文件：`backend-fastapi/core/config_template/service.py`
- 过滤 `is_virtual=false` 的设备 (lines 207, 457)

#### 2.3 Worker 注册保持现状

- Worker 注册上来的设备 `is_virtual=false`（默认值）
- 注册逻辑无需改动

### 3. 定时任务改动

#### 3.1 离线检测任务

文件：`backend-fastapi/core/env_machine/scheduler.py`

`check_offline_machines` 函数 (line 259-262)：

```python
stmt = select(EnvMachine).where(
    EnvMachine.sync_time < threshold,
    EnvMachine.status.in_(["online", "using"]),
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

同时修改 upgrading 状态超时查询 (line 268-271)：

```python
upgrade_stmt = select(EnvMachine).where(
    EnvMachine.sync_time < upgrade_threshold,
    EnvMachine.status == "upgrading",
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

#### 3.2 重启重载任务

文件：`backend-fastapi/core/env_machine/scheduler.py`

`reload_machine_status_after_restart` 函数 (line 529-531)：

```python
stmt = select(EnvMachine).where(
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

### 4. 前端页面改动

#### 4.1 TypeScript Interface 更新

文件：`web/apps/web-ele/src/api/core/env-machine.ts`

`EnvMachine` interface 新增字段：

```typescript
interface EnvMachine {
  // ...existing fields...
  is_virtual: boolean;  // 新增
}
```

#### 4.2 设备列表页面 (`list.vue`)

**新增 checkbox 选择列**：
- 表格左侧添加选择列（`type="selection"`）
- 支持单选、全选
- 选中后工具栏显示"批量删除"按钮

**新增批量导入功能**：
- 按钮位置：重置按钮右边
- 点击弹窗包含：
  - 下载模板按钮
  - 上传 Excel 区域（拖拽或点击上传）
  - 导入结果显示（成功数量、失败列表）

**操作列调整**：
- `is_virtual=true` 的设备：隐藏"日志"、"远程"按钮
- 只显示"编辑"、"删除"

#### 4.2 升级管理页面 (`upgrade.vue`)

- 后端已过滤虚拟设备，前端无需改动

#### 4.3 配置下发页面 (`config.vue`)

- 后端已过滤虚拟设备，前端无需改动

### 5. 导入模板设计

**模板字段**：

| 字段 | 必填 | 说明 |
|------|------|------|
| namespace | 是 | 机器分类，如 `meeting_virtual` |
| device_type | 是 | 设备类型：windows/mac/android/ios |
| asset_number | 是 | 资产编号 |
| ip | 是 | 虚拟标识，同一 namespace 下唯一，如 `perf001` |
| mark | 是 | 标签，如 `windows_perf`（必须符合标签格式规则） |
| extra_message | 是 | JSON 格式账号信息（必须包含 mark 对应的账号配置） |
| note | 否 | 备注 |

**验证规则**：

1. **mark 字段验证**：必须符合现有标签格式规则
   - 前缀必须是 `windows/web/android/ios/mac` 之一
   - 必须小写
   - 下划线后必须有内容

2. **extra_message 验证**：JSON 格式，必须包含 mark 对应的账号配置
   - 例如：`{"windows_perf": {"username": "test", "password": "xxx"}}`
   - 启用设备时验证规则与现有设备一致（`validateExtraMessageWithTag`）

**自动填充字段**：
- `port` = 空（null）
- `status` = `online`
- `is_virtual` = `true`
- `device_sn` = 空（null）

**Excel 导入配置**：

文件：`backend-fastapi/core/env_machine/service.py`

新增虚拟设备导入处理器，与现有 `_import_processor` 分开：

```python
VIRTUAL_EXCEL_COLUMNS = {
    "namespace": "机器分类",
    "device_type": "机器类型",
    "asset_number": "资产编号",
    "ip": "虚拟标识",
    "mark": "标签",
    "extra_message": "扩展信息(JSON)",
    "note": "备注",
}

@classmethod
def _virtual_import_processor(cls, row: Dict[str, Any]) -> Optional[EnvMachine]:
    """虚拟设备导入处理器"""
    # 验证必填字段
    namespace = row.get("namespace")
    device_type = row.get("device_type")
    asset_number = row.get("asset_number")
    ip = row.get("ip")
    mark = row.get("mark")
    extra_message_str = row.get("extra_message")

    if not all([namespace, device_type, asset_number, ip, mark, extra_message_str]):
        return None

    # 解析 extra_message JSON
    try:
        extra_message = json.loads(extra_message_str)
    except json.JSONDecodeError:
        return None

    return EnvMachine(
        namespace=str(namespace),
        device_type=str(device_type),
        asset_number=str(asset_number),
        ip=str(ip),
        port=None,  # 虚拟设备无端口
        device_sn=None,  # 虚拟设备无 SN
        mark=str(mark),
        available=False,  # 导入后默认不启用
        status="online",
        is_virtual=True,  # 标记为虚拟设备
        extra_message=extra_message,
        note=str(row.get("note")) if row.get("note") else None,
    )
```

### 6. 申请/释放流程

虚拟设备的申请和释放流程与真实设备一致，无需特殊处理：

**申请流程**：
1. 从 Redis 缓存中查找匹配标签的设备
2. `status` 变为 `using`
3. 返回 `extra_message` 中对应标签的账号信息
4. 创建延迟释放任务（1分钟后自动释放）
5. 从缓存移除

**保活机制**：
- 调用 `/keepusing` 延长使用时间
- 更新 `last_keepusing_time`

**释放流程**：
1. 调用 `/release`，`status` 恢复 `online`
2. 如果 `available=true`，重新加入缓存
3. 取消延迟释放任务

### 7. Redis 缓存处理

文件：`backend-fastapi/core/env_machine/pool_manager.py`

虚拟设备缓存逻辑与真实设备一致，`sync_machine_to_cache` 方法无需改动：

- `available=true` 且 `status=online` 时加入缓存
- 申请后从缓存移除
- 释放后重新加入缓存

缓存数据包含 `is_virtual` 字段（通过 `to_cache_dict()` 方法）。

### 8. 用户管理方式

- 通过 namespace 区分虚拟设备（如 `meeting_virtual`）
- 使用 namespace 筛选管理虚拟设备
- 不需要额外的 `is_virtual` 筛选按钮

### 9. Namespace 配置

虚拟设备使用的 namespace（如 `meeting_virtual`）需要添加到配置中：

**后端配置**：
文件：`backend-fastapi/env/dev.env`（及其他环境配置）

```ini
NAMESPACE_MAP={"meeting": "...", "meeting_virtual": "虚拟设备池", ...}
```

**前端配置**：
文件：`web/apps/web-ele/.env.development`

```ini
VITE_NAMESPACE_CONFIG={"meeting": "会议", "meeting_virtual": "会议虚拟设备", ...}
```

### 10. 批量删除实现

文件：`backend-fastapi/core/env_machine/api.py`

新增批量删除 API：

```python
@router.post("/batch-delete", summary="批量删除设备")
async def batch_delete_env_machines(
    data: EnvMachineBatchDeleteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    批量删除设备（支持虚拟和真实设备）
    
    - 软删除：设置 is_deleted=True
    - 从 Redis 缓存中移除
    """
    success_count = 0
    failed_ids = []
    
    for machine_id in data.ids:
        machine = await EnvMachineService.get_by_id(db, machine_id)
        if not machine:
            failed_ids.append(machine_id)
            continue
        
        namespace = machine.namespace
        await EnvMachineService.delete(db, machine_id)
        await EnvPoolManager.remove_machine_from_cache(machine_id, namespace)
        success_count += 1
    
    await db.commit()
    
    return {
        "success_count": success_count,
        "failed_ids": failed_ids
    }
```

Schema 定义：

```python
class EnvMachineBatchDeleteRequest(BaseModel):
    """批量删除请求 Schema"""
    ids: List[str] = Field(..., description="设备 ID 列表")
```

### 11. 批量导入实现

文件：`backend-fastapi/core/env_machine/api.py`

新增批量导入 API：

```python
@router.post("/batch-import-virtual", summary="批量导入虚拟设备")
async def batch_import_virtual_devices(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    批量导入虚拟设备
    
    - Excel 文件上传
    - 返回导入结果
    """
    content = await file.read()
    success_count, failed_items = await EnvMachineService.import_virtual_from_excel(db, content)
    await db.commit()
    
    return {
        "success_count": success_count,
        "failed_items": failed_items
    }
```

### 12. 导入模板下载

文件：`backend-fastapi/core/env_machine/api.py`

新增模板下载 API：

```python
@router.get("/import-template", summary="下载虚拟设备导入模板")
async def download_import_template():
    """下载虚拟设备导入 Excel 模板"""
    return await EnvMachineService.generate_virtual_import_template()
```

**模板生成实现**：

文件：`backend-fastapi/core/env_machine/service.py`

```python
@classmethod
async def generate_virtual_import_template(cls) -> BytesIO:
    """生成虚拟设备导入 Excel 模板"""
    import openpyxl
    from openpyxl.styles import Font, Alignment
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "虚拟设备导入模板"
    
    # 写入表头
    headers = list(cls.VIRTUAL_EXCEL_COLUMNS.values())
    ws.append(headers)
    
    # 设置表头样式
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    # 写入示例行
    ws.append([
        "meeting_virtual",  # namespace
        "windows",          # device_type
        "PERF-001",         # asset_number
        "perf001",          # ip
        "windows_perf",     # mark
        '{"windows_perf": {"username": "test", "password": "xxx"}}',  # extra_message
        "性能测试账号",      # note
    ])
    
    # 保存到 BytesIO
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

## 实现计划

### 后端改动

1. **模型改动** (`model.py`)
   - 新增 `is_virtual` 字段
   - `port` 字段改为 `nullable=True`
   - `to_cache_dict()` 新增 `is_virtual`

2. **Schema 改动** (`schema.py`)
   - `EnvMachineResponse` 新增 `is_virtual`
   - `EnvMachineCreateRequest` 新增 `is_virtual` (默认 `true`)
   - 新增 `EnvMachineBatchDeleteRequest`

3. **Service 改动** (`service.py`)
   - 新增 `VIRTUAL_EXCEL_COLUMNS` 配置
   - 新增 `_virtual_import_processor` 方法
   - 新增 `import_virtual_from_excel` 方法
   - 新增 `generate_virtual_import_template` 方法

4. **API 改动** (`api.py`)
   - 新增 `POST /batch-import-virtual`
   - 新增 `POST /batch-delete`
   - 新增 `GET /import-template`
   - 修改 `POST /` 创建接口

5. **升级服务改动** (`upgrade_service.py`)
   - EnvMachine 查询添加 `is_virtual=False` 过滤 (lines 263, 386, 520)

6. **配置模板服务改动** (`config_template/service.py`)
   - EnvMachine 查询添加 `is_virtual=False` 过滤 (lines 207, 457)

7. **定时任务改动** (`scheduler.py`)
   - `check_offline_machines` 添加 `is_virtual=False` 过滤 (line 259-262, 268-271)
   - `reload_machine_status_after_restart` 添加 `is_virtual=False` 过滤 (line 529-531)

8. **数据库迁移**
   - 执行 Alembic 迁移

### 前端改动

1. **TypeScript Interface** (`env-machine.ts`)
   - 新增 `is_virtual` 字段

2. **设备列表页面** (`list.vue`)
   - 表格新增 checkbox 选择列
   - 工具栏新增"批量导入"按钮
   - 工具栏新增"批量删除"按钮（选中时显示）
   - 新增批量导入弹窗（下载模板 + 上传）
   - 操作列根据 `is_virtual` 隐藏"日志"、"远程"按钮

3. **升级管理页面** (`upgrade.vue`)
   - 无需改动（后端已过滤）

4. **配置下发页面** (`config.vue`)
   - 无需改动（后端已过滤）