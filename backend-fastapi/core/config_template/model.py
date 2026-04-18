#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-04-15
@File: model.py
@Desc: ConfigTemplate Model - 配置模板模型
"""
from sqlalchemy import Column, String, Text, Index

from app.base_model import BaseModel


class ConfigTemplate(BaseModel):
    """
    配置模板表

    字段说明：
    - name: 模板名称（唯一）
    - type: 模板类型（config/script）
    - script_name: 脚本名称（仅脚本类型）
    - namespace: 适用命名空间（可选，null表示全部）
    - note: 备注说明
    - config_content: YAML 配置内容或脚本内容
    - version: 版本号（YYYYMMDD-HHMMSS）
    """
    __tablename__ = "config_template"

    # 模板名称（唯一）
    name = Column(String(64), nullable=False, unique=True, comment="模板名称")

    # 模板类型（config/script）
    type = Column(String(20), nullable=False, default="config", comment="模板类型")

    # 脚本名称（仅脚本类型使用）
    script_name = Column(String(128), nullable=True, comment="脚本名称")

    # 适用命名空间（可选）
    namespace = Column(String(64), nullable=True, comment="适用命名空间")

    # 备注说明
    note = Column(Text, nullable=True, comment="备注说明")

    # YAML 配置内容或脚本内容
    config_content = Column(Text, nullable=False, comment="配置内容")

    # 版本号（自动生成）
    version = Column(String(20), nullable=False, comment="版本号YYYYMMDD-HHMMSS")

    # 索引
    __table_args__ = (
        Index("ix_config_template_namespace", "namespace"),
        Index("ix_config_template_type", "type"),
    )