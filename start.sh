#!/bin/bash

# 设置工作目录
cd "$(dirname "$0")"

# 检查是否存在虚拟环境
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 检查日志目录
if [ ! -d "logs" ]; then
    mkdir logs
fi

# 检查是否已经在运行
if pgrep -f "python3 app.py" > /dev/null; then
    echo "Trading bot is already running!"
    exit 1
fi

# 启动应用
echo "Starting trading bot..."
nohup python3 app.py > logs/trading.log 2>&1 &

# 等待几秒检查进程是否成功启动
sleep 3
if pgrep -f "python3 app.py" > /dev/null; then
    echo "Trading bot started successfully!"
    echo "Logs are being written to logs/trading.log"
    echo "You can monitor the logs using: tail -f logs/trading.log"
else
    echo "Failed to start trading bot. Check logs/trading.log for details."
    exit 1
fi 