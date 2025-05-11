# Crypto Trading Bot Dashboard

一个简单的加密货币交易机器人仪表盘，支持币安和LBank交易所。

## 功能特点

- 实时显示账户余额
- 交易历史图表
- API密钥配置
- 交易参数设置
- 支持币安和LBank交易所

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/crypto-trading-bot.git
cd crypto-trading-bot
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行应用：
```bash
python app.py
```

4. 访问 http://localhost:5000 开始使用

## 配置

1. 访问 http://localhost:5000/settings
2. 输入你的币安和LBank API密钥
3. 设置交易参数（交易对、杠杆、数量等）

## 注意事项

- 请确保API密钥具有适当的权限
- 建议先在测试网络进行测试
- 请妥善保管你的API密钥

## 技术栈

- Flask
- Python-Binance
- Plotly
- Bootstrap
- jQuery

## 许可证

MIT 