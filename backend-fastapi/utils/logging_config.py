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
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
RETENTION_COUNT = 5  # 5 个文件，总计 100MB
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"


def setup_logging():
    """
    初始化日志配置，应用启动时调用

    配置内容：
    - 文件日志：RotatingFileHandler，自动旋转
    - 控制台日志：stderr 输出（开发环境）
    """
    # 确保日志目录存在
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # 移除默认 handler
    logger.remove()

    # 添加文件 handler（旋转）
    logger.add(
        os.path.join(LOG_DIR, LOG_FILE),
        format=LOG_FORMAT,
        rotation=MAX_FILE_SIZE,  # 文件大小达到阈值时旋转
        retention=RETENTION_COUNT,  # 保留文件数量
        compression="zip",  # 压缩旧日志文件
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,  # 异步写入，避免阻塞
    )

    # 添加控制台 handler（开发环境）
    logger.add(
        sys.stderr,
        format=LOG_FORMAT,
        level="DEBUG",
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