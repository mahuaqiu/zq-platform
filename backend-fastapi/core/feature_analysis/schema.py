#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特性分析 Schema - Feature Analysis Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class FeatureAnalysisBase(BaseModel):
    """特性分析基础 Schema"""
    feature_id_father: Optional[str] = Field(None, alias="featureIdFather", description="父工作项ID")
    feature_id: Optional[str] = Field(None, alias="featureId", description="需求ID")
    feature_desc: Optional[str] = Field(None, alias="featureDesc", description="需求标题")
    feature_services: Optional[str] = Field(None, alias="featureServices", description="开发归属")
    feature_task_id: Optional[str] = Field(None, alias="featureTaskId", description="需求task id")
    feature_task_service: Optional[str] = Field(None, alias="featureTaskService", description="测试归属")
    feature_owner: Optional[str] = Field(None, alias="featureOwner", description="测试责任人")
    feature_dev_owner: Optional[str] = Field(None, alias="featureDevOwner", description="开发责任人")
    feature_safe_test: Optional[str] = Field(None, alias="featureSafeTest", description="涉及安全")
    feature_code: Optional[str] = Field(None, alias="featureCode", description="代码量")
    feature_test_count: Optional[str] = Field(None, alias="featureTestCount", description="需求转测次数")
    feature_test_expect_time: Optional[str] = Field(None, alias="featureTestExpectTime", description="预计转测时间")
    feature_test_start_time: Optional[str] = Field(None, alias="featureTestStartTime", description="实际转测时间")
    feature_test_end_time: Optional[str] = Field(None, alias="featureTestEndTime", description="完成测试时间")
    feature_judge: Optional[str] = Field(None, alias="featureJudge", description="特性质量评价")
    feature_bug_total: Optional[str] = Field(None, alias="featureBugTotal", description="问题单数量")
    feature_bug_serious: Optional[str] = Field(None, alias="featureBugSerious", description="严重以上数量")
    feature_bug_general: Optional[str] = Field(None, alias="featureBugGeneral", description="一般数量")
    feature_bug_prompt: Optional[str] = Field(None, alias="featureBugPrompt", description="提示数量")
    feature_bug_detail: Optional[str] = Field(None, alias="featureBugDetail", description="引入问题单号")
    feature_progress: Optional[str] = Field(None, alias="featureProgress", description="测试进展")
    feature_risk: Optional[str] = Field(None, alias="featureRisk", description="风险与关键问题")
    feature_version: Optional[str] = Field(None, alias="featureVersion", description="需求归属版本")
    sync_time: Optional[str] = Field(None, alias="syncTime", description="数据同步时间")
    create_by: Optional[str] = Field(None, alias="createBy", description="创建者")
    create_time: Optional[str] = Field(None, alias="createTime", description="创建时间")
    modify_time: Optional[str] = Field(None, alias="modifyTime", description="修改时间")

    class Config:
        populate_by_name = True


class FeatureAnalysisCreate(FeatureAnalysisBase):
    """创建特性分析"""
    pass


class FeatureAnalysisUpdate(FeatureAnalysisBase):
    """更新特性分析"""
    pass


class FeatureAnalysisResponse(FeatureAnalysisBase):
    """特性分析响应"""
    id: str
    test_status: Optional[str] = Field(None, alias="testStatus", description="测试状态")

    class Config:
        populate_by_name = True
        from_attributes = True


class PieChartDataItem(BaseModel):
    """饼图数据项"""
    name: str
    value: int


class PieChartDataResponse(BaseModel):
    """饼图数据响应"""
    seriesData: List[PieChartDataItem]


class VersionListResponse(BaseModel):
    """版本列表响应"""
    items: List[str]