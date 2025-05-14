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

# 更新系统
info "Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

# 安装必要的系统依赖
info "Installing system dependencies..."
sudo apt-get install -y python3-pip python3-venv nginx git

# 创建项目目录
info "Creating project directory..."
sudo mkdir -p /root/AI-Trade
sudo chown $USER:$USER /root/AI-Trade

# 克隆项目代码
info "Cloning project code..."
git clone https://github.com/your-repo/trading-bot.git /root/AI-Trade

# 创建并激活虚拟环境
info "Setting up Python virtual environment..."
cd /root/AI-Trade
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
info "Installing Python dependencies..."
pip install -r requirements.txt

# 创建配置文件
info "Creating configuration files..."

# 创建.env文件
cat > .env << EOL
SECRET_KEY=your-secret-key-here
BINANCE_API_KEY=your-binance-api-key
BINANCE_API_SECRET=your-binance-api-secret
LBANK_API_KEY=your-lbank-api-key
LBANK_API_SECRET=your-lbank-api-secret
CURRENT_EXCHANGE=binance
TRADING_PAIR=BTCUSDT
LEVERAGE=10
QUANTITY=0.001
STOP_LOSS_PERCENTAGE=0.3
TAKE_PROFIT_PERCENTAGE=0.6
MAX_DAILY_TRADES=100
EOL

# 配置Nginx
info "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/ai-trade << EOL
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL

# 启用Nginx配置
sudo ln -s /etc/nginx/sites-available/ai-trade /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 配置Systemd服务
info "Configuring Systemd service..."
sudo tee /etc/systemd/system/ai-trade.service << EOL
[Unit]
Description=AI Trading Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/AI-Trade
Environment="PATH=/root/AI-Trade/venv/bin"
ExecStart=/root/AI-Trade/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# 重新加载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl enable ai-trade
sudo systemctl start ai-trade

info "Deployment completed!"
info "You can check the service status with: sudo systemctl status ai-trade"
info "View logs with: sudo journalctl -u ai-trade -f" 