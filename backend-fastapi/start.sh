#!/bin/bash
# 启动脚本：控制多 worker 模式下的调度器

# WORKERS 环境变量控制 worker 数量，默认 1
WORKERS=${WORKERS:-1}

echo "Starting FastAPI with ${WORKERS} workers..."

# 使用 gunicorn 启动，通过环境变量控制主 worker
# gunicorn 在 fork worker 之前会设置 GUNICORN_WORKER_ID (从 0 开始)
# 我们利用 preload 模式，让 master 进程先加载代码，然后 fork worker

# 方案：使用 gunicorn 的 --preload 配合环境变量
# 主 worker (worker_id=0) 设置 IS_MAIN_WORKER=true

exec gunicorn main:app \
    -w "${WORKERS}" \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    --timeout 120 \
    --preload \
    --access-logfile - \
    --error-logfile -