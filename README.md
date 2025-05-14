# AI Trade 量化交易系统

## 项目简介
AI Trade 是一个基于 Flask 的多交易所量化交易系统，支持币安（Binance）、LBank 等主流交易所，集成了多种交易策略（如RSI、布林带、SuperTrend、网格、Ichimoku等），并提供了可视化的仪表盘和交易机器人控制面板。

## 主要功能
- 实时市场行情与K线图展示
- 账户资产与持仓信息总览
- 交易机器人控制（启动/停止/重启）
- 策略参数可视化配置与保存
- 交易历史与运行日志查询
- 多交易所API密钥管理
- 支持多种主流量化策略

## 技术栈
- Python 3.8+
- Flask & Flask-SQLAlchemy
- Bootstrap 5 & Bootstrap Icons
- JavaScript (Fetch API)
- Lightweight Charts (K线图)
- python-binance, requests, python-dotenv, pandas, plotly

## 安装与部署
### 1. 克隆项目
```bash
git clone <your-repo-url>
cd AI-Trade
```

### 2. 安装依赖
```bash
pip3 install -r requirements.txt
```

### 3. 配置环境变量
编辑 `.env` 文件，填写如下内容（请用你自己的API Key/Secret替换）：
```ini
SECRET_KEY=your_secret_key
CURRENT_EXCHANGE=Binance
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
LBANK_API_KEY=xxx
LBANK_API_SECRET=xxx
# 其他策略参数...
```

### 4. 初始化数据库
```bash
python3 init_db.py
```

### 5. 启动服务
开发环境：
```bash
python3 app.py
```
生产环境（推荐使用 systemd）：
```bash
sudo systemctl restart ai-trade
sudo systemctl status ai-trade
```

### 6. 访问系统
浏览器访问：http://your-server-ip:5000

## 目录结构
```
AI-Trade/
├── app.py                # 主后端服务
├── init_db.py            # 数据库初始化脚本
├── requirements.txt      # 依赖包列表
├── .env                  # 环境变量配置
├── templates/            # 前端页面模板
│   ├── base.html         # 基础布局
│   ├── dashboard.html    # 仪表盘
│   ├── trading_bot.html  # 交易机器人控制
│   └── ...
├── static/               # 静态资源
│   └── ...
└── app.log               # 日志文件
```

## 环境变量说明
- `SECRET_KEY`：Flask应用密钥
- `CURRENT_EXCHANGE`：当前交易所（Binance/LBank）
- `BINANCE_API_KEY`/`BINANCE_API_SECRET`：币安API密钥
- `LBANK_API_KEY`/`LBANK_API_SECRET`：LBank API密钥
- 其他策略参数（如RSI、布林带、SuperTrend等）可在`.env`中配置

## 常见问题
- **API密钥无效/未生效**：请确保`.env`和数据库中的密钥一致，重启服务后生效。
- **页面数据一直显示"加载中..."**：请检查API密钥配置、网络连通性和日志文件（`app.log`）。
- **数据库初始化报错**：请确认已正确安装依赖，并使用`python3`运行`init_db.py`。
- **服务无法启动**：检查`app.log`和`systemctl status ai-trade`输出，排查端口占用、依赖缺失等问题。

## 贡献与反馈
如需贡献代码或反馈问题，请提交 Issue 或 Pull Request。

## 联系方式
- 作者：AI Trade 团队
- 邮箱：your@email.com

---
如有更多问题，欢迎联系开发者或查阅源码注释。 