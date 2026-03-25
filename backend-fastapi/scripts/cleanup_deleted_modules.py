"""
清理数据库中已删除模块的菜单和表
运行方式: cd backend-fastapi && python scripts/cleanup_deleted_modules.py
"""
import asyncio
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import AsyncSessionLocal, engine


async def cleanup_menus():
    """清理菜单数据"""
    async with AsyncSessionLocal() as db:
        deleted_count = 0

        # 需要删除的路径前缀（菜单路径）
        paths_to_delete = [
            '/tool',
            '/monitor',
            '/moniter',
            '/message',
            '/scheduler',
            '/database',
            '/online-development',
            '/data-source',
            '/system/dict',
            '/dict',
        ]

        # 1. 先删除所有子菜单的关联
        print("=== 步骤1: 删除角色-菜单关联 ===")
        for path in paths_to_delete:
            result = await db.execute(
                text("""
                    DELETE FROM core_role_menu WHERE menu_id IN (
                        SELECT id FROM core_menu WHERE path LIKE :path
                    )
                """),
                {"path": f"{path}%"},
            )
            if result.rowcount > 0:
                print(f"  删除角色-菜单关联 (路径 {path}%): {result.rowcount} 条")

        # 2. 删除权限
        print("\n=== 步骤2: 删除权限 ===")
        for path in paths_to_delete:
            result = await db.execute(
                text("""
                    DELETE FROM core_permission WHERE menu_id IN (
                        SELECT id FROM core_menu WHERE path LIKE :path
                    )
                """),
                {"path": f"{path}%"},
            )
            if result.rowcount > 0:
                print(f"  删除权限 (路径 {path}%): {result.rowcount} 条")

        # 3. 删除菜单（先删除子菜单，再删除父菜单）
        print("\n=== 步骤3: 删除菜单 ===")
        for path in paths_to_delete:
            result = await db.execute(
                text("DELETE FROM core_menu WHERE path LIKE :path"),
                {"path": f"{path}%"},
            )
            if result.rowcount > 0:
                print(f"  删除菜单 (路径 {path}%): {result.rowcount} 条")
                deleted_count += result.rowcount

        # 4. 按名称删除可能遗漏的菜单
        print("\n=== 步骤4: 按名称删除菜单 ===")
        names_to_delete = [
            'scheduler', 'scheduled', 'filemanager', 'file-manager', 'filemanager',
            'redis', 'server-monitor', 'servermonitor', 'database-monitor', 'databasemonitor',
            'page-manager', 'pagemanager', 'message', 'data-source', 'datasource',
            'dict', 'dictionary', 'systemtools', 'systemmonitor',
            'databasemanagement', 'databasemanager', 'redismanagement', 'redismanager',
            'onlinedevelopment', 'online-development', 'messagecenter',
        ]

        for name in names_to_delete:
            result = await db.execute(
                text("DELETE FROM core_menu WHERE LOWER(name) LIKE :name"),
                {"name": f"%{name}%"},
            )
            if result.rowcount > 0:
                print(f"  删除菜单 (名称包含 {name}): {result.rowcount} 条")
                deleted_count += result.rowcount

        # 5. 按标题删除菜单
        print("\n=== 步骤5: 按标题删除菜单 ===")
        titles_to_delete = [
            'databasemanagement', 'systemmonitoring', 'systemtools',
            'filemanagement', 'scheduledtasks', 'redimonitoring', 'servermonitoring',
            'databasemonitoring', 'pagemanagement', 'datasource',
            'messagemanagement', 'messagecenter', 'dictionarymanagement',
        ]

        for title in titles_to_delete:
            result = await db.execute(
                text("DELETE FROM core_menu WHERE LOWER(title) LIKE :title"),
                {"title": f"%{title}%"},
            )
            if result.rowcount > 0:
                print(f"  删除菜单 (标题包含 {title}): {result.rowcount} 条")
                deleted_count += result.rowcount

        await db.commit()
        print(f"\n=== 总共删除了 {deleted_count} 个菜单项 ===")


async def drop_tables():
    """删除不再使用的表"""
    tables_to_drop = [
        'core_scheduler_log',
        'core_scheduler_job',
        'core_message',
        'core_file_manager',
        'core_page_manager',
        'core_dict_item',
        'core_dict',
    ]

    print("\n=== 步骤6: 删除数据库表 ===")
    async with engine.begin() as conn:
        for table in tables_to_drop:
            try:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                print(f"  已删除表: {table}")
            except Exception as e:
                print(f"  删除表 {table} 失败: {e}")


async def show_remaining_menus():
    """显示剩余的菜单"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT id, name, path, title FROM core_menu ORDER BY path")
        )
        rows = result.fetchall()
        print("\n=== 剩余菜单列表 ===")
        for row in rows:
            print(f"  {row[1]}: {row[2]}")


async def main():
    print("=" * 60)
    print("开始清理数据库...")
    print("=" * 60)

    await cleanup_menus()
    await drop_tables()
    await show_remaining_menus()

    print("\n" + "=" * 60)
    print("清理完成！请刷新前端页面查看效果。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())