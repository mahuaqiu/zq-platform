#!/bin/bash
# 启动脚本：控制多 worker 模式下的调度器

# WORKERS 环境变量控制 worker 数量，默认 1
WORKERS=${WORKERS:-1}

echo "Starting FastAPI with ${WORKERS} workers..."

# 使用 gunicorn 启动。
# 调度器领导权由 Redis 租约决定（core/scheduler/service.py LEASE_KEY），
# 与 worker 编号无关；多 worker / 多副本部署均安全。

exec gunicorn main:app \
    -w "${WORKERS}" \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    --timeout 120 \
    --preload \
    --access-logfile - \
    --error-logfile -