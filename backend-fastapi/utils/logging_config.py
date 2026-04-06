#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author: 臧成龙
@Contact: 939589097@qq.com
@Time: 2026-03-29
@File: logging_config.py
@Desc: Loguru 日志配置模块
"""
import sys
import os
from loguru import logger

# 日志配置参数
LOG_DIR = "logs"
LOG_FILE = "app.log"
SCHEDULER_LOG_FILE = "scheduler.log"  # 定时任务专用日志文件
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
RETENTION_COUNT = 5  # 5 个文件，总计 100MB
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"


def setup_logging():
    """
    初始化日志配置，应用启动时调用

    配置内容：
    - 主日志文件：app.log，记录应用主要日志
    - 定时任务日志文件：scheduler.log，记录定时任务执行日志
    - 控制台日志：仅输出 INFO 及以上级别，避免大量调试日志
    """
    # 确保日志目录存在
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # 移除默认 handler
    logger.remove()

    # 添加主日志文件 handler（记录所有模块）
    logger.add(
        os.path.join(LOG_DIR, LOG_FILE),
        format=LOG_FORMAT,
        rotation=MAX_FILE_SIZE,
        retention=RETENTION_COUNT,
        compression="zip",
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: "scheduler" not in record["name"].lower(),  # 排除定时任务日志
    )

    # 添加定时任务专用日志文件 handler
    logger.add(
        os.path.join(LOG_DIR, SCHEDULER_LOG_FILE),
        format=LOG_FORMAT,
        rotation=MAX_FILE_SIZE,
        retention=RETENTION_COUNT,
        compression="zip",
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: any(keyword in record["name"].lower() for keyword in ["scheduler", "apscheduler"]),  # 只记录定时任务相关日志
    )

    # 添加控制台 handler（仅INFO及以上级别，避免大量调试日志）
    logger.add(
        sys.stderr,
        format=LOG_FORMAT,
        level="INFO",  # 控制台只显示 INFO 及以上级别
        colorize=True,
    )

    logger.info("日志系统初始化完成")


def get_logger(name: str = None):
    """
    获取日志实例

    Args:
        name: 模块名称，用于标识日志来源

    Returns:
        logger 实例

    使用方式：
        from utils.logging_config import get_logger
        log = get_logger(__name__)
        log.info("操作成功")
    """
    if name:
        return logger.bind(name=name)
    return logger