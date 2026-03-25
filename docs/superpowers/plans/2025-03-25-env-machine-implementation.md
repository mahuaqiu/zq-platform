# 机器管理前端页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现机器管理前端页面，支持五个子菜单（集成验证/APP/音视频/公共设备/手工使用）的设备列表展示和管理。

**Architecture:** 后端新增 asset_number 字段和 CRUD API；前端使用 Vue 3 + Element Plus + VxeTable，通过路由参数区分不同 namespace，复用同一套表格组件。

**Tech Stack:** FastAPI + SQLAlchemy (后端)，Vue 3 + Element Plus + VxeTable + TypeScript (前端)

---

## 文件结构

### 后端文件（修改）
- `backend-fastapi/core/env_machine/model.py` - 新增 asset_number 字段
- `backend-fastapi/core/env_machine/schema.py` - 新增 CRUD Schema
- `backend-fastapi/core/env_machine/api.py` - 新增 CRUD API 端点
- `backend-fastapi/core/env_machine/service.py` - 新增查询方法

### 前端文件（新建）
- `web/apps/web-ele/src/api/core/env-machine.ts` - API 接口定义
- `web/apps/web-ele/src/views/env-machine/index.vue` - 主页面入口
- `web/apps/web-ele/src/views/env-machine/data.ts` - 表格列、表单 Schema 配置
- `web/apps/web-ele/src/views/env-machine/types.ts` - TypeScript 类型定义
- `web/apps/web-ele/src/views/env-machine/modules/machine-form-modal.vue` - 新增/编辑弹窗

---

## Task 1: 后端 - 新增 asset_number 字段

**Files:**
- Modify: `backend-fastapi/core/env_machine/model.py`

- [ ] **Step 1: 在 model.py 中新增 asset_number 字段**

在 `EnvMachine` 类中添加字段：

```python
# 在 port 字段后添加
# 资产编号
asset_number = Column(String(32), nullable=True, comment="资产编号")
```

- [ ] **Step 2: 更新 to_cache_dict 方法**

在 `to_cache_dict` 方法中添加：

```python
"asset_number": self.asset_number,
```

- [ ] **Step 3: 更新 excel_columns 配置**

在 `EnvMachineService` 的 `excel_columns` 中添加：

```python
"asset_number": "资产编号",
```

- [ ] **Step 4: 更新 _export_converter 方法**

在 `_export_converter` 方法中添加：

```python
"asset_number": item.asset_number or "",
```

- [ ] **Step 5: 更新 _import_processor 方法**

在 `_import_processor` 方法中添加：

```python
asset_number=str(row.get("asset_number")) if row.get("asset_number") else None,
```

在 `EnvMachine` 构造函数参数中添加 `asset_number`。

- [ ] **Step 6: 提交**

```bash
git add backend-fastapi/core/env_machine/model.py backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): 新增 asset_number 资产编号字段"
```

---

## Task 2: 后端 - 新增 CRUD Schema

**Files:**
- Modify: `backend-fastapi/core/env_machine/schema.py`

- [ ] **Step 1: 新增 EnvMachineListRequest Schema**

```python
class EnvMachineListRequest(BaseModel):
    """执行机列表查询请求 Schema"""
    namespace: str = Field(..., description="机器分类")
    device_type: Optional[str] = Field(None, description="机器类型")
    ip: Optional[str] = Field(None, description="IP地址（模糊查询）")
    asset_number: Optional[str] = Field(None, description="资产编号（模糊查询）")
    mark: Optional[str] = Field(None, description="标签（模糊查询）")
    available: Optional[bool] = Field(None, description="是否启用")
    note: Optional[str] = Field(None, description="备注（模糊查询）")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
```

- [ ] **Step 2: 新增 EnvMachineCreateRequest Schema**

```python
class EnvMachineCreateRequest(BaseModel):
    """新增执行机请求 Schema"""
    namespace: str = Field(..., description="机器分类")
    device_type: str = Field(..., description="机器类型：windows/mac/ios/android")
    asset_number: str = Field(..., description="资产编号（必填）")
    ip: Optional[str] = Field(None, description="IP地址（Windows/Mac）")
    device_sn: Optional[str] = Field(None, description="设备SN（iOS/Android）")
    note: Optional[str] = Field(None, description="备注")
```

- [ ] **Step 3: 新增 EnvMachineUpdateRequest Schema**

```python
class EnvMachineUpdateRequest(BaseModel):
    """更新执行机请求 Schema"""
    asset_number: Optional[str] = Field(None, description="资产编号")
    ip: Optional[str] = Field(None, description="IP地址")
    device_sn: Optional[str] = Field(None, description="设备SN")
    mark: Optional[str] = Field(None, description="标签")
    available: Optional[bool] = Field(None, description="是否启用")
    note: Optional[str] = Field(None, description="备注")
```

- [ ] **Step 4: 更新 EnvMachineResponse Schema**

在 `EnvMachineResponse` 中添加 `asset_number` 字段：

```python
asset_number: Optional[str] = Field(None, description="资产编号")
```

- [ ] **Step 5: 提交**

```bash
git add backend-fastapi/core/env_machine/schema.py
git commit -m "feat(env_machine): 新增 CRUD Schema 定义"
```

---

## Task 3: 后端 - 新增 Service 查询方法

**Files:**
- Modify: `backend-fastapi/core/env_machine/service.py`

- [ ] **Step 1: 新增 get_list_with_filters 方法**

在 `EnvMachineService` 类中添加：

```python
@classmethod
async def get_list_with_filters(
    cls,
    db: AsyncSession,
    namespace: str,
    device_type: Optional[str] = None,
    ip: Optional[str] = None,
    asset_number: Optional[str] = None,
    mark: Optional[str] = None,
    available: Optional[bool] = None,
    note: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[EnvMachine], int]:
    """
    多条件查询执行机列表

    :param db: 数据库会话
    :param namespace: 机器分类（必填）
    :param device_type: 机器类型
    :param ip: IP地址（模糊查询）
    :param asset_number: 资产编号（模糊查询）
    :param mark: 标签（模糊查询）
    :param available: 是否启用
    :param note: 备注（模糊查询）
    :param page: 页码
    :param page_size: 每页数量
    :return: (机器列表, 总数)
    """
    filters = [EnvMachine.namespace == namespace, EnvMachine.is_deleted == False]

    if device_type:
        filters.append(EnvMachine.device_type == device_type)

    if ip:
        escaped_ip = ip.replace("%", r"\%").replace("_", r"\_")
        filters.append(EnvMachine.ip.ilike(f"%{escaped_ip}%"))

    if asset_number:
        escaped_asset_number = asset_number.replace("%", r"\%").replace("_", r"\_")
        filters.append(EnvMachine.asset_number.ilike(f"%{escaped_asset_number}%"))

    if mark:
        escaped_mark = mark.replace("%", r"\%").replace("_", r"\_")
        filters.append(EnvMachine.mark.ilike(f"%{escaped_mark}%"))

    if available is not None:
        filters.append(EnvMachine.available == available)

    if note:
        escaped_note = note.replace("%", r"\%").replace("_", r"\_")
        filters.append(EnvMachine.note.ilike(f"%{escaped_note}%"))

    return await cls.get_list(db, page=page, page_size=page_size, filters=filters)
```

- [ ] **Step 2: 提交**

```bash
git add backend-fastapi/core/env_machine/service.py
git commit -m "feat(env_machine): 新增多条件查询方法 get_list_with_filters"
```

---

## Task 4: 后端 - 新增 CRUD API 端点

**Files:**
- Modify: `backend-fastapi/core/env_machine/api.py`

- [ ] **Step 1: 导入新的 Schema 和分页响应**

```python
from core.env_machine.schema import (
    EnvRegisterRequest,
    EnvMachineIdItem,
    EnvSuccessResponse,
    EnvFailResponse,
    EnvMachineListRequest,
    EnvMachineCreateRequest,
    EnvMachineUpdateRequest,
    EnvMachineResponse,
)
from app.base_schema import PaginatedResponse
```

- [ ] **Step 2: 新增列表查询 API**

```python
@router.get("", response_model=PaginatedResponse[EnvMachineResponse], summary="查询执行机列表")
async def list_env_machines(
    namespace: str,
    device_type: Optional[str] = None,
    ip: Optional[str] = None,
    asset_number: Optional[str] = None,
    mark: Optional[str] = None,
    available: Optional[bool] = None,
    note: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse[EnvMachineResponse]:
    """
    查询执行机列表

    支持 namespace 必填筛选，其他条件可选。
    """
    machines, total = await EnvMachineService.get_list_with_filters(
        db,
        namespace=namespace,
        device_type=device_type,
        ip=ip,
        asset_number=asset_number,
        mark=mark,
        available=available,
        note=note,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=[EnvMachineResponse.model_validate(m) for m in machines],
        total=total,
    )
```

- [ ] **Step 3: 新增创建 API**

```python
@router.post("", response_model=EnvMachineResponse, summary="新增执行机")
async def create_env_machine(
    data: EnvMachineCreateRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """
    新增执行机（手工使用场景）

    根据设备类型自动处理：
    - Windows/Mac：填写 IP
    - iOS/Android：填写 device_sn
    """
    # 构建端口默认值
    port = data.ip.split(":")[1] if data.ip and ":" in data.ip else "8088"
    ip = data.ip.split(":")[0] if data.ip and ":" in data.ip else data.ip

    machine = EnvMachine(
        namespace=data.namespace,
        device_type=data.device_type,
        asset_number=data.asset_number,
        ip=ip or "",
        port=port,
        device_sn=data.device_sn,
        note=data.note,
        status="offline",
        available=False,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)

    return EnvMachineResponse.model_validate(machine)
```

- [ ] **Step 4: 新增更新 API**

```python
@router.put("/{machine_id}", response_model=EnvMachineResponse, summary="更新执行机")
async def update_env_machine(
    machine_id: str,
    data: EnvMachineUpdateRequest,
    db: AsyncSession = Depends(get_db)
) -> EnvMachineResponse:
    """更新执行机信息"""
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(machine, key, value)

    await db.commit()
    await db.refresh(machine)

    return EnvMachineResponse.model_validate(machine)
```

- [ ] **Step 5: 新增删除 API**

```python
@router.delete("/{machine_id}", summary="删除执行机")
async def delete_env_machine(
    machine_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除执行机（软删除）"""
    machine = await EnvMachineService.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="执行机不存在")

    await EnvMachineService.delete(db, machine_id)
    await db.commit()

    return {"status": "success", "message": "删除成功"}
```

- [ ] **Step 6: 提交**

```bash
git add backend-fastapi/core/env_machine/api.py
git commit -m "feat(env_machine): 新增 CRUD API 端点"
```

---

## Task 5: 后端 - 数据库迁移

**Files:**
- Run: `alembic revision --autogenerate -m "add asset_number to env_machine"`
- Run: `alembic upgrade head`

- [ ] **Step 1: 激活 Python 虚拟环境**

```bash
conda activate zq-fastapi
# 或者
source .venv/bin/activate  # Mac/Linux
.venv\Scripts\activate     # Windows
```

- [ ] **Step 2: 生成迁移文件**

```bash
cd backend-fastapi
alembic revision --autogenerate -m "add asset_number to env_machine"
```

- [ ] **Step 3: 执行迁移**

```bash
alembic upgrade head
```

- [ ] **Step 4: 验证迁移**

启动后端服务，确认无报错：

```bash
python main.py
```

- [ ] **Step 5: 提交迁移文件**

```bash
git add backend-fastapi/alembic/versions/
git commit -m "feat(env_machine): 数据库迁移 - 新增 asset_number 字段"
```

---

## Task 6: 前端 - 新增 API 接口定义

**Files:**
- Create: `web/apps/web-ele/src/api/core/env-machine.ts`

- [ ] **Step 1: 创建 API 文件**

```typescript
import { requestClient } from '#/api/request';

/**
 * 执行机类型定义
 */
export interface EnvMachine {
  id: string;
  namespace: string;
  ip: string;
  port: string;
  mark?: string;
  device_type: string;
  device_sn?: string;
  asset_number?: string;
  available: boolean;
  status: string;
  status_display?: string;
  note?: string;
  extra_message?: Record<string, any>;
  version?: string;
  sync_time?: string;
  last_keepusing_time?: string;
  sort: number;
  is_deleted: boolean;
  sys_create_datetime?: string;
  sys_update_datetime?: string;
}

/**
 * 查询参数
 */
export interface EnvMachineQueryParams {
  namespace: string;
  device_type?: string;
  ip?: string;
  asset_number?: string;
  mark?: string;
  available?: boolean;
  note?: string;
  page: number;
  page_size: number;
}

/**
 * 创建参数
 */
export interface EnvMachineCreateParams {
  namespace: string;
  device_type: string;
  asset_number: string;
  ip?: string;
  device_sn?: string;
  note?: string;
}

/**
 * 更新参数
 */
export interface EnvMachineUpdateParams {
  asset_number?: string;
  ip?: string;
  device_sn?: string;
  mark?: string;
  available?: boolean;
  note?: string;
}

/**
 * 分页响应（后端只返回 items 和 total）
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

/**
 * 获取执行机列表
 */
export async function getEnvMachineListApi(params: EnvMachineQueryParams) {
  return requestClient.get<PaginatedResponse<EnvMachine>>('/api/core/env', { params });
}

/**
 * 新增执行机
 */
export async function createEnvMachineApi(data: EnvMachineCreateParams) {
  return requestClient.post<EnvMachine>('/api/core/env', data);
}

/**
 * 更新执行机
 */
export async function updateEnvMachineApi(id: string, data: EnvMachineUpdateParams) {
  return requestClient.put<EnvMachine>(`/api/core/env/${id}`, data);
}

/**
 * 删除执行机
 */
export async function deleteEnvMachineApi(id: string) {
  return requestClient.delete(`/api/core/env/${id}`);
}
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/api/core/env-machine.ts
git commit -m "feat(env_machine): 新增前端 API 接口定义"
```

---

## Task 7: 前端 - 新增类型定义

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/types.ts`

- [ ] **Step 1: 创建类型定义文件**

```typescript
/**
 * 设备类型
 */
export type DeviceType = 'windows' | 'mac' | 'ios' | 'android';

/**
 * 设备状态
 */
export type DeviceStatus = 'online' | 'using' | 'offline';

/**
 * Namespace 映射
 */
export const NAMESPACE_MAP: Record<string, string> = {
  gamma: 'meeting_gamma',
  app: 'meeting_app',
  av: 'meeting_av',
  public: 'meeting_public',
  manual: 'meeting_manual',
};

/**
 * 设备类型选项
 */
export const DEVICE_TYPE_OPTIONS = [
  { label: 'Windows', value: 'windows' },
  { label: 'Mac', value: 'mac' },
  { label: 'iOS', value: 'ios' },
  { label: 'Android', value: 'android' },
];

/**
 * 状态选项
 */
export const STATUS_OPTIONS = [
  { label: '在线', value: 'online', type: 'success' },
  { label: '使用中', value: 'using', type: 'warning' },
  { label: '离线', value: 'offline', type: 'info' },
];

/**
 * 是否启用选项
 */
export const AVAILABLE_OPTIONS = [
  { label: '是', value: true },
  { label: '否', value: false },
];

/**
 * 判断是否为移动端设备
 */
export function isMobileDevice(deviceType: DeviceType): boolean {
  return deviceType === 'ios' || deviceType === 'android';
}
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/types.ts
git commit -m "feat(env_machine): 新增前端类型定义和常量"
```

---

## Task 8: 前端 - 新增表格列和表单 Schema 配置

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/data.ts`

- [ ] **Step 1: 创建 data.ts 文件**

```typescript
import type { Column } from 'element-plus';
import type { VbenFormSchema } from '#/adapter/form';

import { z } from '#/adapter/form';

import {
  DEVICE_TYPE_OPTIONS,
  STATUS_OPTIONS,
  AVAILABLE_OPTIONS,
} from './types';

/**
 * 标准页面搜索表单 Schema（集成验证/APP/音视频/公共设备）
 */
export function useStandardSearchFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Select',
      fieldName: 'device_type',
      label: '机器类型',
      componentProps: {
        options: DEVICE_TYPE_OPTIONS,
        clearable: true,
        placeholder: '请选择机器类型',
      },
    },
    {
      component: 'Input',
      fieldName: 'ip',
      label: '机器信息',
      componentProps: {
        placeholder: '搜索IP地址',
      },
    },
    {
      component: 'Input',
      fieldName: 'asset_number',
      label: '资产编号',
      componentProps: {
        placeholder: '搜索资产编号',
      },
    },
    {
      component: 'Input',
      fieldName: 'mark',
      label: '标签',
      componentProps: {
        placeholder: '搜索标签',
      },
    },
    {
      component: 'Select',
      fieldName: 'available',
      label: '是否启用',
      componentProps: {
        options: AVAILABLE_OPTIONS,
        clearable: true,
        placeholder: '请选择',
      },
    },
  ];
}

/**
 * 手工使用页面搜索表单 Schema
 */
export function useManualSearchFormSchema(): VbenFormSchema[] {
  return [
    {
      component: 'Select',
      fieldName: 'device_type',
      label: '机器类型',
      componentProps: {
        options: DEVICE_TYPE_OPTIONS,
        clearable: true,
        placeholder: '请选择机器类型',
      },
    },
    {
      component: 'Input',
      fieldName: 'ip',
      label: '机器信息',
      componentProps: {
        placeholder: '搜索IP地址',
      },
    },
    {
      component: 'Input',
      fieldName: 'asset_number',
      label: '资产编号',
      componentProps: {
        placeholder: '搜索资产编号',
      },
    },
    {
      component: 'Input',
      fieldName: 'note',
      label: '备注',
      componentProps: {
        placeholder: '搜索备注',
      },
    },
  ];
}

/**
 * 格式化设备类型显示
 */
function formatDeviceType(value: string): string {
  const option = DEVICE_TYPE_OPTIONS.find((o) => o.value === value);
  return option?.label || value;
}

/**
 * 标准页面表格列配置（集成验证/APP/音视频/公共设备）
 * 使用 Element Plus Table Column API
 */
export function useStandardColumns(): Column[] {
  return [
    {
      key: 'device_type',
      title: '机器类型',
      width: 100,
      align: 'center' as const,
      slots: { default: 'cell-device_type' },
    },
    {
      key: 'ip',
      dataKey: 'ip',
      title: '机器信息',
      width: 140,
    },
    {
      key: 'device_sn',
      dataKey: 'device_sn',
      title: 'SN',
      width: 140,
    },
    {
      key: 'asset_number',
      dataKey: 'asset_number',
      title: '资产编号',
      width: 120,
    },
    {
      key: 'mark',
      dataKey: 'mark',
      title: '标签',
      width: 100,
    },
    {
      key: 'status',
      title: '状态',
      width: 80,
      align: 'center' as const,
      slots: { default: 'cell-status' },
    },
    {
      key: 'available',
      title: '是否启用',
      width: 80,
      align: 'center' as const,
      slots: { default: 'cell-available' },
    },
    {
      key: 'note',
      dataKey: 'note',
      title: '备注',
      width: 120,
    },
    {
      key: 'extra_message',
      title: '扩展信息',
      width: 150,
      slots: { default: 'cell-extra_message' },
    },
    {
      key: 'version',
      dataKey: 'version',
      title: '版本',
      width: 80,
    },
    {
      key: 'actions',
      title: '操作',
      width: 150,
      fixed: true,
      align: 'center' as const,
      slots: { default: 'cell-actions' },
    },
  ];
}

/**
 * 手工使用页面表格列配置
 */
export function useManualColumns(): Column[] {
  return [
    {
      key: 'device_type',
      title: '机器类型',
      width: 100,
      align: 'center' as const,
      slots: { default: 'cell-device_type' },
    },
    {
      key: 'ip',
      dataKey: 'ip',
      title: '机器信息',
      width: 140,
    },
    {
      key: 'device_sn',
      dataKey: 'device_sn',
      title: 'SN',
      width: 140,
    },
    {
      key: 'asset_number',
      dataKey: 'asset_number',
      title: '资产编号',
      width: 120,
    },
    {
      key: 'note',
      dataKey: 'note',
      title: '备注',
      width: 150,
    },
    {
      key: 'actions',
      title: '操作',
      width: 150,
      fixed: true,
      align: 'center' as const,
      slots: { default: 'cell-actions' },
    },
  ];
}

/**
 * 新增/编辑表单 Schema（动态）
 */
export function useFormSchema(isMobile: boolean = false): VbenFormSchema[] {
  const schemas: VbenFormSchema[] = [
    {
      component: 'Select',
      fieldName: 'device_type',
      label: '机器类型',
      rules: z.string().min(1, '请选择机器类型'),
      componentProps: {
        options: DEVICE_TYPE_OPTIONS,
      },
      defaultValue: 'windows',
    },
    {
      component: 'Input',
      fieldName: 'asset_number',
      label: '资产编号',
      rules: z.string().min(1, '资产编号必填'),
      componentProps: {
        placeholder: '请输入资产编号，如 A2024582125',
      },
    },
  ];

  if (!isMobile) {
    // Windows/Mac：显示 IP 地址
    schemas.push({
      component: 'Input',
      fieldName: 'ip',
      label: 'IP地址',
      componentProps: {
        placeholder: '请输入IP地址，如 192.168.0.200',
      },
    });
  } else {
    // iOS/Android：显示 SN
    schemas.push({
      component: 'Input',
      fieldName: 'device_sn',
      label: 'SN',
      componentProps: {
        placeholder: '请输入设备SN号',
      },
    });
  }

  schemas.push({
    component: 'Textarea',
    fieldName: 'note',
    label: '备注',
    componentProps: {
      placeholder: '请输入备注信息',
      rows: 3,
    },
  });

  return schemas;
}
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/data.ts
git commit -m "feat(env_machine): 新增表格列和表单 Schema 配置"
```

---

## Task 9: 前端 - 新增表单弹窗组件

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/modules/machine-form-modal.vue`

- [ ] **Step 1: 创建表单弹窗组件**

```vue
<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';

import { ZqDialog } from '#/components/zq-dialog';

import { ElButton, ElMessage } from 'element-plus';

import { useVbenForm } from '#/adapter/form';
import { createEnvMachineApi, updateEnvMachineApi } from '#/api/core/env-machine';
import { isMobileDevice } from '../types';
import { useFormSchema } from '../data';

const props = defineProps<{
  namespace: string;
}>();

const emit = defineEmits(['success']);
const formData = ref<EnvMachine>();
const visible = ref(false);
const confirmLoading = ref(false);

const isMobile = computed(() => {
  const deviceType = formData.value?.device_type || 'windows';
  return isMobileDevice(deviceType as any);
});

const getTitle = computed(() => {
  return formData.value?.id ? '编辑设备' : '新增设备';
});

const [Form, formApi] = useVbenForm({
  layout: 'vertical',
  schema: useFormSchema(false),
  showDefaultActions: false,
});

// 监听设备类型变化，动态切换表单字段
watch(
  () => formApi.form?.values?.device_type,
  (newType) => {
    if (newType) {
      const mobile = isMobileDevice(newType as any);
      formApi.setState({ schema: useFormSchema(mobile) });
    }
  }
);

function resetForm() {
  formApi.resetForm();
  formApi.setValues(formData.value || {});
}

async function onSubmit() {
  const { valid } = await formApi.validate();
  if (!valid) return;

  confirmLoading.value = true;
  const data = await formApi.getValues();

  try {
    if (formData.value?.id) {
      await updateEnvMachineApi(formData.value.id, data);
    } else {
      await createEnvMachineApi({
        ...data,
        namespace: props.namespace,
      });
    }
    visible.value = false;
    emit('success');
    ElMessage.success(formData.value?.id ? '更新成功' : '创建成功');
  } catch (error) {
    ElMessage.error(formData.value?.id ? '更新失败' : '创建失败');
  } finally {
    confirmLoading.value = false;
  }
}

function open(data?: EnvMachine) {
  visible.value = true;
  if (data) {
    formData.value = data;
    // 先设置 schema，再设置值
    const mobile = isMobileDevice(data.device_type as any);
    formApi.setState({ schema: useFormSchema(mobile) });
    setTimeout(() => {
      formApi.setValues(formData.value!);
    }, 0);
  } else {
    formData.value = undefined;
    formApi.setState({ schema: useFormSchema(false) });
    formApi.resetForm();
  }
}

defineExpose({ open });
</script>

<template>
  <ZqDialog
    v-model="visible"
    :title="getTitle"
    :confirm-loading="confirmLoading"
    @confirm="onSubmit"
  >
    <Form class="mx-4" />
    <template #footer-left>
      <ElButton type="primary" @click="resetForm">
        重置
      </ElButton>
    </template>
  </ZqDialog>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/modules/machine-form-modal.vue
git commit -m "feat(env_machine): 新增设备表单弹窗组件"
```

---

## Task 10: 前端 - 新增主页面

**Files:**
- Create: `web/apps/web-ele/src/views/env-machine/index.vue`

- [ ] **Step 1: 创建主页面组件**

```vue
<script lang="ts" setup>
import type { EnvMachine } from '#/api/core/env-machine';

import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { Page } from '@vben/common-ui';
import { Edit, Plus, Trash2 } from '@vben/icons';

import { ElButton, ElMessage, ElMessageBox, ElTag } from 'element-plus';

import { deleteEnvMachineApi, getEnvMachineListApi } from '#/api/core/env-machine';
import { useZqTable } from '#/components/zq-table';

import {
  NAMESPACE_MAP,
  DEVICE_TYPE_OPTIONS,
  STATUS_OPTIONS,
  AVAILABLE_OPTIONS,
} from './types';
import {
  useStandardColumns,
  useStandardSearchFormSchema,
  useManualColumns,
  useManualSearchFormSchema,
} from './data';
import MachineFormModal from './modules/machine-form-modal.vue';

defineOptions({ name: 'EnvMachine' });

const route = useRoute();

// 从路由获取 namespace key
const namespaceKey = computed(() => {
  const path = route.path;
  const key = path.split('/').pop() || 'gamma';
  return key;
});

// 获取实际的 namespace 值
const namespace = computed(() => {
  return NAMESPACE_MAP[namespaceKey.value] || 'meeting_gamma';
});

// 是否为手工使用页面
const isManual = computed(() => namespaceKey.value === 'manual');

// 页面标题
const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    gamma: '集成验证',
    app: 'APP',
    av: '音视频',
    public: '公共设备',
    manual: '手工使用',
  };
  return titles[namespaceKey.value] || '执行机管理';
});

const formModalRef = ref();

// 类型映射
type TagType = 'danger' | 'info' | 'primary' | 'success' | 'warning';

function getTagType(value: any, options: any[]): TagType {
  const option = options.find((o) => o.value === value);
  return (option?.type as TagType) || 'info';
}

function getTagLabel(value: any, options: any[]): string {
  const option = options.find((o) => o.value === value);
  return option?.label || String(value || '-');
}

// 编辑设备
function onEdit(row: EnvMachine) {
  formModalRef.value?.open(row);
}

// 新增设备
function onCreate() {
  formModalRef.value?.open();
}

// 删除单条记录
function onDelete(row: EnvMachine) {
  ElMessageBox.confirm(
    `确定要删除设备 "${row.asset_number || row.ip}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )
    .then(async () => {
      try {
        await deleteEnvMachineApi(row.id);
        ElMessage.success('删除成功');
        gridApi.reload();
      } catch {
        ElMessage.error('删除失败');
      }
    })
    .catch(() => {});
}

// 列表 API
const fetchMachineList = async (params: any) => {
  const res = await getEnvMachineListApi({
    namespace: namespace.value,
    page: params.page.currentPage,
    page_size: params.page.pageSize,
    device_type: params.form?.device_type,
    ip: params.form?.ip,
    asset_number: params.form?.asset_number,
    mark: params.form?.mark,
    available: params.form?.available,
    note: params.form?.note,
  });
  return {
    items: res.items,
    total: res.total,
  };
};

// 使用 ZqTable
const [Grid, gridApi] = useZqTable({
  gridOptions: {
    columns: isManual.value ? useManualColumns() : useStandardColumns(),
    border: true,
    stripe: true,
    showSelection: false,
    showIndex: true,
    proxyConfig: {
      autoLoad: true,
      ajax: {
        query: fetchMachineList,
      },
    },
    pagerConfig: {
      enabled: true,
      pageSize: 20,
    },
    toolbarConfig: {
      search: true,
      refresh: true,
      zoom: true,
      custom: true,
    },
  },
  formOptions: {
    schema: isManual.value
      ? useManualSearchFormSchema()
      : useStandardSearchFormSchema(),
    showCollapseButton: false,
    submitOnChange: false,
  },
});

// 监听路由变化，重新加载
watch(namespaceKey, () => {
  gridApi.reload();
});

// 刷新表格
function refreshGrid() {
  gridApi.reload();
}
</script>

<template>
  <Page auto-content-height :title="pageTitle">
    <MachineFormModal
      ref="formModalRef"
      :namespace="namespace"
      @success="refreshGrid"
    />

    <Grid>
      <!-- 工具栏操作 -->
      <template v-if="isManual" #toolbar-actions>
        <ElButton type="primary" :icon="Plus" @click="onCreate">
          新增设备
        </ElButton>
      </template>

      <!-- 设备类型列 -->
      <template #cell-device_type="{ row }">
        <ElTag type="info" size="small">
          {{ getTagLabel(row.device_type, DEVICE_TYPE_OPTIONS) }}
        </ElTag>
      </template>

      <!-- 状态列 -->
      <template #cell-status="{ row }">
        <ElTag :type="getTagType(row.status, STATUS_OPTIONS)" size="small">
          {{ getTagLabel(row.status, STATUS_OPTIONS) }}
        </ElTag>
      </template>

      <!-- 是否启用列 -->
      <template #cell-available="{ row }">
        <ElTag :type="row.available ? 'success' : 'danger'" size="small">
          {{ row.available ? '是' : '否' }}
        </ElTag>
      </template>

      <!-- 扩展信息列 -->
      <template #cell-extra_message="{ row }">
        <span v-if="!row.extra_message">-</span>
        <span v-else-if="typeof row.extra_message === 'object'">
          {{ JSON.stringify(row.extra_message) }}
        </span>
        <span v-else>{{ row.extra_message }}</span>
      </template>

      <!-- 操作列 -->
      <template #cell-actions="{ row }">
        <ElButton link type="primary" :icon="Edit" @click="onEdit(row)">
          编辑
        </ElButton>
        <ElButton link type="danger" :icon="Trash2" @click="onDelete(row)">
          删除
        </ElButton>
      </template>
    </Grid>
  </Page>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add web/apps/web-ele/src/views/env-machine/index.vue
git commit -m "feat(env_machine): 新增机器管理主页面"
```

---

## Task 11: 前端 - 配置路由

**Files:**
- 后端菜单配置（通过管理后台添加）

- [ ] **Step 1: 在后端管理系统中添加菜单**

菜单配置：
- 一级菜单：设备管理
  - 路径：`/env-machine`
  - 组件：`LAYOUT`

- 二级菜单：
  - 集成验证：`/env-machine/gamma`，组件：`views/env-machine/index`
  - APP：`/env-machine/app`，组件：`views/env-machine/index`
  - 音视频：`/env-machine/av`，组件：`views/env-machine/index`
  - 公共设备：`/env-machine/public`，组件：`views/env-machine/index`
  - 手工使用：`/env-machine/manual`，组件：`views/env-machine/index`

- [ ] **Step 2: 验证路由**

启动前端服务，确认菜单正常显示和跳转：

```bash
cd web && pnpm dev
```

- [ ] **Step 3: 提交（如有前端路由配置文件修改）**

```bash
git add .
git commit -m "feat(env_machine): 配置菜单路由"
```

---

## Task 12: 集成测试

- [ ] **Step 1: 启动后端服务**

```bash
cd backend-fastapi
python main.py
```

- [ ] **Step 2: 启动前端服务**

```bash
cd web
pnpm dev
```

- [ ] **Step 3: 测试功能清单**

- [ ] 3.1 访问五个子菜单页面，确认数据正常加载
- [ ] 3.2 测试筛选功能：机器类型、IP、资产编号、标签、是否启用
- [ ] 3.3 在手工使用页面测试新增设备功能
  - [ ] 新增 Windows/Mac 设备（填写 IP）
  - [ ] 新增 iOS/Android 设备（填写 SN）
- [ ] 3.4 测试编辑功能
- [ ] 3.5 测试删除功能

- [ ] **Step 4: 最终提交**

```bash
git add .
git commit -m "feat(env_machine): 完成机器管理前端页面开发"
```