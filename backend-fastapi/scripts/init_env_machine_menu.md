# 执行机管理菜单配置脚本

## 菜单结构

```
设备管理（一级菜单）
├── 集成验证（namespace: meeting_gamma）
├── APP（namespace: meeting_app）
├── 音视频（namespace: meeting_av）
├── 公共设备（namespace: meeting_public）
└── 手工使用（namespace: meeting_manual）
```

## 方式一：SQL 脚本

执行以下 SQL 语句插入菜单数据（需要替换 UUID）：

```sql
-- 一级菜单：设备管理
INSERT INTO core_menu (
    id, name, title, path, type, icon, "order",
    component, parent_id, sort, is_deleted,
    sys_create_datetime, sys_update_datetime
) VALUES (
    'env-machine-root',  -- 使用固定ID方便引用
    'EnvMachine',
    '设备管理',
    '/env-machine',
    'catalog',
    'ep:monitor',
    100,
    NULL,
    NULL,
    100,
    false,
    NOW(),
    NOW()
);

-- 二级菜单：集成验证
INSERT INTO core_menu (
    id, name, title, path, type, component, parent_id, "order", sort, is_deleted,
    sys_create_datetime, sys_update_datetime
) VALUES (
    'env-machine-gamma',
    'EnvMachineGamma',
    '集成验证',
    '/env-machine/gamma',
    'menu',
    '/views/env-machine/index',
    'env-machine-root',
    1,
    1,
    false,
    NOW(),
    NOW()
);

-- 二级菜单：APP
INSERT INTO core_menu (
    id, name, title, path, type, component, parent_id, "order", sort, is_deleted,
    sys_create_datetime, sys_update_datetime
) VALUES (
    'env-machine-app',
    'EnvMachineApp',
    'APP',
    '/env-machine/app',
    'menu',
    '/views/env-machine/index',
    'env-machine-root',
    2,
    2,
    false,
    NOW(),
    NOW()
);

-- 二级菜单：音视频
INSERT INTO core_menu (
    id, name, title, path, type, component, parent_id, "order", sort, is_deleted,
    sys_create_datetime, sys_update_datetime
) VALUES (
    'env-machine-av',
    'EnvMachineAv',
    '音视频',
    '/env-machine/av',
    'menu',
    '/views/env-machine/index',
    'env-machine-root',
    3,
    3,
    false,
    NOW(),
    NOW()
);

-- 二级菜单：公共设备
INSERT INTO core_menu (
    id, name, title, path, type, component, parent_id, "order", sort, is_deleted,
    sys_create_datetime, sys_update_datetime
) VALUES (
    'env-machine-public',
    'EnvMachinePublic',
    '公共设备',
    '/env-machine/public',
    'menu',
    '/views/env-machine/index',
    'env-machine-root',
    4,
    4,
    false,
    NOW(),
    NOW()
);

-- 二级菜单：手工使用
INSERT INTO core_menu (
    id, name, title, path, type, component, parent_id, "order", sort, is_deleted,
    sys_create_datetime, sys_update_datetime
) VALUES (
    'env-machine-manual',
    'EnvMachineManual',
    '手工使用',
    '/env-machine/manual',
    'menu',
    '/views/env-machine/index',
    'env-machine-root',
    5,
    5,
    false,
    NOW(),
    NOW()
);
```

## 方式二：Python 脚本

将以下脚本保存为 `scripts/init_env_machine_menu.py` 并执行：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化执行机管理菜单
执行方式: python scripts/init_env_machine_menu.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_factory
from core.menu.model import Menu


# 菜单配置数据
MENUS = [
    # 一级菜单
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
    # 二级菜单
    {
        "id": "env-machine-gamma",
        "name": "EnvMachineGamma",
        "title": "集成验证",
        "path": "/env-machine/gamma",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 1,
    },
    {
        "id": "env-machine-app",
        "name": "EnvMachineApp",
        "title": "APP",
        "path": "/env-machine/app",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 2,
    },
    {
        "id": "env-machine-av",
        "name": "EnvMachineAv",
        "title": "音视频",
        "path": "/env-machine/av",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 3,
    },
    {
        "id": "env-machine-public",
        "name": "EnvMachinePublic",
        "title": "公共设备",
        "path": "/env-machine/public",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 4,
    },
    {
        "id": "env-machine-manual",
        "name": "EnvMachineManual",
        "title": "手工使用",
        "path": "/env-machine/manual",
        "type": "menu",
        "component": "/views/env-machine/index",
        "parent_id": "env-machine-root",
        "order": 5,
    },
]


async def init_menus():
    """初始化菜单"""
    async with async_session_factory() as session:
        for menu_data in MENUS:
            # 检查菜单是否已存在
            result = await session.execute(
                select(Menu).where(Menu.id == menu_data["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"菜单已存在，跳过: {menu_data['title']}")
                continue

            # 创建新菜单
            menu = Menu(
                id=menu_data["id"],
                name=menu_data["name"],
                title=menu_data["title"],
                path=menu_data["path"],
                type=menu_data["type"],
                icon=menu_data.get("icon"),
                component=menu_data.get("component"),
                parent_id=menu_data.get("parent_id"),
                order=menu_data.get("order", 0),
                sort=menu_data.get("order", 0),
            )
            session.add(menu)
            print(f"创建菜单: {menu_data['title']}")

        await session.commit()
        print("\n菜单初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_menus())
```

## 方式三：通过 API 调用

使用 curl 命令调用菜单创建 API（需要先登录获取 token）：

```bash
#!/bin/bash
# 文件: scripts/init_env_machine_menu.sh

# 配置
BASE_URL="http://localhost:8000"
TOKEN="<your_jwt_token>"  # 替换为实际的 token

# 创建一级菜单
ROOT_ID=$(curl -s -X POST "${BASE_URL}/api/core/menu" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "EnvMachine",
    "title": "设备管理",
    "path": "/env-machine",
    "type": "catalog",
    "icon": "ep:monitor",
    "order": 100
  }' | jq -r '.id')

echo "创建一级菜单: ${ROOT_ID}"

# 创建二级菜单
curl -s -X POST "${BASE_URL}/api/core/menu" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"${ROOT_ID}\", \"name\": \"EnvMachineGamma\", \"title\": \"集成验证\", \"path\": \"/env-machine/gamma\", \"type\": \"menu\", \"component\": \"/views/env-machine/index\", \"order\": 1}"

curl -s -X POST "${BASE_URL}/api/core/menu" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"${ROOT_ID}\", \"name\": \"EnvMachineApp\", \"title\": \"APP\", \"path\": \"/env-machine/app\", \"type\": \"menu\", \"component\": \"/views/env-machine/index\", \"order\": 2}"

curl -s -X POST "${BASE_URL}/api/core/menu" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"${ROOT_ID}\", \"name\": \"EnvMachineAv\", \"title\": \"音视频\", \"path\": \"/env-machine/av\", \"type\": \"menu\", \"component\": \"/views/env-machine/index\", \"order\": 3}"

curl -s -X POST "${BASE_URL}/api/core/menu" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"${ROOT_ID}\", \"name\": \"EnvMachinePublic\", \"title\": \"公共设备\", \"path\": \"/env-machine/public\", \"type\": \"menu\", \"component\": \"/views/env-machine/index\", \"order\": 4}"

curl -s -X POST "${BASE_URL}/api/core/menu" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"parent_id\": \"${ROOT_ID}\", \"name\": \"EnvMachineManual\", \"title\": \"手工使用\", \"path\": \"/env-machine/manual\", \"type\": \"menu\", \"component\": \"/views/env-machine/index\", \"order\": 5}"

echo "菜单创建完成！"
```

## 注意事项

1. **权限配置**：菜单创建后，需要在角色管理中为相应角色分配这些菜单权限
2. **菜单名称唯一**：`name` 字段必须唯一，用于前端路由
3. **组件路径**：`component` 指向 `views/env-machine/index.vue`，所有二级菜单共用同一个组件
4. **路由区分**：前端通过路由路径的最后一段（gamma/app/av/public/manual）来区分不同的 namespace

## 执行顺序

1. 确保后端服务已启动
2. 确保数据库连接正常
3. 执行上述任意一种脚本
4. 刷新前端页面，菜单应自动显示