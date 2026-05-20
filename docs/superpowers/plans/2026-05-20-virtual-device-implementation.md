# 虚拟设备功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现虚拟设备管理功能，支持批量导入、批量删除，用于性能测试场景的账号申请

**Architecture:** 在现有设备管理系统基础上，新增 `is_virtual` 字段标识虚拟设备，修改定时任务跳过虚拟设备，新增批量导入和批量删除 API

**Tech Stack:** FastAPI + SQLAlchemy + PostgreSQL (后端), Vue 3 + Element Plus (前端)

---

## 文件结构

### 后端文件

| 文件 | 责任 | 改动类型 |
|------|------|---------|
| `backend-fastapi/core/env_machine/model.py` | 数据模型定义 | Modify |
| `backend-fastapi/core/env_machine/schema.py` | API 请求/响应 Schema | Modify |
| `backend-fastapi/core/env_machine/service.py` | 业务逻辑和导入处理 | Modify |
| `backend-fastapi/core/env_machine/api.py` | API 路由定义 | Modify |
| `backend-fastapi/core/env_machine/scheduler.py` | 定时任务（离线检测） | Modify |
| `backend-fastapi/core/env_machine/upgrade_service.py` | 升级服务 | Modify |
| `backend-fastapi/core/config_template/service.py` | 配置下发服务 | Modify |

### 前端文件

| 文件 | 责任 | 改动类型 |
|------|------|---------|
| `web/apps/web-ele/src/api/core/env-machine.ts` | TypeScript Interface | Modify |
| `web/apps/web-ele/src/views/env-machine/list.vue` | 设备列表页面 | Modify |
| `web/apps/web-ele/src/views/env-machine/types.ts` | 类型定义 | Modify |

---

## Task 1: 后端模型改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/model.py`

- [ ] **Step 1: 添加 is_virtual 字段**

在 `EnvMachine` 类中添加新字段（约 line 61 之后）：

```python
# 是否为虚拟设备（虚拟设备不参与离线检测和重启重载）
is_virtual = Column(Boolean, nullable=False, default=False, comment="是否为虚拟设备")
```

- [ ] **Step 2: 修改 port 字段为 nullable**

找到现有 port 字段定义（约 line 46），修改为：

```python
# 机器端口（虚拟设备可为空）
port = Column(String(10), nullable=True, comment="机器端口")
```

- [ ] **Step 3: 添加 is_virtual 索引**

找到 `__table_args__` 定义（约 line 91），添加新索引：

```python
__table_args__ = (
    UniqueConstraint("namespace", "ip", "device_type", "device_sn", name="uq_env_machine_namespace_ip_device"),
    Index("ix_env_machine_status", "status"),
    Index("ix_env_machine_sync_time", "sync_time"),
    Index("ix_env_machine_is_virtual", "is_virtual"),  # 新增
)
```

- [ ] **Step 4: 更新 to_cache_dict() 方法**

找到 `to_cache_dict()` 方法（约 line 110），添加 is_virtual 字段：

```python
def to_cache_dict(self) -> dict:
    """转换为缓存字典格式"""
    return {
        "id": self.id,
        "namespace": self.namespace,
        "ip": self.ip,
        "port": self.port,
        "asset_number": self.asset_number,
        "mark": self.mark,
        "device_type": self.device_type,
        "device_sn": self.device_sn,
        "available": self.available,
        "status": self.status,
        "note": self.note,
        "sync_time": self.sync_time.isoformat() if self.sync_time else None,
        "extra_message": self.extra_message,
        "version": self.version,
        "config_version": self.config_version,
        "config_status": self.config_status,
        "scripts": self.scripts,
        "last_keepusing_time": self.last_keepusing_time.isoformat() if self.last_keepusing_time else None,
        "is_virtual": self.is_virtual,  # 新增
    }
```

- [ ] **Step 5: 提交模型改动**

```bash
git add backend-fastapi/core/env_machine/model.py
git commit -m "feat(env_machine): 添加 is_virtual 字段和修改 port nullable"
```

---

## Task 2: 后端 Schema 改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py`

- [ ] **Step 1: EnvMachineResponse 新增 is_virtual 字段**

找到 `EnvMachineResponse` 类（约 line 92），在末尾添加：

```python
is_virtual: bool = Field(default=False, description="是否为虚拟设备")
```

完整字段列表应为：

```python
class EnvMachineResponse(BaseModel):
    """执行机信息响应 Schema"""
    id: str = Field(..., description="机器ID")
    namespace: str = Field(..., description="机器分类")
    ip: str = Field(..., description="机器IP")
    port: str = Field(..., description="机器端口")
    asset_number: Optional[str] = Field(None, description="资产编号")
    mark: Optional[str] = Field(None, description="机器标签")
    device_type: str = Field(..., description="机器类型")
    device_sn: Optional[str] = Field(None, description="设备SN")
    available: bool = Field(..., description="是否启用")
    status: str = Field(..., description="状态")
    status_display: Optional[str] = Field(None, description="状态显示名称")
    note: Optional[str] = Field(None, description="备注")
    sync_time: Optional[datetime] = Field(None, description="同步时间")
    extra_message: Optional[Dict[str, Any]] = Field(None, description="扩展信息")
    version: Optional[str] = Field(None, description="机器版本")
    config_version: Optional[str] = Field(None, description="配置版本")
    config_status: Optional[str] = Field(None, description="配置状态")
    scripts: Optional[Dict[str, str]] = Field(None, description="脚本版本字典")
    last_keepusing_time: Optional[datetime] = Field(None, description="最后保持使用时间")
    sort: int = Field(default=0, description="排序")
    is_deleted: bool = Field(default=False, description="是否删除")
    sys_create_datetime: Optional[datetime] = Field(None, description="创建时间")
    sys_update_datetime: Optional[datetime] = Field(None, description="更新时间")
    is_virtual: bool = Field(default=False, description="是否为虚拟设备")  # 新增

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: EnvMachineCreateRequest 新增 is_virtual 字段**

找到 `EnvMachineCreateRequest` 类（约 line 43），添加字段：

```python
class EnvMachineCreateRequest(BaseModel):
    """新增执行机请求 Schema"""
    namespace: str = Field(..., description="机器分类")
    device_type: str = Field(..., description="机器类型：windows/mac/ios/android")
    asset_number: str = Field(..., description="资产编号（必填）")
    ip: Optional[str] = Field(None, description="IP地址（Windows/Mac）")
    device_sn: Optional[str] = Field(None, description="设备SN（iOS/Android）")
    note: Optional[str] = Field(None, description="备注")
    is_virtual: bool = Field(default=True, description="是否为虚拟设备")  # 新增，默认为虚拟设备
```

- [ ] **Step 3: 新增 EnvMachineBatchDeleteRequest Schema**

在文件末尾添加：

```python
class EnvMachineBatchDeleteRequest(BaseModel):
    """批量删除请求 Schema"""
    ids: List[str] = Field(..., description="设备 ID 列表")


class EnvMachineBatchImportResponse(BaseModel):
    """批量导入响应 Schema"""
    success_count: int = Field(..., description="成功导入数量")
    failed_items: List[Dict[str, Any]] = Field(default_factory=list, description="失败列表")
```

- [ ] **Step 4: 提交 Schema 改动**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): Schema 新增 is_virtual 和批量操作 Schema"
```

---

## Task 3: 后端 Service 改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/service.py`

- [ ] **Step 1: 添加 import 语句**

在文件顶部添加：

```python
import json
import openpyxl
from openpyxl.styles import Font, Alignment
```

- [ ] **Step 2: 添加 VIRTUAL_EXCEL_COLUMNS 配置**

在 `EnvMachineService` 类中，在 `excel_columns` 之后添加：

```python
# 虚拟设备 Excel 导入导出配置
VIRTUAL_EXCEL_COLUMNS = {
    "namespace": "机器分类",
    "device_type": "机器类型",
    "asset_number": "资产编号",
    "ip": "虚拟标识",
    "mark": "标签",
    "extra_message": "扩展信息(JSON)",
    "note": "备注",
}
```

- [ ] **Step 3: 添加 _virtual_import_processor 方法**

在 `_import_processor` 方法之后添加：

```python
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
        if not isinstance(extra_message, dict):
            return None
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

- [ ] **Step 4: 添加 import_virtual_from_excel 方法**

在 `import_from_excel` 方法之后添加：

```python
@classmethod
async def import_virtual_from_excel(
    cls,
    db: AsyncSession,
    file_content: bytes,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    从 Excel 导入虚拟设备

    :param db: 数据库会话
    :param file_content: Excel 文件内容
    :return: (成功数量, 失败列表)
    """
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(file_content))
    ws = wb.active

    success_count = 0
    failed_items = []

    # 获取表头映射
    headers = [cell.value for cell in ws[1]]
    column_map = {}
    for key, cn_name in cls.VIRTUAL_EXCEL_COLUMNS.items():
        for idx, header in enumerate(headers):
            if header == cn_name:
                column_map[key] = idx
                break

    # 验证表头完整性
    required_keys = ["namespace", "device_type", "asset_number", "ip", "mark", "extra_message"]
    missing_keys = [k for k in required_keys if k not in column_map]
    if missing_keys:
        return 0, [{"row": 0, "reason": f"缺少必填列: {cls.VIRTUAL_EXCEL_COLUMNS[k]}" for k in missing_keys}]

    # 处理数据行（跳过表头）
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):  # 跳过空行
            continue

        # 构建 row dict
        row_dict = {}
        for key, idx in column_map.items():
            row_dict[key] = row[idx] if idx < len(row) else None

        # 处理导入
        machine = cls._virtual_import_processor(row_dict)
        if machine:
            db.add(machine)
            success_count += 1
        else:
            failed_items.append({
                "row": row_idx,
                "reason": "数据验证失败（必填字段缺失或 JSON 格式错误）"
            })

    if success_count > 0:
        await db.commit()

    return success_count, failed_items
```

- [ ] **Step 5: 添加 generate_virtual_import_template 方法**

在文件末尾添加：

```python
@classmethod
async def generate_virtual_import_template(cls) -> BytesIO:
    """生成虚拟设备导入 Excel 模板"""
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

- [ ] **Step 6: 提交 Service 改动**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): 添加虚拟设备导入处理和模板生成方法"
```

---

## Task 4: 后端 API 改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 导入新增 Schema**

在文件顶部 import 区域添加：

```python
from core.env_machine.schema import (
    # ...existing imports...
    EnvMachineBatchDeleteRequest,
    EnvMachineBatchImportResponse,
)
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
```

- [ ] **Step 2: 修改创建设备 API**

找到 `create_env_machine` 函数（约 line 415），修改为支持 is_virtual：

```python
@router.post("", response_model=EnvMachineResponse, summary="新增执行机")
async def create_env_machine(
    data: EnvMachineCreateRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """
    新增执行机（手工使用场景或虚拟设备）

    根据设备类型自动处理：
    - Windows/Mac：填写 IP
    - iOS/Android：填写 device_sn
    - 虚拟设备：is_virtual=True，无需真实 worker
    """
    # 构建端口默认值
    # 虚拟设备无端口，非虚拟设备默认8088
    if data.ip and ":" in data.ip:
        port = data.ip.split(":")[1]
        ip = data.ip.split(":")[0]
    else:
        ip = data.ip or ""
        port = None if data.is_virtual else "8088"

    # 虚拟设备默认 online（无需心跳），非虚拟设备默认 offline（等待心跳）
    machine = EnvMachine(
        namespace=data.namespace,
        device_type=data.device_type,
        asset_number=data.asset_number,
        ip=ip or "",
        port=port,
        device_sn=data.device_sn,
        note=data.note,
        status="online" if data.is_virtual else "offline",
        available=False,
        is_virtual=data.is_virtual,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)

    return EnvMachineResponse.model_validate(machine)
```

- [ ] **Step 3: 添加批量删除 API**

在文件末尾添加：

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

- [ ] **Step 4: 添加批量导入虚拟设备 API**

在批量删除 API 之后添加：

```python
@router.post("/batch-import-virtual", response_model=EnvMachineBatchImportResponse, summary="批量导入虚拟设备")
async def batch_import_virtual_devices(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> EnvMachineBatchImportResponse:
    """
    批量导入虚拟设备

    - Excel 文件上传
    - 返回导入结果
    """
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持 Excel 文件 (.xlsx, .xls)")

    content = await file.read()
    success_count, failed_items = await EnvMachineService.import_virtual_from_excel(db, content)

    return EnvMachineBatchImportResponse(
        success_count=success_count,
        failed_items=failed_items
    )
```

- [ ] **Step 5: 添加导入模板下载 API**

在批量导入 API 之后添加：

```python
@router.get("/import-template", summary="下载虚拟设备导入模板")
async def download_import_template():
    """
    下载虚拟设备导入 Excel 模板

    模板包含表头和示例数据
    """
    buffer = await EnvMachineService.generate_virtual_import_template()

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=virtual_device_import_template.xlsx"
        }
    )
```

- [ ] **Step 6: 提交 API 改动**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 添加批量导入、批量删除和模板下载 API"
```

---

## Task 5: 定时任务改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/scheduler.py`

- [ ] **Step 1: 修改 check_offline_machines 函数**

找到 `check_offline_machines` 函数（约 line 239），修改第一个查询（约 line 259-262）：

```python
stmt = select(EnvMachine).where(
    EnvMachine.sync_time < threshold,
    EnvMachine.status.in_(["online", "using"]),
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

- [ ] **Step 2: 修改 upgrading 状态超时查询**

在同一函数中找到 upgrading 查询（约 line 268-271），添加过滤：

```python
upgrade_stmt = select(EnvMachine).where(
    EnvMachine.sync_time < upgrade_threshold,
    EnvMachine.status == "upgrading",
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

- [ ] **Step 3: 修改 reload_machine_status_after_restart 函数**

找到 `reload_machine_status_after_restart` 函数（约 line 509），修改查询（约 line 529-531）：

```python
stmt = select(EnvMachine).where(
    EnvMachine.is_deleted == False,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
)
```

- [ ] **Step 4: 提交定时任务改动**

```bash
git add backend-fastapi/core/env_machine/scheduler.py
git commit -m "feat(env_machine): 定时任务跳过虚拟设备"
```

---

## Task 6: 升级服务改动

**Files:**
- Modify: `backend-fastapi/core/env_machine/upgrade_service.py`

- [ ] **Step 1: 找到并修改 get_machines_for_upgrade 函数**

找到查询 EnvMachine 的位置（约 line 263），添加过滤：

```python
stmt = select(EnvMachine).where(
    and_(
        EnvMachine.status == "upgrading",
        EnvMachine.is_deleted == False,
        EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
    )
)
```

- [ ] **Step 2: 找到并修改 get_upgrade_candidate_machines 函数**

找到查询位置（约 line 386），修改 conditions 列表：

```python
conditions = [
    EnvMachine.is_deleted == False,
    EnvMachine.available == True,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
]
```

- [ ] **Step 3: 找到并修改 search_machines_for_upgrade 函数**

找到查询位置（约 line 520），修改 conditions 列表：

```python
conditions = [
    EnvMachine.is_deleted == False,
    EnvMachine.available == True,
    EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
]
```

- [ ] **Step 4: 提交升级服务改动**

```bash
git add backend-fastapi/core/env_machine/upgrade_service.py
git commit -m "feat(env_machine): 升级服务过滤虚拟设备"
```

---

## Task 7: 配置模板服务改动

**Files:**
- Modify: `backend-fastapi/core/config_template/service.py`

- [ ] **Step 1: 找到并修改 get_machines_for_config 函数**

找到查询 EnvMachine 的位置（约 line 207），在 conditions 列表末尾添加：

```python
conditions.append(EnvMachine.is_virtual == False)  # 新增：跳过虚拟设备
```

完整代码应为：

```python
# 构建查询条件
conditions = [EnvMachine.is_deleted == False]

# ...existing conditions...

# 新增：过滤虚拟设备
conditions.append(EnvMachine.is_virtual == False)

result = await db.execute(select(EnvMachine).where(and_(*conditions)))
```

- [ ] **Step 2: 找到并修改批量配置下发相关查询**

找到另一个查询位置（约 line 457），添加过滤：

```python
stmt = select(EnvMachine).where(
    and_(
        EnvMachine.id.in_(machine_ids),
        EnvMachine.is_deleted == False,
        EnvMachine.is_virtual == False,  # 新增：跳过虚拟设备
    )
)
```

- [ ] **Step 3: 提交配置模板服务改动**

```bash
git add backend-fastapi/core/config_template/service.py
git commit -m "feat(config_template): 配置下发服务过滤虚拟设备"
```

---

## Task 8: 数据库迁移

**Files:**
- None (执行命令)

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add is_virtual field and make port nullable for virtual devices"
```

预期输出：生成新的迁移文件在 `alembic/versions/` 目录

- [ ] **Step 2: 执行迁移**

```bash
alembic upgrade head
```

预期输出：数据库更新成功

- [ ] **Step 3: 验证迁移**

连接数据库验证：

```sql
-- 检查 is_virtual 字段是否存在
SELECT column_name, data_type, nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'env_machine' AND column_name = 'is_virtual';

-- 检查 port 字段 nullable
SELECT column_name, nullable 
FROM information_schema.columns 
WHERE table_name = 'env_machine' AND column_name = 'port';
```

预期结果：
- is_virtual 字段存在，类型 boolean，nullable=false，default=false
- port 字段 nullable=true

- [ ] **Step 4: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/*.py
git commit -m "feat: 数据库迁移 - 添加 is_virtual 字段和修改 port nullable"
```

---

## Task 9: 前端 TypeScript Interface 更新

**Files:**
- Modify: `web/apps/web-ele/src/api/core/env-machine.ts`

- [ ] **Step 1: 读取现有 Interface**

找到 EnvMachine interface 定义

- [ ] **Step 2: 新增 is_virtual 字段**

在 interface 末尾添加：

```typescript
export interface EnvMachine {
  id: string;
  namespace: string;
  ip: string;
  port: string;
  asset_number?: string;
  mark?: string;
  device_type: string;
  device_sn?: string;
  available: boolean;
  status: string;
  status_display?: string;
  note?: string;
  sync_time?: string;
  extra_message?: Record<string, any>;
  version?: string;
  config_version?: string;
  config_status?: string;
  scripts?: Record<string, string>;
  last_keepusing_time?: string;
  sort: number;
  is_deleted: boolean;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
  is_virtual: boolean;  // 新增
}
```

- [ ] **Step 3: 新增批量删除和批量导入 API 函数**

在文件末尾添加：

```typescript
// 批量删除设备
export function batchDeleteEnvMachineApi(ids: string[]) {
  return requestClient.post<{ success_count: number; failed_ids: string[] }>(
    '/env/batch-delete',
    { ids }
  );
}

// 批量导入虚拟设备
export async function batchImportVirtualDevicesApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<{ success_count: number; failed_items: Array<{ row: number; reason: string }> }>(
    '/env/batch-import-virtual',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
}

// 下载虚拟设备导入模板
export async function downloadImportTemplateApi() {
  const response = await requestClient.get('/env/import-template', {
    responseType: 'blob',
  });
  return response;
}
```

- [ ] **Step 4: 提交 TypeScript 改动**

```bash
git add web/apps/web-ele/src/api/core/env-machine.ts
git commit -m "feat(env-machine): TypeScript 新增 is_virtual 和批量操作 API"
```

---

## Task 10: 前端设备列表页面改动 - Part 1 (选择功能)

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 添加表格选择列**

在 `<ElTable>` 组件中添加 selection 列和 ref：

```vue
<script lang="ts" setup>
// ...existing code...

// 新增：表格选择相关
const selectedRows = ref<EnvMachine[]>([]);
const selectionAll = ref(false);

function handleSelectionChange(rows: EnvMachine[]) {
  selectedRows.value = rows;
}
</script>

<template>
  <!-- 修改 ElTable -->
  <ElTable 
    :data="tableData" 
    v-loading="loading" 
    class="env-table" 
    border
    @selection-change="handleSelectionChange"
  >
    <!-- 新增：选择列 -->
    <ElTableColumn type="selection" width="50" />
    
    <!-- ...existing columns... -->
  </ElTable>
</template>
```

- [ ] **Step 2: 添加批量删除按钮**

在搜索按钮区域添加批量删除按钮：

```vue
<script lang="ts" setup>
// ...existing code...

// 新增：批量删除
const batchDeleteLoading = ref(false);

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的设备');
    return;
  }

  const count = selectedRows.value.length;
  ElMessageBox.confirm(
    `确定要删除选中的 ${count} 台设备吗？`,
    '批量删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    batchDeleteLoading.value = true;
    try {
      const ids = selectedRows.value.map(row => row.id);
      const result = await batchDeleteEnvMachineApi(ids);
      ElMessage.success(`成功删除 ${result.success_count} 台设备`);
      selectedRows.value = [];
      loadData();
    } catch (error) {
      ElMessage.error('批量删除失败');
    } finally {
      batchDeleteLoading.value = false;
    }
  });
}
</script>

<template>
  <!-- 在 env-search-buttons 区域添加批量删除按钮 -->
  <div class="env-search-buttons">
    <ElButton type="primary" @click="handleSearch">查询</ElButton>
    <ElButton @click="handleReset">重置</ElButton>
    <!-- 新增：批量导入按钮 -->
    <ElButton type="success" @click="importDialogVisible = true">批量导入</ElButton>
    <!-- 新增：批量删除按钮（仅选中时显示） -->
    <ElButton 
      v-if="selectedRows.length > 0"
      type="danger" 
      :loading="batchDeleteLoading"
      @click="handleBatchDelete"
    >
      批量删除 ({{ selectedRows.length }})
    </ElButton>
  </div>
</template>
```

- [ ] **Step 3: 提交选择功能改动**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat(env-machine): 添加表格选择列和批量删除按钮"
```

---

## Task 11: 前端设备列表页面改动 - Part 2 (批量导入弹窗)

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 添加批量导入弹窗状态**

```vue
<script lang="ts" setup>
// ...existing code...

// 新增：批量导入相关
const importDialogVisible = ref(false);
const importLoading = ref(false);
const importFile = ref<File | null>(null);
const importResult = ref<{ success_count: number; failed_items: Array<{ row: number; reason: string }> } | null>(null);

// 文件上传处理
function handleFileChange(file: File) {
  importFile.value = file;
  importResult.value = null;
  return false; // 阻止自动上传
}

// 下载模板
async function handleDownloadTemplate() {
  try {
    const blob = await downloadImportTemplateApi();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'virtual_device_import_template.xlsx';
    link.click();
    window.URL.revokeObjectURL(url);
    ElMessage.success('模板下载成功');
  } catch (error) {
    ElMessage.error('模板下载失败');
  }
}

// 执行导入
async function handleImport() {
  if (!importFile.value) {
    ElMessage.warning('请先选择要导入的 Excel 文件');
    return;
  }

  importLoading.value = true;
  try {
    const result = await batchImportVirtualDevicesApi(importFile.value);
    importResult.value = result;
    if (result.success_count > 0) {
      ElMessage.success(`成功导入 ${result.success_count} 台虚拟设备`);
      loadData();
    }
    if (result.failed_items.length > 0) {
      ElMessage.warning(`${result.failed_items.length} 条数据导入失败`);
    }
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '导入失败';
    ElMessage.error(msg);
  } finally {
    importLoading.value = false;
  }
}

// 关闭弹窗
function handleImportDialogClose() {
  importDialogVisible.value = false;
  importFile.value = null;
  importResult.value = null;
}
</script>
```

- [ ] **Step 2: 添加批量导入弹窗组件**

```vue
<template>
  <!-- ...existing code... -->

  <!-- 新增：批量导入弹窗 -->
  <ElDialog
    v-model="importDialogVisible"
    title="批量导入虚拟设备"
    width="600px"
    :close-on-click-modal="false"
    @close="handleImportDialogClose"
  >
    <div class="import-dialog-content">
      <!-- 下载模板 -->
      <div class="import-section">
        <ElButton type="primary" plain @click="handleDownloadTemplate">
          下载导入模板
        </ElButton>
        <span class="import-tip">请先下载模板，按格式填写数据后再导入</span>
      </div>

      <!-- 上传文件 -->
      <div class="import-section">
        <ElUpload
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xls"
          :before-upload="handleFileChange"
        >
          <ElButton type="success">选择 Excel 文件</ElButton>
        </ElUpload>
        <span v-if="importFile" class="import-file-name">{{ importFile.name }}</span>
      </div>

      <!-- 导入结果 -->
      <div v-if="importResult" class="import-result">
        <div class="import-success">
          成功导入：<strong>{{ importResult.success_count }}</strong> 台
        </div>
        <div v-if="importResult.failed_items.length > 0" class="import-failed">
          <div>失败记录：</div>
          <ul>
            <li v-for="item in importResult.failed_items" :key="item.row">
              第 {{ item.row }} 行：{{ item.reason }}
            </li>
          </ul>
        </div>
      </div>
    </div>

    <template #footer>
      <ElButton @click="handleImportDialogClose">关闭</ElButton>
      <ElButton type="primary" :loading="importLoading" @click="handleImport">
        开始导入
      </ElButton>
    </template>
  </ElDialog>
</template>
```

- [ ] **Step 3: 添加弹窗样式**

```vue
<style scoped>
/* ...existing styles... */

/* 批量导入弹窗样式 */
.import-dialog-content {
  padding: 20px;
}

.import-section {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.import-tip {
  color: #666;
  font-size: 13px;
}

.import-file-name {
  color: #52c41a;
  font-size: 13px;
}

.import-result {
  margin-top: 20px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 4px;
}

.import-success {
  margin-bottom: 12px;
}

.import-success strong {
  color: #52c41a;
}

.import-failed {
  color: #ff4d4f;
}

.import-failed ul {
  margin-top: 8px;
  padding-left: 20px;
}
</style>
```

- [ ] **Step 4: 提交批量导入弹窗改动**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat(env-machine): 添加批量导入虚拟设备弹窗"
```

---

## Task 12: 前端设备列表页面改动 - Part 3 (操作列调整)

**Files:**
- Modify: `web/apps/web-ele/src/views/env-machine/list.vue`

- [ ] **Step 1: 修改操作列**

找到操作列（约 template line 503），修改为根据 is_virtual 隐藏日志和远程按钮：

```vue
<ElTableColumn label="操作" min-width="160">
  <template #default="{ row }">
    <span class="nowrap">
      <!-- 日志按钮：虚拟设备隐藏 -->
      <a 
        v-if="!isMobileDevice(row.device_type) && row.status !== 'offline' && !row.is_virtual" 
        class="env-link" 
        @click="handleViewLogs(row)"
      >
        日志
      </a>
      <!-- 远程按钮：虚拟设备隐藏 -->
      <a 
        v-if="row.status === 'online' && !row.is_virtual" 
        class="env-link" 
        @click="handleDebug(row)"
      >
        远程
      </a>
      <!-- 编辑和删除：所有设备显示 -->
      <a class="env-link" @click="handleEdit(row)">编辑</a>
      <a class="env-link env-link-danger" @click="handleDelete(row)">删除</a>
    </span>
  </template>
</ElTableColumn>
```

- [ ] **Step 2: 提交操作列改动**

```bash
git add web/apps/web-ele/src/views/env-machine/list.vue
git commit -m "feat(env-machine): 虚拟设备隐藏日志和远程按钮"
```

---

## Task 13: 功能验证

**Files:**
- None (手动验证)

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi
conda activate zq-fastapi
python main.py
```

预期：服务启动成功，监听 8000 端口

- [ ] **Step 2: 启动前端服务**

```bash
cd web
pnpm dev
```

预期：前端服务启动成功

- [ ] **Step 3: 验证 API 文档**

访问 http://localhost:8000/docs

验证新增 API：
- `POST /api/core/env/batch-import-virtual`
- `POST /api/core/env/batch-delete`
- `GET /api/core/env/import-template`

- [ ] **Step 4: 验证批量导入流程**

1. 点击"批量导入"按钮
2. 点击"下载导入模板"
3. 填写 Excel 文件
4. 上传并导入
5. 检查导入结果

- [ ] **Step 5: 验证批量删除流程**

1. 选择多台设备
2. 点击"批量删除"按钮
3. 确认删除
4. 检查删除结果

- [ ] **Step 6: 验证虚拟设备不显示日志/远程**

1. 导入虚拟设备
2. 检查操作列是否隐藏日志和远程按钮

- [ ] **Step 7: 验证虚拟设备申请流程**

1. 编辑虚拟设备，设置 available=true 和 extra_message
2. 通过 API 申请虚拟设备
3. 检查申请结果

---

## Task 14: 最终提交

- [ ] **Step 1: 合并所有改动**

```bash
git status
git log --oneline -10
```

- [ ] **Step 2: 创建功能完成标记**

```bash
git tag -a v1.x-virtual-device -m "虚拟设备功能完成"
```

- [ ] **Step 3: 推送到远程仓库**

```bash
git push origin main --tags
```