# AI Trading Bot Dashboard

一个基于 Flask 的加密货币交易机器人仪表盘，提供实时监控、交易管理和策略优化功能。

## 功能特点

### 1. 实时监控
- 账户余额实时显示
- 交易历史图表展示
- 持仓状态监控
- 盈亏统计

### 2. 交易管理
- 交易参数配置
- 杠杆倍数调整
- 交易对选择
- 订单管理

### 3. 策略优化
- 回测系统
- 参数优化
- 性能分析
- 策略回测报告

## 系统要求

- Python 3.8+
- pip3
- git
- 支持的操作系统：Linux/Ubuntu

## 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/vivian5285/AI-Trade.git
cd AI-Trade
```

### 2. 自动部署
```bash
chmod +x deploy.sh
./deploy.sh
```

部署脚本会自动：
- 检查系统要求
- 安装所需依赖
- 配置虚拟环境
- 设置日志系统
- 启动应用

### 3. 手动部署（可选）

如果需要手动部署，请按以下步骤操作：

1. 安装依赖：
```bash
pip3 install -r requirements.txt
```

2. 配置环境变量：
创建 `.env` 文件并设置以下配置：
```env
BINANCE_API_KEY=你的API密钥
BINANCE_API_SECRET=你的API密钥
TRADING_PAIR=BTCUSDT
LEVERAGE=20
QUANTITY=0.001
```

3. 启动应用：
```bash
./start.sh
```

## 使用说明

### 访问仪表盘
- 主页面：`http://你的服务器IP:5000`
- 设置页面：`http://你的服务器IP:5000/settings`

### 常用命令
- 启动机器人：`./start.sh`
- 停止机器人：`./stop.sh`
- 查看日志：`tail -f logs/trading.log`
- 重启服务：`./start.sh`

### 日志管理
- 日志位置：`logs/trading.log`
- 日志轮转：每天自动轮转，保留最近7天的日志
- 日志压缩：自动压缩历史日志

## 目录结构
```
AI-Trade/
├── app.py              # 主应用文件
├── config.py           # 配置文件
├── deploy.sh           # 部署脚本
├── start.sh            # 启动脚本
├── stop.sh             # 停止脚本
├── requirements.txt    # 依赖列表
├── .env               # 环境变量配置
├── logs/              # 日志目录
└── data/              # 数据存储目录
```

## 安全说明

1. API密钥安全
   - 请妥善保管API密钥
   - 建议使用只读权限的API密钥
   - 定期更换API密钥

2. 服务器安全
   - 建议使用防火墙
   - 定期更新系统
   - 使用强密码
   - 限制SSH访问

## 故障排除

1. 应用无法启动
   - 检查Python版本
   - 确认依赖安装完整
   - 查看日志文件

2. 无法连接交易所
   - 检查网络连接
   - 验证API密钥
   - 确认API权限

3. 性能问题
   - 检查服务器资源使用
   - 优化数据库查询
   - 调整缓存设置

## 技术栈

- 后端：Flask 2.0.1
- 数据库：SQLite
- 图表：Plotly
- 交易API：python-binance
- 数据处理：pandas, numpy

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

- GitHub: [@vivian5285](https://github.com/vivian5285)
- 项目地址：https://github.com/vivian5285/AI-Trade

## 免责声明

本项目仅供学习和研究使用，不构成投资建议。使用本软件进行交易的风险由用户自行承担。 