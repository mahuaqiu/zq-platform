#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: service.py
@Desc: ConfigCenter Service - 配置中心服务（CRUD 继承 BaseService）
"""
from app.base_service import BaseService
from core.config_center.model import ConfigCenterItem
from core.config_center.schema import ConfigCenterItemCreate, ConfigCenterItemUpdate


class ConfigCenterService(BaseService[ConfigCenterItem, ConfigCenterItemCreate, ConfigCenterItemUpdate]):
    """配置中心服务。

    按键查询：get_by_field(db, "key", key)；按键唯一性校验：check_unique(db, "key", key, exclude_id)。
    """

    model = ConfigCenterItem
