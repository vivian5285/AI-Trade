# AI Trading System

一个支持多交易所的自动化交易系统，包括MT4、Binance和LBank。

## 功能特性

### 多交易所支持
- MT4交易支持
  - 实时行情监控
  - 自动交易执行
  - 技术指标分析
  - 风险管理系统
- Binance交易支持
  - 现货和合约交易
  - 网格交易策略
  - 趋势跟踪策略
  - 风险控制系统
- LBank交易支持
  - 现货和合约交易
  - 多策略支持
  - 实时市场分析
  - 资金管理系统

### 统一配置管理
- 基于环境变量的配置系统
- 支持多交易所配置
- 参数验证和默认值
- 灵活的配置继承机制

### 策略系统
- 基础策略框架
- 多因子信号系统
- 动态仓位管理
- 自适应风险控制
- 完整的回测支持

### 风险控制
- 止损止盈管理
- 资金管理
- 风险预警
- 交易限制

## 安装说明

### 环境要求
- Python 3.8+
- MT4平台
- 网络连接
- Docker (可选，用于容器化部署)

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/yourusername/ai-trading.git
cd ai-trading
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp examples/.env.mt4 .env
# 编辑.env文件，填入您的配置信息
```

4. 安装MT4 EA
- 将`mt4_ea/MT4Connector.mq4`复制到MT4的Experts目录
- 在MT4中编译EA
- 将EA附加到图表

### Docker部署

1. 构建镜像
```bash
docker-compose build
```

2. 启动服务
```bash
docker-compose up -d
```

3. 查看日志
```bash
# 查看所有服务的日志
docker-compose logs -f

# 查看特定服务的日志
docker-compose logs -f mt4_trader
docker-compose logs -f binance_trader
docker-compose logs -f lbank_trader
```

4. 停止服务
```bash
docker-compose down
```

5. 重启服务
```bash
docker-compose restart
```

### Docker配置说明

1. 服务配置
- `mt4_trader`: MT4交易服务
- `binance_trader`: Binance交易服务
- `lbank_trader`: LBank交易服务

2. 数据持久化
- 配置文件: `./config:/app/config`
- 日志文件: `./logs:/app/logs`
- 环境变量: `./.env:/app/.env`

3. 网络配置
- 所有服务都在`trading_network`网络中
- 服务间可以相互通信

4. 时区设置
- 默认使用`Asia/Shanghai`时区
- 可在`docker-compose.yml`中修改

## 使用方法

### MT4交易

1. 启动MT4 EA
- 在MT4中打开图表
- 将MT4Connector EA附加到图表
- 确保EA显示"已启动"状态

2. 运行交易策略
```bash
python examples/run_mt4_strategy.py
```

### Binance交易

1. 配置API密钥
- 在Binance创建API密钥
- 将API密钥添加到环境变量

2. 运行交易策略
```bash
python examples/run_binance_strategy.py
```

### LBank交易

1. 配置API密钥
- 在LBank创建API密钥
- 将API密钥添加到环境变量

2. 运行交易策略
```bash
python examples/run_lbank_strategy.py
```

## 配置说明

### MT4配置
```ini
# MT4连接配置
MT4_SERVER=localhost
MT4_PORT=8222
MT4_SYMBOL=EURUSD
MT4_MAGIC_NUMBER=123456

# 交易参数
MT4_INTERVAL=1m
MT4_LOOKBACK=100
MT4_RISK_PER_TRADE=0.02
MT4_MAX_POSITION_SIZE=1.0
MT4_DEFAULT_POSITION_SIZE=0.1

# 技术指标参数
MT4_FAST_MA_PERIOD=10
MT4_SLOW_MA_PERIOD=20
MT4_RSI_PERIOD=14
MT4_RSI_OVERBOUGHT=70
MT4_RSI_OVERSOLD=30

# 波动率参数
MT4_HIGH_VOLATILITY=0.02
MT4_LOW_VOLATILITY=0.005

# 信号权重
MT4_TREND_WEIGHT=0.4
MT4_MOMENTUM_WEIGHT=0.3
MT4_VOLATILITY_WEIGHT=0.2
MT4_VOLUME_WEIGHT=0.1

# 开平仓阈值
MT4_OPEN_THRESHOLD=0.6
MT4_CLOSE_THRESHOLD=0.4

# 止损止盈参数
MT4_STOP_LOSS_PIPS=50
MT4_TAKE_PROFIT_PIPS=100
MT4_POINT_VALUE=0.1
```

### Binance配置
```ini
# API配置
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 交易参数
TRADING_PAIR=BTCUSDT
LEVERAGE=20
QUANTITY=0.001
STOP_LOSS_PERCENTAGE=2.0
TAKE_PROFIT_PERCENTAGE=4.0

# 风险控制
MAX_DAILY_TRADES=10
MAX_DAILY_LOSS_PERCENTAGE=5.0
MIN_VOLUME_THRESHOLD=1000000

# 网格交易参数
GRID_SIZE=5
GRID_SPACING=100

# 趋势跟踪参数
TREND_EMA_FAST=12
TREND_EMA_SLOW=26

# 短线交易参数
SCALPING_PROFIT_TARGET=0.5
SCALPING_STOP_LOSS=0.3
```

### LBank配置
```ini
# API配置
LBANK_API_KEY=your_api_key
LBANK_SECRET_KEY=your_secret_key

# 交易参数
TRADING_PAIR=btc_usdt
LEVERAGE=20
POSITION_SIZE=0.001
MAX_POSITIONS=5

# 风险控制
MAX_DRAWDOWN=10.0
DAILY_LOSS_LIMIT=5.0
MAX_LEVERAGE=20

# 技术指标参数
FAST_EMA=12
SLOW_EMA=26
RSI_PERIOD=14
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30

# 布林带参数
BB_PERIOD=20
BB_STD=2.0

# 市场参数
MIN_VOLUME=1000000
PRICE_CHANGE_THRESHOLD=0.5
EXECUTION_INTERVAL=1.0
```

## 项目结构
```
ai-trading/
├── config/                 # 配置文件
│   ├── base_config.py     # 基础配置类
│   ├── binance_config.py  # Binance配置
│   ├── lbank_config.py    # LBank配置
│   └── mt4_config.py      # MT4配置
├── mt4_connector/         # MT4连接器
│   └── mt4_client.py      # MT4客户端
├── mt4_ea/               # MT4 EA
│   └── MT4Connector.mq4  # MT4连接器EA
├── strategies/           # 交易策略
│   ├── base.py          # 基础策略类
│   └── mt4_strategy.py  # MT4策略实现
├── examples/            # 示例代码
│   ├── .env.mt4        # MT4环境变量
│   └── run_mt4_strategy.py  # MT4策略运行示例
└── README.md           # 项目文档
```

## 注意事项

1. 风险提示
- 本系统仅供学习和研究使用
- 实盘交易存在风险，请谨慎使用
- 建议先在模拟账户测试

2. 使用建议
- 定期检查系统运行状态
- 及时更新配置参数
- 做好风险控制
- 保持系统安全

3. 常见问题
- 确保MT4 EA正确安装
- 检查网络连接状态
- 验证API密钥权限
- 确认配置参数正确

## 贡献指南

欢迎提交Issue和Pull Request来帮助改进项目。

## 许可证

MIT License 