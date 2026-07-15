"""merge platform and performance migration heads

Revision ID: f8b9c0d1e2f3
Revises: add_command_and_ip_template, f7a8b9c0d1e2
Create Date: 2026-07-14
"""
from typing import Sequence, Union

revision: str = "f8b9c0d1e2f3"
down_revision: Union[str, tuple[str, str], None] = (
    "add_command_and_ip_template",
    "f7a8b9c0d1e2",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass