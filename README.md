# 币安合约量化交易机器人

这是一个基于Python的币安合约量化交易机器人，支持自动做多和做空操作。

## 功能特点

- 支持币安合约交易
- 自动做多和做空
- 使用多个技术指标（RSI、MACD、布林带）生成交易信号
- 自动设置止损和止盈
- 支持杠杆交易
- 高频交易（1分钟K线）

## 安装要求

1. Python 3.7+
2. 币安账户和API密钥

## 安装步骤

1. 克隆仓库：
```bash
git clone [repository-url]
cd [repository-name]
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
- 复制 `.env.example` 文件为 `.env`
- 在 `.env` 文件中填入你的币安API密钥和其他配置

## 配置说明

在 `.env` 文件中配置以下参数：

- `BINANCE_API_KEY`: 币安API密钥
- `BINANCE_API_SECRET`: 币安API密钥密码
- `TRADING_PAIR`: 交易对（例如：BTCUSDT）
- `LEVERAGE`: 杠杆倍数
- `QUANTITY`: 交易数量
- `STOP_LOSS_PERCENTAGE`: 止损百分比
- `TAKE_PROFIT_PERCENTAGE`: 止盈百分比

## 使用方法

运行交易机器人：
```bash
python trading_bot.py
```

## 交易策略

该机器人使用以下技术指标组合来生成交易信号：

1. RSI（相对强弱指标）
   - RSI < 30: 买入信号
   - RSI > 70: 卖出信号

2. MACD（移动平均线趋势指标）
   - MACD线上穿信号线: 买入信号
   - MACD线下穿信号线: 卖出信号

3. 布林带
   - 价格触及下轨: 买入信号
   - 价格触及上轨: 卖出信号

## 风险提示

- 加密货币交易具有高风险，请谨慎使用
- 建议先在测试网络进行测试
- 请确保了解合约交易的风险
- 建议使用小资金进行测试

## 免责声明

本项目仅供学习和研究使用，不构成投资建议。使用本程序进行交易造成的任何损失由使用者自行承担。 