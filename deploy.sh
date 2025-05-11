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

# 检查系统要求
check_system() {
    info "检查系统要求..."
    
    # 检查Python版本
    if ! command -v python3 &> /dev/null; then
        error "Python3 未安装"
        exit 1
    fi
    
    # 检查pip
    if ! command -v pip3 &> /dev/null; then
        error "pip3 未安装"
        exit 1
    fi
    
    # 检查git
    if ! command -v git &> /dev/null; then
        error "git 未安装"
        exit 1
    fi
    
    info "系统要求检查完成"
}

# 安装系统依赖
install_system_deps() {
    info "安装系统依赖..."
    
    # 更新包列表
    sudo apt-get update
    
    # 安装必要的系统包
    sudo apt-get install -y python3-venv python3-dev build-essential
}

# 设置虚拟环境
setup_venv() {
    info "设置Python虚拟环境..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖
    pip install -r requirements.txt
}

# 检查配置文件
check_config() {
    info "检查配置文件..."
    
    if [ ! -f ".env" ]; then
        error "未找到.env配置文件"
        echo "请创建.env文件并设置以下配置："
        echo "BINANCE_API_KEY=你的API密钥"
        echo "BINANCE_API_SECRET=你的API密钥"
        echo "TRADING_PAIR=BTCUSDT"
        echo "LEVERAGE=20"
        echo "QUANTITY=0.001"
        exit 1
    fi
    
    # 检查必要的环境变量
    required_vars=("BINANCE_API_KEY" "BINANCE_API_SECRET" "TRADING_PAIR" "LEVERAGE" "QUANTITY")
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" .env; then
            error "缺少必要的环境变量: ${var}"
            exit 1
        fi
    done
    
    info "配置文件检查完成"
}

# 创建必要的目录
create_directories() {
    info "创建必要的目录..."
    
    mkdir -p logs
    mkdir -p data
}

# 设置日志轮转
setup_logrotate() {
    info "设置日志轮转..."
    
    if [ ! -f "/etc/logrotate.d/trading-bot" ]; then
        sudo tee /etc/logrotate.d/trading-bot > /dev/null << EOF
$(pwd)/logs/trading.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
}
EOF
    fi
}

# 主函数
main() {
    info "开始部署交易机器人..."
    
    # 检查系统要求
    check_system
    
    # 安装系统依赖
    install_system_deps
    
    # 设置虚拟环境
    setup_venv
    
    # 检查配置文件
    check_config
    
    # 创建必要的目录
    create_directories
    
    # 设置日志轮转
    setup_logrotate
    
    # 启动应用
    info "启动交易机器人..."
    ./start.sh
    
    info "部署完成！"
    info "你可以使用以下命令："
    info "查看日志: tail -f logs/trading.log"
    info "停止机器人: ./stop.sh"
    info "重启机器人: ./start.sh"
}

# 运行主函数
main 