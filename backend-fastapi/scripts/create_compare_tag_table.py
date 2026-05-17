#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创建 performance_compare_tag 表的脚本（使用相对时间）
"""
import asyncio
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


async def create_table():
    """创建 performance_compare_tag 表"""
    async with engine.begin() as conn:
        # 删除旧表（如果存在）
        await conn.execute(text("DROP TABLE IF EXISTS performance_compare_tag CASCADE"))
        print("已删除旧表（如果存在）")

        # 创建新表
        await conn.execute(text("""
            CREATE TABLE performance_compare_tag (
                id VARCHAR(50) NOT NULL PRIMARY KEY,
                sort INTEGER DEFAULT 0,
                is_deleted BOOLEAN DEFAULT false,
                sys_create_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sys_update_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sys_creator_id VARCHAR(50),
                sys_modifier_id VARCHAR(50),
                name VARCHAR(100) NOT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'peak',
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                note TEXT
            )
        """))
        print("已创建 performance_compare_tag 表（使用相对时间）")


async def main():
    print("开始创建 performance_compare_tag 表...")
    await create_table()
    print("完成！")


if __name__ == "__main__":
    asyncio.run(main())