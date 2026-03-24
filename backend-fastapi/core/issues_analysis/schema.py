#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
问题分析 Schema - Issues Analysis Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class IssuesAnalysisBase(BaseModel):
    """问题分析基础 Schema"""
    issues_id: Optional[str] = Field(None, alias="issuesId", description="问题编号")
    issues_title: Optional[str] = Field(None, alias="issuesTitle", description="问题名称")
    issues_services: Optional[str] = Field(None, alias="issuesServices", description="问题归属")
    issues_owner: Optional[str] = Field(None, alias="issuesOwner", description="开发责任人")
    issues_test_owner: Optional[str] = Field(None, alias="issuesTestOwner", description="测试责任人")
    issues_severity: Optional[str] = Field(None, alias="issuesSeverity", description="严重程度")
    issues_probability: Optional[str] = Field(None, alias="issuesProbability", description="重现概率")
    issues_status: Optional[str] = Field(None, alias="issuesStatus", description="问题状态")
    issues_version: Optional[str] = Field(None, alias="issuesVersion", description="发现问题版本")
    feature_id: Optional[str] = Field(None, alias="featureId", description="关联需求ID")
    feature_desc: Optional[str] = Field(None, alias="featureDesc", description="需求名称")
    sync_time: Optional[str] = Field(None, alias="syncTime", description="数据同步时间")
    create_by: Optional[str] = Field(None, alias="createBy", description="创建者")
    create_time: Optional[str] = Field(None, alias="createTime", description="创建时间")
    modify_time: Optional[str] = Field(None, alias="modifyTime", description="修改时间")

    class Config:
        populate_by_name = True


class IssuesAnalysisCreate(IssuesAnalysisBase):
    """创建问题分析"""
    pass


class IssuesAnalysisUpdate(IssuesAnalysisBase):
    """更新问题分析"""
    pass


class IssuesAnalysisResponse(IssuesAnalysisBase):
    """问题分析响应"""
    id: str

    class Config:
        populate_by_name = True
        from_attributes = True


class VersionListResponse(BaseModel):
    """版本列表响应"""
    items: List[str]