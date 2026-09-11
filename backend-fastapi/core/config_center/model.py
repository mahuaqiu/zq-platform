#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File: model.py
@Desc: ConfigCenterItem Model - 配置中心键值对模型
"""
from sqlalchemy import Column, String, Text, Index, text

from app.base_model import BaseModel


class ConfigCenterItem(BaseModel):
    """
    配置中心键值对表

    字段说明：
    - key: 配置键（活动记录内唯一，软删除后可重建同名）
    - value: 配置值，JSON 对象字符串，如 {"充许":"允许","聊关":"聊天"}，键值均为字符串
    - remark: 备注
    """
    __tablename__ = "config_center_item"

    key = Column(String(64), nullable=False, comment="配置键")
    value = Column(Text, nullable=False, comment="配置值(JSON对象字符串)")
    remark = Column(Text, nullable=True, comment="备注")

    # 索引
    __table_args__ = (
        Index(
            "uq_config_center_item_active_key",
            "key",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("ix_config_center_item_key", "key"),
    )
