# MT4 EA 伦敦金交易策略

本目录包含用于MetaTrader 4平台的伦敦金(XAUUSD)交易EA策略。

## 目录结构

- `XAUUSD_Scalping.mq4` - 剥头皮策略EA
- `XAUUSD_Grid.mq4` - 网格交易策略EA
- `XAUUSD_Trend.mq4` - 趋势跟踪策略EA
- `XAUUSD_Combined.mq4` - 组合策略EA（剥头皮+趋势+网格）

## 安装说明

1. 打开MT4平台
2. 点击"文件" -> "打开数据文件夹"
3. 进入 `MQL4/Experts` 目录
4. 将.mq4文件复制到此目录
5. 在MT4中按F4打开MetaEditor
6. 编译EA文件
7. 将编译好的EA拖放到XAUUSD图表上

## 策略说明

### 1. 剥头皮策略 (XAUUSD_Scalping.mq4)
- 使用RSI和布林带识别超买超卖
- 快速进出场
- 适合波动较大的市场

### 2. 网格策略 (XAUUSD_Grid.mq4)
- 自动设置网格水平
- 价格波动时自动交易
- 适合震荡市场

### 3. 趋势策略 (XAUUSD_Trend.mq4)
- 使用EMA快慢线判断趋势
- 趋势确认后入场
- 适合趋势明显的市场

### 4. 组合策略 (XAUUSD_Combined.mq4)
- 结合以上三种策略
- 根据市场情况自动选择最佳策略
- 更全面的交易方案

## 参数设置

每个EA都有其特定的参数设置，可以在MT4中加载EA时进行配置：

### 通用参数
- LotSize: 交易手数
- StopLoss: 止损点数
- TakeProfit: 止盈点数
- MagicNumber: EA识别号

### 策略特定参数
- 剥头皮策略：RSI周期、布林带周期
- 网格策略：网格数量、网格间距
- 趋势策略：EMA快慢线周期
- 组合策略：各策略权重

## 风险提示

1. 请在模拟账户中充分测试
2. 建议先用小资金测试
3. 注意控制风险，设置合理的止损
4. 定期检查EA运行状态

## 更新日志

### v1.0.0 (2024-03-21)
- 初始版本发布
- 包含四个基础策略EA 