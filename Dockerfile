# 使用Python 3.8作为基础镜像
FROM python:3.8-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY config/ ./config/
COPY mt4_connector/ ./mt4_connector/
COPY strategies/ ./strategies/
COPY examples/ ./examples/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建日志目录
RUN mkdir -p /app/logs

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 设置入口点
ENTRYPOINT ["python", "examples/run_mt4_strategy.py"] 