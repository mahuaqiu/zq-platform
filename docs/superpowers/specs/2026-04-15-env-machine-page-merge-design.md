# 设备管理页面合并设计文档

## 1. 概述

### 1.1 背景
当前设备管理模块包含5个子菜单页面：集成验证、APP、音视频、公共设备、手工使用。其中前4个页面共用同一个组件 `env-machine/index.vue`，仅通过路由参数区分 namespace。这种方式导致：
- 用户需要在不同菜单间切换查看不同分类的设备
- 管理效率较低，无法在一个页面内查看所有设备状态

### 1.2 目标
将集成验证、APP、音视频、公共设备4个页面合并为一个统一的"设备列表"页面，提供全局视角管理设备，同时保留"手工使用"页面独立。

### 1.3 变更范围
- 前端：新增页面组件、调整路由、更新菜单脚本
- 后端：API 参数调整、Service 方法调整
- 文档：CLAUDE.md 更新

## 2. 架构设计

### 2.1 菜单结构变更

**变更前：**
```
设备管理
├── 集成验证 (/env-machine/gamma)
├── APP (/env-machine/app)
├── 音视频 (/env-machine/av)
├── 公共设备 (/env-machine/public)
└── 手工使用 (/env-machine/manual)
```

**变更后：**
```
设备管理
├── 设备列表 (/env-machine/list)
└── 手工使用 (/env-machine/manual)
```

### 2.2 命名空间映射

| Namespace 原值 | 中文显示名 |
|---------------|-----------|
| meeting_gamma | 集成验证 |
| meeting_app | APP |
| meeting_av | 音视频 |
| meeting_public | 公共设备 |
| meeting_manual | 手工使用（独立页面，不在合并范围内） |

## 3. 前端改动

### 3.1 新增页面组件

**文件路径：** `web/apps/web-ele/src/views/env-machine/list.vue`

**基于：** 现有 `index.vue` 改造

**主要变更点：**

1. **筛选区新增命名空间下拉框**
   - 位置：筛选条件首位
   - 选项：
     - 全部（默认值）
     - 集成验证
     - APP
     - 音视频
     - 公共设备
   - 筛选逻辑：
     - 选择"全部"时，不传 namespace 参数（或传空）
     - 选择具体分类时，传对应的 namespace 原值

2. **表格新增命名空间列**
   - 位置：表格首列
   - 显示：中文映射名（集成验证/APP/音视频/公共设备）
   - 宽度：100px

3. **表格列顺序（合并后）：**
   | 序号 | 列名 | 宽度 | 说明 |
   |-----|------|-----|------|
   | 1 | 命名空间 | 100px | 中文显示 |
   | 2 | 机器类型 | 90px | windows/mac/ios/android |
   | 3 | 机器信息 | 120px | IP地址 |
   | 4 | SN | 100px | 设备SN |
   | 5 | 资产编号 | 110px | |
   | 6 | 标签 | 80px | |
   | 7 | 状态 | 60px | 在线/使用中/离线/升级中 |
   | 8 | 是否启用 | 70px | 是/否 |
   | 9 | 备注 | 100px | |
   | 10 | 扩展信息 | 150px | JSON摘要 |
   | 11 | 版本 | 100px | |
   | 12 | 操作 | 160px | 日志/编辑/删除 |

### 3.2 路由配置

**新增路由文件：** `web/apps/web-ele/src/router/routes/modules/env-machine-list.ts`

```typescript
const routes: RouteRecordRaw[] = [
  {
    path: '/env-machine/list',
    name: 'EnvMachineList',
    component: () => import('#/views/env-machine/list.vue'),
    meta: {
      title: '设备列表',
      hideInMenu: true,
    },
  },
];
```

### 3.3 types.ts 更新

**文件路径：** `web/apps/web-ele/src/views/env-machine/types.ts`

**新增内容：**

```typescript
/**
 * 命名空间选项（用于筛选下拉框）
 */
export const NAMESPACE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '集成验证', value: 'meeting_gamma' },
  { label: 'APP', value: 'meeting_app' },
  { label: '音视频', value: 'meeting_av' },
  { label: '公共设备', value: 'meeting_public' },
];

/**
 * 命名空间中文映射（用于表格显示）
 */
export const NAMESPACE_DISPLAY_MAP: Record<string, string> = {
  meeting_gamma: '集成验证',
  meeting_app: 'APP',
  meeting_av: '音视频',
  meeting_public: '公共设备',
};
```

### 3.4 API 更新

**文件路径：** `web/apps/web-ele/src/api/core/env-machine.ts`

**更新接口参数：**
- `getEnvMachineListApi` 的 namespace 参数改为可选，允许传空字符串表示查询全部

## 4. 后端改动

### 4.1 Schema 改动

**文件路径：** `backend-fastapi/core/env_machine/schema.py`

**改动：**
```python
class EnvMachineListRequest(BaseModel):
    """执行机列表查询请求 Schema"""
    namespace: Optional[str] = Field(None, description="机器分类，None表示查询全部")
    device_type: Optional[str] = Field(None, description="机器类型")
    # ... 其他字段保持不变
```

### 4.2 Service 改动

**文件路径：** `backend-fastapi/core/env_machine/service.py`

**改动：**
- `get_list_with_filters` 方法支持 `namespace=None`
- 当 namespace 为 None 时，查询所有4个命名空间（排除 meeting_manual）

```python
async def get_list_with_filters(
    db: AsyncSession,
    namespace: Optional[str] = None,  # 改为 Optional
    # ... 其他参数
) -> Tuple[List[EnvMachine], int]:
    """查询执行机列表，支持多条件筛选"""
    query = select(EnvMachine).where(EnvMachine.is_deleted == False)
    
    if namespace:
        query = query.where(EnvMachine.namespace == namespace)
    else:
        # 查询所有4个命名空间（排除手工使用）
        valid_namespaces = ['meeting_gamma', 'meeting_app', 'meeting_av', 'meeting_public']
        query = query.where(EnvMachine.namespace.in_(valid_namespaces))
    
    # ... 其他筛选条件
```

### 4.3 API 改动

**文件路径：** `backend-fastapi/core/env_machine/api.py`

**改动：**
```python
@router.get("", response_model=PaginatedResponse[EnvMachineResponse], summary="查询执行机列表")
async def list_env_machines(
    namespace: Optional[str] = None,  # 改为 Optional
    device_type: Optional[str] = None,
    # ... 其他参数
) -> PaginatedResponse[EnvMachineResponse]:
    # ... 调用 service
```

## 5. 脚本改动

### 5.1 菜单初始化脚本

**文件路径：** `backend-fastapi/scripts/init_env_machine_menu.py`

**改动：**
```python
MENUS = [
    # 一级菜单（保持不变）
    {
        "id": "env-machine-root",
        "name": "EnvMachine",
        "title": "设备管理",
        "path": "/env-machine",
        "type": "catalog",
        "icon": "ep:monitor",
        "order": 100,
        "parent_id": None,
    },
    # 二级菜单（合并）
    {
        "id": "env-machine-list",
        "name": "EnvMachineList",
        "title": "设备列表",
        "path": "/env-machine/list",
        "type": "menu",
        "component": "/views/env-machine/list",
        "parent_id": "env-machine-root",
        "order": 1,
    },
    {
        "id": "env-machine-manual",
        "name": "EnvMachineManual",
        "title": "手工使用",
        "path": "/env-machine/manual",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 2,
    },
]
```

### 5.2 菜单更新脚本

**新增脚本：** `backend-fastapi/scripts/update_env_machine_menu.py`

**功能：**
- 删除旧的4个子菜单（gamma/app/av/public）
- 创建新的"设备列表"菜单
- 保留"手工使用"菜单

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新执行机管理菜单（合并4个子菜单为设备列表）
执行方式: cd backend-fastapi && python scripts/update_env_machine_menu.py
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from core.menu.model import Menu

# 要删除的旧菜单ID
OLD_MENU_IDS = [
    "env-machine-gamma",
    "env-machine-app",
    "env-machine-av",
    "env-machine-public",
]

# 新菜单配置
NEW_MENUS = [
    {
        "id": "env-machine-list",
        "name": "EnvMachineList",
        "title": "设备列表",
        "path": "/env-machine/list",
        "type": "menu",
        "component": "/views/env-machine/list",
        "parent_id": "env-machine-root",
        "order": 1,
    },
]

async def update_menus():
    """更新菜单"""
    async with AsyncSessionLocal() as session:
        # 1. 删除旧菜单
        for menu_id in OLD_MENU_IDS:
            result = await session.execute(delete(Menu).where(Menu.id == menu_id))
            if result.rowcount > 0:
                print(f"删除菜单: {menu_id}")
        
        # 2. 创建新菜单
        for menu_data in NEW_MENUS:
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
                continue
            
            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"创建菜单: {menu_data['title']}")
        
        # 3. 更新手工使用菜单的order
        result = await session.execute(
            select(Menu).where(Menu.id == "env-machine-manual")
        )
        manual_menu = result.scalar_one_or_none()
        if manual_menu:
            manual_menu.order = 2
            manual_menu.sort = 2
            print(f"更新菜单顺序: 手工使用 -> order=2")
        
        await session.commit()
        print("\n菜单更新完成！")

if __name__ == "__main__":
    asyncio.run(update_menus())
```

## 6. 文档更新

### 6.1 CLAUDE.md 更新

**文件路径：** `CLAUDE.md`

**改动位置：** 核心模块表格中的 `env_machine` 说明

**改动内容：**
```markdown
| 模块 | 说明 |
|------|------|
| env_machine | 执行机管理（设备管理）- 设备列表页面（合并集成验证/APP/音视频/公共设备）、手工使用页面 |
```

### 6.2 初始化脚本说明更新

**文件路径：** `CLAUDE.md`

**改动位置：** 初始化菜单脚本命令列表

**改动内容：**
```markdown
# 初始化菜单脚本
python scripts/init_env_machine_menu.py    # 设备管理菜单（设备列表+手工使用）
# 或使用更新脚本合并旧菜单
python scripts/update_env_machine_menu.py  # 合并4个子菜单为设备列表
```

## 7. 实现顺序

1. **后端改动**（优先，前端依赖）
   - 更新 schema.py
   - 更新 service.py
   - 更新 api.py
   - 测试 API 响应

2. **前端改动**
   - 更新 types.ts
   - 更新 API 接口定义
   - 创建 list.vue 组件
   - 创建路由配置
   - 测试页面功能

3. **脚本改动**
   - 更新 init_env_machine_menu.py
   - 创建 update_env_machine_menu.py
   - 执行更新脚本

4. **文档更新**
   - 更新 CLAUDE.md

## 8. 验收标准

- [ ] 设备列表页面筛选区有命名空间下拉框，默认"全部"
- [ ] 选择"全部"时显示所有4个分类的设备
- [ ] 表格首列显示命名空间中文名称
- [ ] 菜单结构为：设备管理 → 设备列表、手工使用
- [ ] 旧菜单（集成验证/APP/音视频/公共设备）已删除
- [ ] CLAUDE.md 文档已更新
- [ ] 手工使用页面功能保持不变