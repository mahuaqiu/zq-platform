"""补全 IP 模板中的设备 SN 身份。

Revision ID: 20260807_target_device_sn
Revises: 20260806_ip_soft_unique
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260807_target_device_sn"
down_revision: Union[str, None] = "20260806_ip_soft_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为仍可定位的旧模板目标补充 SN，避免多移动设备误匹配。"""
    op.execute(
        """
        UPDATE env_machine
        SET device_sn = NULL
        WHERE device_sn IS NOT NULL
          AND btrim(device_sn) = ''
          AND is_deleted = false
        """
    )
    op.execute(
        """
        WITH migrated AS (
            SELECT template.id,
                   jsonb_agg(
                       CASE
                           WHEN machine.id IS NULL THEN target.value
                           ELSE target.value || jsonb_build_object(
                               'device_sn', machine.device_sn
                           )
                       END
                       ORDER BY target.ordinality
                   ) AS targets
            FROM machine_selection_template AS template
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(template.machine_targets::jsonb, '[]'::jsonb)
            ) WITH ORDINALITY AS target(value, ordinality)
            LEFT JOIN env_machine AS machine
              ON machine.id::text = target.value->>'machine_id'
             AND machine.is_deleted = false
             AND machine.is_virtual = false
            GROUP BY template.id
        )
        UPDATE machine_selection_template AS template
        SET machine_targets = migrated.targets::json
        FROM migrated
        WHERE template.id = migrated.id
        """
    )


def downgrade() -> None:
    """保留补全后的目标字段，降级无需清理历史快照。"""
    pass
