# 机器管理前端页面设计

## 概述

机器管理模块用于管理不同命名空间下的设备信息，包括集成验证、APP、音视频、公共设备和手工使用五个子模块。

## 菜单结构

```
设备管理（一级菜单）
├── 集成验证（namespace: meeting_gamma）
├── APP（namespace: meeting_app）
├── 音视频（namespace: meeting_av）
├── 公共设备（namespace: meeting_public）
└── 手工使用（namespace: meeting_manual）
```

## 后端配合工作

### 1. 新增字段

在 `env_machine` 表新增 `asset_number` 字段：

```python
# model.py
asset_number = Column(String(32), nullable=True, comment="资产编号")
```

### 2. 新增 CRUD API

后端现有 API（`/register`、`/release` 等）用于执行机业务逻辑，前端管理页面需要新增 CRUD API：

```python
# api.py 新增以下端点

@router.get("", response_model=PaginatedResponse[EnvMachineResponse])
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
):
    """查询执行机列表"""
    pass

@router.post("", response_model=EnvMachineResponse)
async def create_env_machine(
    data: EnvMachineCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """新增执行机（手工使用）"""
    pass

@router.put("/{machine_id}", response_model=EnvMachineResponse)
async def update_env_machine(
    machine_id: str,
    data: EnvMachineUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新执行机"""
    pass

@router.delete("/{machine_id}")
async def delete_env_machine(
    machine_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除执行机"""
    pass
```

### 3. 更新 Schema

```python
# schema.py 新增

class EnvMachineCreateRequest(BaseModel):
    """新增执行机请求"""
    namespace: str
    device_type: str  # windows/mac/ios/android
    asset_number: str  # 必填
    ip: Optional[str] = None  # Windows/Mac 可选
    device_sn: Optional[str] = None  # iOS/Android 可选
    note: Optional[str] = None

class EnvMachineUpdateRequest(BaseModel):
    """更新执行机请求"""
    asset_number: Optional[str] = None
    ip: Optional[str] = None
    device_sn: Optional[str] = None
    mark: Optional[str] = None
    available: Optional[bool] = None
    note: Optional[str] = None
```

## 数据模型

### 字段列表（后端实际字段名）

| 后端字段 | 前端显示 | 类型 | 说明 |
|----------|----------|------|------|
| `device_type` | 机器类型 | String | Windows/Mac/iOS/Android |
| `ip` | 机器信息 | String | IP地址，如 192.168.0.200 |
| `port` | - | String | 端口（表格不展示） |
| `device_sn` | SN | String | 设备序列号 |
| `asset_number` | 资产编号 | String | **新增字段**，如 A2024582125 |
| `mark` | 标签 | String | 标签，如 windows、web |
| `status` | 状态 | String | online/using/offline |
| `available` | 是否启用 | Boolean | true/false |
| `note` | 备注 | Text | 备注信息 |
| `extra_message` | 扩展信息 | JSON | 扩展信息 |
| `version` | 版本 | String | 版本号 |
| `namespace` | - | String | 命名空间（路由参数） |

## 页面设计

### 1. 集成验证/APP/音视频/公共设备页面

四个页面使用相同的表格组件，仅 `namespace` 参数不同。

#### 筛选条件

| 前端字段 | 后端字段 | 类型 | 查询方式 |
|----------|----------|------|----------|
| 机器类型 | device_type | 下拉选择 | 精确匹配 |
| 机器信息 | ip | 输入框 | 模糊查询 |
| 资产编号 | asset_number | 输入框 | 模糊查询 |
| 标签 | mark | 输入框 | 模糊查询 |
| 是否启用 | available | 下拉选择 | 精确匹配 |

#### 表格列

| 列名 | 后端字段 | 说明 |
|------|----------|------|
| 机器类型 | device_type | Windows/Mac/iOS/Android |
| 机器信息 | ip | IP地址（移动端显示 "-"） |
| SN | device_sn | 设备序列号 |
| 资产编号 | asset_number | 资产编号 |
| 标签 | mark | 纯文本显示，不带颜色标签 |
| 状态 | status | 在线/离线，带颜色 |
| 是否启用 | available | 是/否，带颜色 |
| 备注 | note | 备注信息 |
| 扩展信息 | extra_message | JSON 格式化显示 |
| 版本 | version | 版本号 |
| 操作 | - | 编辑、删除按钮 |

### 2. 手工使用页面

特殊页面，支持新增设备功能。

#### 筛选条件

| 前端字段 | 后端字段 | 类型 | 查询方式 |
|----------|----------|------|----------|
| 机器类型 | device_type | 下拉选择 | 精确匹配 |
| 机器信息 | ip | 输入框 | 模糊查询 |
| 资产编号 | asset_number | 输入框 | 模糊查询 |
| 备注 | note | 输入框 | 模糊查询 |

#### 表格列

| 列名 | 后端字段 | 说明 |
|------|----------|------|
| 机器类型 | device_type | Windows/Mac/iOS/Android |
| 机器信息 | ip | IP地址（移动端显示 "-"） |
| SN | device_sn | 设备序列号 |
| 资产编号 | asset_number | 资产编号 |
| 备注 | note | 备注信息 |
| 操作 | - | 编辑、删除按钮 |

### 3. 新增设备弹窗

根据机器类型（device_type）动态切换表单字段。

#### Windows/Mac 类型

| 前端字段 | 后端字段 | 类型 | 必填 | 说明 |
|----------|----------|------|------|------|
| 机器类型 | device_type | 下拉选择 | 是 | Windows/Mac/iOS/Android |
| 资产编号 | asset_number | 输入框 | 是 | 如 A2024582125 |
| IP地址 | ip | 输入框 | 否 | 如 192.168.0.200 |
| 备注 | note | 文本域 | 否 | 备注信息 |

#### iOS/Android 类型

| 前端字段 | 后端字段 | 类型 | 必填 | 说明 |
|----------|----------|------|------|------|
| 机器类型 | device_type | 下拉选择 | 是 | Windows/Mac/iOS/Android |
| 资产编号 | asset_number | 输入框 | 是 | 如 A2024582125 |
| SN | device_sn | 输入框 | 否 | 设备序列号 |
| 备注 | note | 文本域 | 否 | 备注信息 |

> 注：移动端设备不显示 IP 地址字段。

## 组件设计

### 文件结构

```
web/apps/web-ele/src/views/env-machine/
├── index.vue                    # 主入口（路由页面）
├── data.ts                      # 表单Schema、表格列配置
├── types.ts                     # TypeScript 类型定义
├── api.ts                       # API 接口定义
└── modules/
    ├── machine-list.vue         # 列表组件（通用）
    └── machine-form-modal.vue   # 新增/编辑弹窗
```

### 路由配置

后端菜单配置五个子菜单，前端根据路由参数 `namespace` 加载不同数据：

```
/env-machine/gamma   → namespace: meeting_gamma
/env-machine/app     → namespace: meeting_app
/env-machine/av      → namespace: meeting_av
/env-machine/public  → namespace: meeting_public
/env-machine/manual  → namespace: meeting_manual
```

### API 接口

```typescript
// 获取设备列表
GET /api/core/env?namespace={namespace}&page=1&page_size=20

// 查询参数
interface MachineQueryParams {
  namespace: string;
  device_type?: string;
  ip?: string;           // 模糊查询
  asset_number?: string; // 模糊查询
  mark?: string;         // 模糊查询
  available?: boolean;
  note?: string;         // 模糊查询（仅手工使用）
  page: number;
  page_size: number;
}

// 新增设备
POST /api/core/env

// 编辑设备
PUT /api/core/env/{id}

// 删除设备
DELETE /api/core/env/{id}
```

## 实现要点

1. **组件复用**：五个子页面使用同一个列表组件，通过路由参数区分
2. **动态表单**：新增弹窗根据机器类型（device_type）动态显示/隐藏字段
3. **字段映射**：使用后端实际字段名（device_type、device_sn、mark、available、note、extra_message）
4. **标签样式**：标签列使用纯文本显示，不带颜色标签样式
5. **机器信息显示**：仅显示 IP 地址（ip 字段），移动端设备显示 "-"
6. **后端配合**：需要后端新增 `asset_number` 字段和 CRUD API 端点