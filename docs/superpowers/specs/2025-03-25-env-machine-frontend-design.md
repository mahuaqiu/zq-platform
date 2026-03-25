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

## 数据模型

### 后端新增字段

- `asset_number`: 资产编号，字符串类型，如 `A2024582125`
- `namespace`: 命名空间，用于区分不同类型的设备

### 字段列表

| 字段 | 说明 | 示例 |
|------|------|------|
| machine_type | 机器类型 | Windows/Mac/iOS/Android |
| ip | IP地址 | 192.168.0.200 |
| port | 端口（手工使用场景不使用） | 8088 |
| sn | 设备SN号 | ABC123DEF456 |
| asset_number | 资产编号 | A2024582125 |
| tag | 标签 | windows、web |
| status | 状态 | 在线/离线 |
| is_enabled | 是否启用 | true/false |
| remark | 备注 | 临时测试机 |
| extra_info | 扩展信息 | CPU: i7, RAM: 16G |
| version | 版本 | v1.2.0 |

## 页面设计

### 1. 集成验证/APP/音视频/公共设备页面

四个页面使用相同的表格组件，仅 `namespace` 参数不同。

#### 筛选条件

| 字段 | 类型 | 查询方式 |
|------|------|----------|
| 机器类型 | 下拉选择 | 精确匹配 |
| 机器信息 | 输入框 | 模糊查询IP |
| 资产编号 | 输入框 | 模糊查询 |
| 标签 | 输入框 | 模糊查询 |
| 是否启用 | 下拉选择 | 精确匹配 |

#### 表格列

| 列名 | 说明 |
|------|------|
| 机器类型 | Windows/Mac/iOS/Android |
| 机器信息 | IP地址显示（移动端显示 "-"） |
| SN | 设备序列号 |
| 资产编号 | 资产编号 |
| 标签 | 纯文本显示，不带颜色标签 |
| 状态 | 在线/离线，带颜色 |
| 是否启用 | 是/否，带颜色 |
| 备注 | 备注信息 |
| 扩展信息 | 扩展信息 |
| 版本 | 版本号 |
| 操作 | 编辑、删除按钮 |

### 2. 手工使用页面

特殊页面，支持新增设备功能。

#### 筛选条件

| 字段 | 类型 | 查询方式 |
|------|------|----------|
| 机器类型 | 下拉选择 | 精确匹配 |
| 机器信息 | 输入框 | 模糊查询IP |
| 资产编号 | 输入框 | 模糊查询 |
| 备注 | 输入框 | 模糊查询 |

> 注：手工使用页面的"资产编号"实际复用后端的 `tag` 字段存储。

#### 表格列

| 列名 | 说明 |
|------|------|
| 机器类型 | Windows/Mac/iOS/Android |
| 机器信息 | IP地址显示（移动端显示 "-"） |
| SN | 设备序列号 |
| 资产编号 | 资产编号（实际存储在 tag 字段） |
| 备注 | 备注信息 |
| 操作 | 编辑、删除按钮 |

### 3. 新增设备弹窗

根据机器类型动态切换表单字段。

#### Windows/Mac 类型

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 机器类型 | 下拉选择 | 是 | Windows/Mac/iOS/Android |
| 资产编号 | 输入框 | 是 | 如 A2024582125 |
| IP地址 | 输入框 | 否 | 如 192.168.0.200 |
| 备注 | 文本域 | 否 | 备注信息 |

#### iOS/Android 类型

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 机器类型 | 下拉选择 | 是 | Windows/Mac/iOS/Android |
| 资产编号 | 输入框 | 是 | 如 A2024582125 |
| SN | 输入框 | 否 | 设备序列号 |
| 备注 | 文本域 | 否 | 备注信息 |

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
GET /api/core/env-machine?namespace={namespace}&page=1&pageSize=20

// 查询参数
interface MachineQueryParams {
  namespace: string;
  machine_type?: string;
  ip?: string;           // 模糊查询
  asset_number?: string; // 模糊查询
  tag?: string;          // 模糊查询
  is_enabled?: boolean;
  remark?: string;       // 模糊查询（仅手工使用）
  page: number;
  pageSize: number;
}

// 新增设备
POST /api/core/env-machine

// 编辑设备
PUT /api/core/env-machine/{id}

// 删除设备
DELETE /api/core/env-machine/{id}
```

## 实现要点

1. **组件复用**：五个子页面使用同一个列表组件，通过路由参数区分
2. **动态表单**：新增弹窗根据机器类型动态显示/隐藏字段
3. **字段映射**：手工使用页面的"资产编号"使用 `tag` 字段存储
4. **标签样式**：标签列使用纯文本显示，不带颜色标签样式
5. **机器信息显示**：仅显示 IP 地址，端口不在手工使用场景展示