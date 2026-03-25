"""drop_unused_tables

Revision ID: fd586a9cc5ef
Revises: 4d672ac66c71
Create Date: 2026-03-25 21:50:21.320440

删除不再使用的模块表：
- core_file_manager (文件管理)
- core_message (消息中心)
- core_scheduler_job (定时任务)
- core_scheduler_log (定时任务日志)
- core_page_manager (页面管理) - 如果存在

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'fd586a9cc5ef'
down_revision: Union[str, None] = '4d672ac66c71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除菜单数据（先删除子菜单，再删除父菜单）
    # 删除消息中心相关菜单
    op.execute("DELETE FROM core_menu WHERE path LIKE '/message%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-tools/message%'")

    # 删除定时任务相关菜单
    op.execute("DELETE FROM core_menu WHERE path LIKE '/scheduler%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-tools/scheduler%'")

    # 删除系统工具相关菜单（文件管理、数据源、数据库管理、Redis管理）
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-tools/file%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-tools/data-source%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-tools/database%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-tools/redis%'")

    # 删除系统监控相关菜单（Redis监控、Server监控、数据库监控）
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-monitor/redis%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-monitor/server%'")
    op.execute("DELETE FROM core_menu WHERE path LIKE '/system-monitor/database%'")

    # 删除在线开发相关菜单（页面管理）
    op.execute("DELETE FROM core_menu WHERE path LIKE '/online-development/page%'")

    # 删除系统工具、系统监控、在线开发、消息中心父菜单
    op.execute("DELETE FROM core_menu WHERE name = 'SystemTools'")
    op.execute("DELETE FROM core_menu WHERE name = 'SystemMonitor'")
    op.execute("DELETE FROM core_menu WHERE name = 'OnlineDevelopment'")
    op.execute("DELETE FROM core_menu WHERE name = 'MessageCenter'")

    # 删除权限表中关联已删除菜单的权限
    op.execute("DELETE FROM core_permission WHERE menu_id NOT IN (SELECT id FROM core_menu)")

    # 删除角色-菜单关联表中已删除菜单的关联
    op.execute("DELETE FROM core_role_menu WHERE menu_id NOT IN (SELECT id FROM core_menu)")

    # 删除定时任务日志表
    op.execute("DROP TABLE IF EXISTS core_scheduler_log")

    # 删除定时任务表
    op.execute("DROP TABLE IF EXISTS core_scheduler_job")

    # 删除消息表
    op.execute("DROP TABLE IF EXISTS core_message")

    # 删除文件管理表
    op.execute("DROP TABLE IF EXISTS core_file_manager")

    # 删除页面管理表（如果存在）
    op.execute("DROP TABLE IF EXISTS core_page_manager")


def downgrade() -> None:
    # 重新创建文件管理表
    op.execute("""
        CREATE TABLE IF NOT EXISTS core_file_manager (
            name VARCHAR(255) NOT NULL,
            type VARCHAR(10),
            parent_id VARCHAR(36),
            path TEXT NOT NULL,
            size BIGINT,
            file_ext VARCHAR(50),
            mime_type VARCHAR(200),
            storage_type VARCHAR(20),
            storage_path TEXT NOT NULL,
            url TEXT,
            thumbnail_url TEXT,
            md5 VARCHAR(32),
            is_public BOOLEAN,
            download_count INTEGER,
            id VARCHAR(21) NOT NULL PRIMARY KEY,
            sort INTEGER,
            is_deleted BOOLEAN,
            sys_create_datetime TIMESTAMP DEFAULT now(),
            sys_update_datetime TIMESTAMP DEFAULT now(),
            sys_creator_id VARCHAR(21),
            sys_modifier_id VARCHAR(21)
        )
    """)

    # 重新创建消息表
    op.execute("""
        CREATE TABLE IF NOT EXISTS core_message (
            recipient_id VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            msg_type VARCHAR(20),
            status VARCHAR(20),
            link_type VARCHAR(50),
            link_id VARCHAR(50),
            read_at TIMESTAMP,
            sender_id VARCHAR(50),
            id VARCHAR(21) NOT NULL PRIMARY KEY,
            sort INTEGER,
            is_deleted BOOLEAN,
            sys_create_datetime TIMESTAMP DEFAULT now(),
            sys_update_datetime TIMESTAMP DEFAULT now(),
            sys_creator_id VARCHAR(21),
            sys_modifier_id VARCHAR(21)
        )
    """)

    # 重新创建定时任务表
    op.execute("""
        CREATE TABLE IF NOT EXISTS core_scheduler_job (
            name VARCHAR(128) NOT NULL,
            code VARCHAR(128) NOT NULL UNIQUE,
            description TEXT,
            "group" VARCHAR(64),
            trigger_type VARCHAR(20),
            cron_expression VARCHAR(128),
            interval_seconds INTEGER,
            run_date TIMESTAMP,
            task_func VARCHAR(256) NOT NULL,
            task_args TEXT,
            task_kwargs TEXT,
            status INTEGER,
            priority INTEGER,
            max_instances INTEGER,
            max_retries INTEGER,
            timeout INTEGER,
            coalesce BOOLEAN,
            allow_concurrent BOOLEAN,
            total_run_count INTEGER,
            success_count INTEGER,
            failure_count INTEGER,
            last_run_time TIMESTAMP,
            next_run_time TIMESTAMP,
            last_run_status VARCHAR(20),
            last_run_result TEXT,
            remark TEXT,
            id VARCHAR(21) NOT NULL PRIMARY KEY,
            sort INTEGER,
            is_deleted BOOLEAN,
            sys_create_datetime TIMESTAMP DEFAULT now(),
            sys_update_datetime TIMESTAMP DEFAULT now(),
            sys_creator_id VARCHAR(21),
            sys_modifier_id VARCHAR(21)
        )
    """)

    # 重新创建定时任务日志表
    op.execute("""
        CREATE TABLE IF NOT EXISTS core_scheduler_log (
            job_id VARCHAR(36) NOT NULL,
            job_name VARCHAR(128) NOT NULL,
            job_code VARCHAR(128) NOT NULL,
            status VARCHAR(20),
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration FLOAT,
            result TEXT,
            exception TEXT,
            traceback TEXT,
            hostname VARCHAR(128),
            process_id INTEGER,
            retry_count INTEGER,
            id VARCHAR(21) NOT NULL PRIMARY KEY,
            sort INTEGER,
            is_deleted BOOLEAN,
            sys_create_datetime TIMESTAMP DEFAULT now(),
            sys_update_datetime TIMESTAMP DEFAULT now(),
            sys_creator_id VARCHAR(21),
            sys_modifier_id VARCHAR(21)
        )
    """)