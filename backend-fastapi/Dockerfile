FROM python:3.11.13-slim-bookworm

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置工作目录
WORKDIR /app

# 更换为阿里云国内源 (Debian bookworm)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用阿里云源）
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p /data/test_reports

# 设置启动脚本权限
RUN chmod +x start.sh

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV ENV=prod
ENV WORKERS=1

# 启动命令
CMD ["./start.sh"]