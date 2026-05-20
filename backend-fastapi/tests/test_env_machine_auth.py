#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time: 2026-05-21
@File: test_env_machine_auth.py
@Desc: 执行机申请权限验证单元测试
"""
import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from core.env_machine.auth import verify_env_apply_auth


class TestVerifyEnvApplyAuth:
    """权限验证测试"""

    @pytest.mark.asyncio
    async def test_missing_header(self):
        """测试缺少 X-Env-Auth header"""
        with patch('core.env_machine.auth.settings') as mock_settings:
            mock_settings.env_apply_auth_map = {"dev_key": ["meeting_gamma"]}

            with pytest.raises(HTTPException) as exc:
                await verify_env_apply_auth(namespace="meeting_gamma", x_env_auth=None)

            assert exc.value.status_code == 401
            assert exc.value.detail == "缺少 X-Env-Auth header"

    @pytest.mark.asyncio
    async def test_invalid_key(self):
        """测试无效的 key"""
        with patch('core.env_machine.auth.settings') as mock_settings:
            mock_settings.env_apply_auth_map = {"dev_key": ["meeting_gamma"]}

            with pytest.raises(HTTPException) as exc:
                await verify_env_apply_auth(namespace="meeting_gamma", x_env_auth="wrong_key")

            assert exc.value.status_code == 401
            assert exc.value.detail == "权限不足: 无权申请该命名空间的机器"

    @pytest.mark.asyncio
    async def test_key_not_authorized_for_namespace(self):
        """测试 key 未授权该 namespace"""
        with patch('core.env_machine.auth.settings') as mock_settings:
            mock_settings.env_apply_auth_map = {"dev_key": ["meeting_gamma"]}

            with pytest.raises(HTTPException) as exc:
                await verify_env_apply_auth(namespace="meeting_app", x_env_auth="dev_key")

            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_key_and_namespace(self):
        """测试正确的 key 和授权的 namespace"""
        with patch('core.env_machine.auth.settings') as mock_settings:
            mock_settings.env_apply_auth_map = {"dev_key": ["meeting_gamma", "meeting_app"]}

            # 不应抛出异常
            await verify_env_apply_auth(namespace="meeting_gamma", x_env_auth="dev_key")

    @pytest.mark.asyncio
    async def test_empty_config(self):
        """测试配置为空时拒绝所有申请"""
        with patch('core.env_machine.auth.settings') as mock_settings:
            mock_settings.env_apply_auth_map = {}

            with pytest.raises(HTTPException) as exc:
                await verify_env_apply_auth(namespace="meeting_gamma", x_env_auth="any_key")

            assert exc.value.status_code == 401


class TestEnvApplyAuthMap:
    """配置解析测试"""

    def test_valid_config(self):
        """测试有效的 JSON 配置解析"""
        from app.config import Settings
        settings = Settings(ENV_APPLY_AUTH='{"key1":["ns1","ns2"]}')

        result = settings.env_apply_auth_map
        assert result == {"key1": ["ns1", "ns2"]}

    def test_empty_config(self):
        """测试空配置"""
        from app.config import Settings
        settings = Settings(ENV_APPLY_AUTH='')

        result = settings.env_apply_auth_map
        assert result == {}

    def test_invalid_json_config(self):
        """测试无效的 JSON 配置"""
        from app.config import Settings
        settings = Settings(ENV_APPLY_AUTH='invalid json')

        result = settings.env_apply_auth_map
        assert result == {}  # 解析失败返回空字典