#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析模型 - Feature Analysis Model
"""
from sqlalchemy import Column, String, Text, Index

from app.base_model import BaseModel


class FeatureAnalysis(BaseModel):
    """特性分析表"""
    __tablename__ = "feature_analysis"

    # 工作项信息
    feature_id_father = Column(String(64), nullable=True, comment="父工作项ID")
    feature_id = Column(String(64), nullable=True, comment="需求ID")
    feature_desc = Column(String(255), nullable=True, comment="需求标题")

    # 归属信息
    feature_services = Column(String(64), nullable=True, comment="开发归属")
    feature_task_id = Column(String(64), nullable=True, comment="需求task id")
    feature_task_service = Column(String(64), nullable=True, comment="测试归属")
    feature_owner = Column(String(64), nullable=True, comment="测试责任人")
    feature_dev_owner = Column(String(64), nullable=True, comment="开发责任人")

    # 测试相关
    feature_safe_test = Column(String(64), nullable=True, comment="涉及安全")
    feature_code = Column(String(64), nullable=True, comment="代码量")
    feature_test_count = Column(String(64), nullable=True, comment="需求转测次数")
    feature_test_expect_time = Column(String(64), nullable=True, comment="预计转测时间")
    feature_test_start_time = Column(String(64), nullable=True, comment="实际转测时间")
    feature_test_end_time = Column(String(64), nullable=True, comment="完成测试时间")

    # 质量评价
    feature_judge = Column(Text, nullable=True, comment="特性质量评价")
    feature_bug_total = Column(String(64), nullable=True, comment="问题单数量")
    feature_bug_serious = Column(String(64), nullable=True, comment="严重以上数量")
    feature_bug_general = Column(String(64), nullable=True, comment="一般数量")
    feature_bug_prompt = Column(String(64), nullable=True, comment="提示数量")
    feature_bug_detail = Column(String(255), nullable=True, comment="引入问题单号")

    # 进展与风险
    feature_progress = Column(Text, nullable=True, comment="测试进展")
    feature_risk = Column(Text, nullable=True, comment="风险与关键问题")

    # 版本与同步
    feature_version = Column(String(64), nullable=True, comment="需求归属版本")
    sync_time = Column(String(64), nullable=True, comment="数据同步时间")

    # 原有字段
    create_by = Column(String(64), nullable=True, comment="创建者")
    create_time = Column(String(64), nullable=True, comment="创建时间")
    modify_time = Column(String(64), nullable=True, comment="修改时间")

    # 索引
    __table_args__ = (
        Index('idx_feature_version', 'feature_version'),
        Index('idx_feature_deleted', 'is_deleted'),
    )

    def get_test_status(self) -> str:
        """获取测试状态"""
        if self.feature_test_end_time:
            return "已完成"
        elif self.feature_test_start_time:
            return "测试中"
        else:
            return "未开始"