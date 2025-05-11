#!/bin/bash

# 查找并停止交易机器人进程
PID=$(pgrep -f "python3 app.py")

if [ -z "$PID" ]; then
    echo "Trading bot is not running."
    exit 0
fi

echo "Stopping trading bot (PID: $PID)..."
kill $PID

# 等待进程结束
sleep 3
if pgrep -f "python3 app.py" > /dev/null; then
    echo "Force stopping trading bot..."
    kill -9 $PID
fi

echo "Trading bot stopped successfully." 