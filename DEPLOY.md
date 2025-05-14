# AI Trading Bot 部署指南

本文档提供了在 VPS 上部署 AI Trading Bot 的详细步骤。

## 1. 系统要求

- Ubuntu 20.04 LTS 或更高版本
- 至少 1GB RAM
- 至少 20GB 存储空间
- 稳定的网络连接

## 2. 初始设置

### 2.1 更新系统
```bash
apt update && apt upgrade -y
```

### 2.2 安装基本工具
```bash
apt install -y git python3 python3-pip python3-venv ufw htop
```

### 2.3 配置防火墙
```bash
# 允许 SSH 连接
ufw allow ssh

# 允许 Web 界面访问
ufw allow 5000

# 启用防火墙
ufw enable
```

## 3. 部署步骤

### 3.1 克隆项目
```bash
cd /root
git clone https://github.com/vivian5285/AI-Trade.git
cd AI-Trade
```

### 3.2 配置环境变量
```bash
# 创建并编辑 .env 文件
nano .env
```

在 .env 文件中添加以下内容（替换为你的实际值）：
```env
BINANCE_API_KEY=你的币安API密钥
BINANCE_API_SECRET=你的币安API密钥
TRADING_PAIR=BTCUSDT
LEVERAGE=20
QUANTITY=0.001
```

### 3.3 运行部署脚本
```bash
# 添加执行权限
chmod +x deploy.sh start.sh stop.sh

# 运行部署脚本
./deploy.sh
```

## 4. 验证部署

### 4.1 检查服务状态
```bash
# 检查进程是否运行
ps aux | grep python3

# 查看日志
tail -f logs/trading.log
```

### 4.2 访问仪表盘
- 在浏览器中访问：`http://你的VPS_IP:5000`
- 如果无法访问，检查防火墙设置

## 5. 系统服务设置

### 5.1 创建系统服务
```bash
nano /etc/systemd/system/trading-bot.service
```

添加以下内容：
```ini
[Unit]
Description=AI Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/AI-Trade
ExecStart=/root/AI-Trade/start.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.2 启用服务
```bash
systemctl enable trading-bot
systemctl start trading-bot
```

## 6. 维护命令

### 6.1 服务管理
```bash
# 启动服务
systemctl start trading-bot

# 停止服务
systemctl stop trading-bot

# 重启服务
systemctl restart trading-bot

# 查看状态
systemctl status trading-bot
```

### 6.2 日志查看
```bash
# 查看服务日志
journalctl -u trading-bot -f

# 查看应用日志
tail -f /root/AI-Trade/logs/trading.log
```

## 7. 备份设置

### 7.1 创建备份脚本
```bash
nano /root/backup.sh
```

添加以下内容：
```bash
#!/bin/bash
BACKUP_DIR="/root/backups"
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/trading-bot-$(date +%Y%m%d).tar.gz /root/AI-Trade
find $BACKUP_DIR -type f -mtime +7 -delete
```

### 7.2 设置定时备份
```bash
chmod +x /root/backup.sh
crontab -e
```

添加以下内容（每天凌晨 2 点执行备份）：
```
0 2 * * * /root/backup.sh
```

## 8. 安全建议

### 8.1 SSH 安全
```bash
# 修改 SSH 端口
nano /etc/ssh/sshd_config
# 修改 Port 22 为其他端口，如 Port 2222

# 重启 SSH 服务
systemctl restart sshd
```

### 8.2 系统更新
```bash
# 设置自动更新
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

### 8.3 监控设置
```bash
# 安装监控工具
apt install -y htop iotop

# 查看系统资源使用
htop
```

## 9. 故障排除

### 9.1 常见问题

1. 无法访问仪表盘
   - 检查防火墙设置
   - 确认服务是否运行
   - 查看错误日志

2. 服务无法启动
   - 检查 Python 环境
   - 确认依赖安装
   - 查看系统日志

3. API 连接问题
   - 验证 API 密钥
   - 检查网络连接
   - 确认 API 权限

### 9.2 日志位置
- 应用日志：`/root/AI-Trade/logs/trading.log`
- 系统日志：`journalctl -u trading-bot`
- 备份日志：`/root/backups/`

## 10. 性能优化

### 10.1 系统优化
```bash
# 调整系统参数
nano /etc/sysctl.conf
```

添加以下内容：
```
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
```

### 10.2 应用优化
- 定期清理日志文件
- 监控内存使用
- 优化数据库查询

## 11. 更新部署

### 11.1 更新代码
```bash
cd /root/AI-Trade
git pull
./deploy.sh
```

### 11.2 回滚更新
```bash
cd /root/AI-Trade
git reset --hard HEAD^
./deploy.sh
```

## 12. 联系支持

- GitHub Issues: https://github.com/vivian5285/AI-Trade/issues
- 项目地址：https://github.com/vivian5285/AI-Trade

## 13. 免责声明

本项目仅供学习和研究使用，不构成投资建议。使用本软件进行交易的风险由用户自行承担。 