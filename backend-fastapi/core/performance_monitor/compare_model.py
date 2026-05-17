#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本对比标签模型
"""
from sqlalchemy import Column, String, Integer, Text

from app.base_model import BaseModel


class CompareTag(BaseModel):
    """对比标签表（跨版本共享标签，使用相对时间）"""
    __tablename__ = "performance_compare_tag"

    name = Column(String(100), nullable=False, comment="标签名称")
    type = Column(String(20), nullable=False, default="peak", comment="类型: peak(冲高) / stable(稳态)")
    start_time = Column(Integer, nullable=False, comment="开始时间（相对秒数）")
    end_time = Column(Integer, nullable=False, comment="结束时间（相对秒数）")
    note = Column(Text, nullable=True, comment="备注")

    TYPE_DISPLAY = {
        "peak": "冲高",
        "stable": "稳态",
    }

    def get_type_display(self) -> str:
        """返回类型的中文显示名称"""
        return self.TYPE_DISPLAY.get(self.type, "") or self.type or ""