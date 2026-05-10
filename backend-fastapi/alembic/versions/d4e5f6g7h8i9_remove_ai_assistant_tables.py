"""remove ai_assistant tables

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-05-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 删除AI助手相关菜单数据
    op.execute("""
        DELETE FROM core_menu WHERE id LIKE 'ai-assistant%';
    """)

    # 2. 删除AI助手相关表
    # 注意：删除顺序很重要，先删除关联表和外键约束的表

    # 删除消息表（有外键关联）
    op.drop_table('ai_assistant_message')

    # 删除会话表
    op.drop_table('ai_assistant_session')

    # 删除群组-角色关联表（多对多）
    op.drop_table('ai_group_role')

    # 删除群组表（被关联表引用）
    op.drop_table('ai_assistant_group')

    # 删除角色表
    op.drop_table('ai_assistant_role')


def downgrade() -> None:
    # 恢复AI助手菜单数据（先恢复父菜单，再恢复子菜单）
    op.execute("""
        INSERT INTO core_menu (id, parent_id, name, title, path, type, component, icon, order, sort, is_deleted,
                              hideInMenu, hideChildrenInMenu, hideInBreadcrumb, hideInTab, affixTab, keepAlive,
                              noBasicLayout, openInNewWindow, sys_create_datetime, sys_update_datetime)
        VALUES
        ('ai-assistant-root', NULL, 'AIAssistant', 'AI助手', '/ai-assistant', 'catalog', NULL, 'ep:chat-dot-round', 3, 3, false,
         false, false, false, false, false, false, false, false, NOW(), NOW()),
        ('ai-assistant-role', 'ai-assistant-root', 'AIAssistantRole', '角色管理', '/ai-assistant/role', 'menu',
         '/views/ai-assistant/role/index', NULL, 0, 0, false, false, false, false, false, false, false, false, false, NOW(), NOW()),
        ('ai-assistant-session', 'ai-assistant-root', 'AIAssistantSession', '会话管理', '/ai-assistant/session', 'menu',
         '/views/ai-assistant/session/index', NULL, 1, 1, false, false, false, false, false, false, false, false, false, NOW(), NOW()),
        ('ai-assistant-group', 'ai-assistant-root', 'AIAssistantGroup', '群组管理', '/ai-assistant/group', 'menu',
         '/views/ai-assistant/group/index', NULL, 2, 2, false, false, false, false, false, false, false, false, false, NOW(), NOW()),
        ('ai-assistant-skill', 'ai-assistant-root', 'AIAssistantSkill', 'Skill管理', '/ai-assistant/skill', 'menu',
         '/views/ai-assistant/skill/index', NULL, 3, 3, false, false, false, false, false, false, false, false, false, NOW(), NOW());
    """)

    # 1. 角色表
    op.create_table(
        'ai_assistant_role',
        sa.Column('id', sa.String(21), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('role_id', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('avatar', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('role_id'),
    )
    op.create_index('ix_ai_assistant_role_name', 'ai_assistant_role', ['name'])
    op.create_index('ix_ai_assistant_role_role_id', 'ai_assistant_role', ['role_id'])
    op.create_index('ix_ai_assistant_role_is_active', 'ai_assistant_role', ['is_active'])

    # 2. 群组表
    op.create_table(
        'ai_assistant_group',
        sa.Column('id', sa.String(21), nullable=False),
        sa.Column('group_id', sa.String(100), nullable=False),
        sa.Column('group_name', sa.String(200), nullable=False),
        sa.Column('is_group', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('trigger_word', sa.String(50), nullable=True),
        sa.Column('requires_trigger', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_message_time', sa.DateTime(), nullable=True),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id'),
    )
    op.create_index('ix_ai_assistant_group_group_id', 'ai_assistant_group', ['group_id'])
    op.create_index('ix_ai_assistant_group_is_active', 'ai_assistant_group', ['is_active'])

    # 3. 群组-角色关联表
    op.create_table(
        'ai_group_role',
        sa.Column('group_id', sa.String(21), sa.ForeignKey('ai_assistant_group.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', sa.String(21), sa.ForeignKey('ai_assistant_role.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('group_id', 'role_id'),
    )

    # 4. 会话表
    op.create_table(
        'ai_assistant_session',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('group_id', sa.String(100), nullable=False),
        sa.Column('chat_id', sa.String(150), nullable=False),
        sa.Column('session_name', sa.String(200), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('last_message_time', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id'),
    )
    op.create_index('ix_ai_assistant_session_group_id', 'ai_assistant_session', ['group_id'])
    op.create_index('ix_ai_assistant_session_chat_id', 'ai_assistant_session', ['chat_id'])
    op.create_index('ix_ai_assistant_session_status', 'ai_assistant_session', ['status'])
    op.create_index('ix_ai_assistant_session_is_active', 'ai_assistant_session', ['is_active'])

    # 5. 消息表
    op.create_table(
        'ai_assistant_message',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('message_type', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.String(100), nullable=False),
        sa.Column('sender_name', sa.String(100), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('nanoclaw_message_id', sa.String(100), nullable=True),
        sa.Column('reply_to_message_id', sa.String(100), nullable=True),
        sa.Column('send_time', sa.DateTime(), nullable=False),
        sa.Column('receive_time', sa.DateTime(), nullable=True),
        sa.Column('is_context_recovery', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('profile_id', sa.String(100), nullable=True),
        sa.Column('profile_name', sa.String(100), nullable=True),
        sa.Column('trigger_word', sa.String(50), nullable=True),
        sa.Column('sort', sa.Integer(), server_default='0'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('sys_create_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_update_datetime', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sys_creator_id', sa.String(50), nullable=True),
        sa.Column('sys_modifier_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_assistant_message_session_id', 'ai_assistant_message', ['session_id'])
    op.create_index('ix_ai_assistant_message_message_type', 'ai_assistant_message', ['message_type'])