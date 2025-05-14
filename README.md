# AI Trading Bot

一个基于Python的自动化交易机器人系统，支持多个交易所和多种交易策略。

## 功能特点

- 支持多个交易所（Binance、LBank）
- 多种交易策略（网格交易、超级趋势、RSI、布林带等）
- 实时市场数据监控
- 自动交易执行
- 风险管理系统
- Web控制面板
- 交易历史记录
- 性能分析报告

## 系统要求

- Python 3.8+
- MySQL/PostgreSQL
- Nginx
- Supervisor

## 安装步骤

1. 克隆代码库：
```bash
git clone https://github.com/your-repo/trading-bot.git
cd trading-bot
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
- 复制 `.env.example` 到 `.env`
- 填写必要的配置信息（API密钥等）

4. 初始化数据库：
```bash
flask db upgrade
```

5. 启动服务：
```bash
./deploy.sh
```

## 配置说明

### 环境变量

- `SECRET_KEY`: Flask应用密钥
- `BINANCE_API_KEY`: Binance API密钥
- `BINANCE_API_SECRET`: Binance API密钥
- `LBANK_API_KEY`: LBank API密钥
- `LBANK_API_SECRET`: LBank API密钥
- `CURRENT_EXCHANGE`: 当前使用的交易所
- `TRADING_PAIR`: 交易对
- `LEVERAGE`: 杠杆倍数
- `QUANTITY`: 交易数量
- `STOP_LOSS_PERCENTAGE`: 止损百分比
- `TAKE_PROFIT_PERCENTAGE`: 止盈百分比
- `MAX_DAILY_TRADES`: 每日最大交易次数

### 策略配置

在 `config.json` 中配置各个策略的参数：

```json
{
  "rsi": {
    "period": 14,
    "overbought": 70,
    "oversold": 30
  },
  "bollinger_bands": {
    "period": 20,
    "std_dev": 2
  },
  "supertrend": {
    "atr_period": 10,
    "atr_multiplier": 3
  }
}
```

## 使用说明

1. 访问控制面板：
- 打开浏览器访问 `http://your-domain.com`
- 默认用户名：admin
- 默认密码：admin123

2. 配置交易机器人：
- 选择交易所和交易对
- 设置交易参数
- 选择交易策略
- 设置风险参数

3. 启动交易：
- 点击"启动"按钮开始交易
- 监控交易状态和性能
- 查看交易历史和报告

## 安全建议

1. 修改默认密码
2. 使用强密码
3. 定期更新API密钥
4. 启用双因素认证
5. 限制API权限
6. 定期备份数据

## 故障排除

1. 检查日志文件：
```bash
tail -f /var/log/trading_bot/err.log
```

2. 检查服务状态：
```bash
sudo supervisorctl status trading_bot
```

3. 重启服务：
```bash
sudo supervisorctl restart trading_bot
```

## 维护说明

1. 定期更新：
```bash
git pull
pip install -r requirements.txt
sudo supervisorctl restart trading_bot
```

2. 数据库备份：
```bash
pg_dump -U your_user your_database > backup.sql
```

3. 日志轮转：
```bash
sudo logrotate -f /etc/logrotate.d/trading_bot
```

## 许可证

MIT License 