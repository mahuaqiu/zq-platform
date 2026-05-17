#!/usr/bin/env python
import asyncio
from app.database import AsyncSessionLocal
from core.performance_monitor.model import ExportTask
from sqlalchemy import select

async def check_task():
    async with AsyncSessionLocal() as db:
        stmt = select(ExportTask).where(ExportTask.is_deleted == False).order_by(ExportTask.sys_create_datetime.desc()).limit(5)
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        for t in tasks:
            print(f"ID: {t.id}, Status: {t.status}, FilePath: {t.file_path}, Progress: {t.progress}")

asyncio.run(check_task())