#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 打印带颜色的信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查文件是否存在
check_file() {
    if [ ! -f "$1" ]; then
        warn "File $1 does not exist, skipping backup"
        return 1
    fi
    return 0
}

# 进入项目目录
cd /root/AI-Trade || {
    error "Failed to change to project directory"
    exit 1
}

# 停止服务
info "Stopping service..."
sudo systemctl stop ai-trade

# 备份当前配置
info "Backing up configuration..."
check_file .env && cp .env .env.backup
check_file config.json && cp config.json config.json.backup

# 更新代码
info "Updating code..."
git pull

# 更新虚拟环境
info "Updating virtual environment..."
source venv/bin/activate || {
    error "Failed to activate virtual environment"
    exit 1
}

# 安装依赖
info "Installing dependencies..."
pip install -r requirements.txt || {
    error "Failed to install dependencies"
    exit 1
}

# 恢复配置
info "Restoring configuration..."
[ -f .env.backup ] && cp .env.backup .env
[ -f config.json.backup ] && cp config.json.backup config.json

# 重启服务
info "Restarting service..."
sudo systemctl restart ai-trade

# 检查服务状态
info "Checking service status..."
sudo systemctl status ai-trade

info "Update completed!" 