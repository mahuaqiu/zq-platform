"""IP 模板按 IP 解析，并修复软删除唯一约束。

Revision ID: 20260806_ip_soft_unique
Revises: f9b0c1d2e3f4
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260806_ip_soft_unique"
down_revision: Union[str, None] = "f9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_UNIQUE_FIELDS = (
    "username",
    "gitee_id",
    "github_id",
    "qq_id",
    "google_id",
    "wechat_unionid",
    "microsoft_id",
    "dingtalk_unionid",
    "feishu_union_id",
)


def _create_active_unique_index(index_name: str, table: str, columns: list[str]) -> None:
    op.create_index(
        index_name,
        table,
        columns,
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def upgrade() -> None:
    op.add_column(
        "machine_selection_template",
        sa.Column(
            "machine_targets",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="机器目标快照（IP + 设备类型）",
        ),
    )
    op.execute(
        """
        UPDATE machine_selection_template AS template
        SET machine_targets = resolved.targets
        FROM (
            SELECT source.id,
                   COALESCE(
                       json_agg(
                           json_build_object(
                               'machine_id', machine_id.value,
                               'ip', machine.ip,
                               'device_type', machine.device_type
                           ) ORDER BY machine_id.ordinality
                       ) FILTER (WHERE machine.id IS NOT NULL),
                       '[]'::json
                   ) AS targets
            FROM machine_selection_template AS source
            LEFT JOIN LATERAL json_array_elements_text(source.machine_ids)
                WITH ORDINALITY AS machine_id(value, ordinality) ON true
            LEFT JOIN env_machine AS machine
                ON machine.id = machine_id.value
               AND machine.is_deleted = false
               AND machine.is_virtual = false
            GROUP BY source.id
        ) AS resolved
        WHERE template.id = resolved.id
          AND template.machine_ids IS NOT NULL
        """
    )

    # 历史版本按 namespace 查重，切换 namespace 后可能已产生同物理设备重复行。
    # 优先保留有扩展信息、已启用且最近更新的记录，并同步最新注册信息。
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER identity_window AS keep_id,
                   first_value(namespace) OVER latest_window AS latest_namespace,
                   first_value(port) OVER latest_window AS latest_port,
                   first_value(status) OVER latest_window AS latest_status,
                   first_value(sync_time) OVER latest_window AS latest_sync_time,
                   first_value(version) OVER latest_window AS latest_version,
                   first_value(config_version) OVER latest_window AS latest_config_version,
                   first_value(config_status) OVER latest_window AS latest_config_status,
                   first_value(scripts) OVER latest_window AS latest_scripts,
                   count(*) OVER identity_partition AS duplicate_count
            FROM env_machine
            WHERE is_deleted = false
              AND is_virtual = false
            WINDOW identity_partition AS (PARTITION BY ip, device_type, device_sn),
                   identity_window AS (
                       PARTITION BY ip, device_type, device_sn
                       ORDER BY (
                                    CASE
                                        WHEN json_typeof(extra_message) = 'object'
                                        THEN json_object_length(extra_message)
                                        ELSE 0
                                    END
                                ) DESC,
                                available DESC,
                                sys_update_datetime DESC
                   ),
                   latest_window AS (
                       PARTITION BY ip, device_type, device_sn
                       ORDER BY sync_time DESC, sys_update_datetime DESC
                   )
        )
        UPDATE env_machine AS target
        SET namespace = ranked.latest_namespace,
            port = ranked.latest_port,
            status = ranked.latest_status,
            sync_time = ranked.latest_sync_time,
            version = ranked.latest_version,
            config_version = ranked.latest_config_version,
            config_status = ranked.latest_config_status,
            scripts = ranked.latest_scripts
        FROM ranked
        WHERE target.id = ranked.keep_id
          AND ranked.duplicate_count > 1
        """
    )
    op.execute(
        """
        DELETE FROM env_machine AS target
        USING (
            SELECT id,
                   first_value(id) OVER (
                       PARTITION BY ip, device_type, device_sn
                       ORDER BY (
                                    CASE
                                        WHEN json_typeof(extra_message) = 'object'
                                        THEN json_object_length(extra_message)
                                        ELSE 0
                                    END
                                ) DESC,
                                available DESC,
                                sys_update_datetime DESC
                   ) AS keep_id
            FROM env_machine
            WHERE is_deleted = false
              AND is_virtual = false
        ) AS ranked
        WHERE target.id = ranked.id
          AND ranked.id <> ranked.keep_id
        """
    )
    op.drop_constraint(
        "uq_env_machine_namespace_ip_device", "env_machine", type_="unique"
    )
    op.create_index(
        "uq_env_machine_active_host_identity",
        "env_machine",
        ["ip", "device_type"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND is_virtual = false AND device_sn IS NULL"
        ),
    )
    op.create_index(
        "uq_env_machine_active_device_identity",
        "env_machine",
        ["ip", "device_type", "device_sn"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND is_virtual = false AND device_sn IS NOT NULL"
        ),
    )

    op.drop_constraint("config_template_name_key", "config_template", type_="unique")
    op.drop_constraint(
        "machine_selection_template_name_key",
        "machine_selection_template",
        type_="unique",
    )
    _create_active_unique_index(
        "uq_config_template_active_name", "config_template", ["name"]
    )
    _create_active_unique_index(
        "uq_machine_selection_template_active_name",
        "machine_selection_template",
        ["name"],
    )

    for table, index_name, columns in (
        ("core_role", "ix_core_role_code", ["code"]),
        ("core_dept", "ix_core_dept_code", ["code"]),
        ("core_scheduler_job", "ix_core_scheduler_job_code", ["code"]),
    ):
        op.drop_index(index_name, table_name=table)
        _create_active_unique_index(index_name, table, columns)

    op.drop_constraint("uq_permission_menu_code", "core_permission", type_="unique")
    _create_active_unique_index(
        "uq_permission_menu_code", "core_permission", ["menu_id", "code"]
    )

    for field in USER_UNIQUE_FIELDS:
        index_name = f"ix_core_user_{field}"
        op.drop_index(index_name, table_name="core_user")
        _create_active_unique_index(index_name, "core_user", [field])


def downgrade() -> None:
    for field in USER_UNIQUE_FIELDS:
        index_name = f"ix_core_user_{field}"
        op.drop_index(index_name, table_name="core_user")
        op.create_index(index_name, "core_user", [field], unique=True)

    op.drop_index("uq_permission_menu_code", table_name="core_permission")
    op.create_unique_constraint(
        "uq_permission_menu_code", "core_permission", ["menu_id", "code"]
    )

    for table, index_name, columns in (
        ("core_scheduler_job", "ix_core_scheduler_job_code", ["code"]),
        ("core_dept", "ix_core_dept_code", ["code"]),
        ("core_role", "ix_core_role_code", ["code"]),
    ):
        op.drop_index(index_name, table_name=table)
        op.create_index(index_name, table, columns, unique=True)

    op.drop_index(
        "uq_machine_selection_template_active_name",
        table_name="machine_selection_template",
    )
    op.drop_index("uq_config_template_active_name", table_name="config_template")
    op.create_unique_constraint(
        "machine_selection_template_name_key",
        "machine_selection_template",
        ["name"],
    )
    op.create_unique_constraint(
        "config_template_name_key", "config_template", ["name"]
    )
    op.drop_index(
        "uq_env_machine_active_device_identity", table_name="env_machine"
    )
    op.drop_index("uq_env_machine_active_host_identity", table_name="env_machine")
    op.create_unique_constraint(
        "uq_env_machine_namespace_ip_device",
        "env_machine",
        ["namespace", "ip", "device_type", "device_sn"],
    )
    op.drop_column("machine_selection_template", "machine_targets")
