#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析模型 - Issues Analysis Model
"""
from sqlalchemy import Column, String, Index

from app.base_model import BaseModel


class IssuesAnalysis(BaseModel):
    """问题分析表"""
    __tablename__ = "issues_analysis"

    # 问题信息
    issues_id = Column(String(64), nullable=True, comment="问题编号")
    issues_title = Column(String(64), nullable=True, comment="问题名称")
    issues_services = Column(String(64), nullable=True, comment="问题归属")
    issues_owner = Column(String(64), nullable=True, comment="开发责任人")
    issues_test_owner = Column(String(64), nullable=True, comment="测试责任人")
    issues_severity = Column(String(64), nullable=True, comment="严重程度")
    issues_probability = Column(String(64), nullable=True, comment="重现概率")
    issues_status = Column(String(64), nullable=True, comment="问题状态")
    issues_version = Column(String(64), nullable=True, comment="发现问题版本")

    # 关联需求
    feature_id = Column(String(64), nullable=True, comment="关联需求ID")
    feature_desc = Column(String(64), nullable=True, comment="需求名称")

    # 同步信息
    sync_time = Column(String(64), nullable=True, comment="数据同步时间")
    create_by = Column(String(64), nullable=True, comment="创建者")
    create_time = Column(String(64), nullable=True, comment="创建时间")
    modify_time = Column(String(64), nullable=True, comment="修改时间")

    __table_args__ = (
        Index('idx_issues_version', 'issues_version'),
        Index('idx_issues_deleted', 'is_deleted'),
    )