#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core模块统一路由入口
"""
from fastapi import APIRouter

from core.auth.api import router as auth_router
from core.dept.api import router as dept_router
from core.menu.api import router as menu_router
from core.permission.api import router as permission_router
from core.post.api import router as post_router
from core.role.api import router as role_router
from core.user.api import router as user_router
from core.login_log.api import router as login_log_router
from core.oauth.api import router as oauth_router
from core.feature_analysis.api import router as feature_analysis_router
from core.issues_analysis.api import router as issues_analysis_router
from core.env_machine.api import router as env_machine_router
from core.test_report.api import router as test_report_router
from core.scheduler.api import router as scheduler_router

router = APIRouter()

# 注册子模块路由
router.include_router(auth_router)
router.include_router(dept_router)
router.include_router(menu_router)
router.include_router(permission_router)
router.include_router(post_router)
router.include_router(role_router)
router.include_router(user_router)
router.include_router(login_log_router)
router.include_router(oauth_router)
router.include_router(feature_analysis_router)
router.include_router(issues_analysis_router)
router.include_router(env_machine_router)
router.include_router(test_report_router)
router.include_router(scheduler_router)