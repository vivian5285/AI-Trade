//+------------------------------------------------------------------+
//|                                              XAUUSD_Trend.mq4 |
//|                                                                  |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024"
#property link      ""
#property version   "1.00"
#property strict

// 输入参数
extern double LotSize = 0.1;           // 交易手数
extern int MagicNumber = 12347;        // EA识别号
extern int StopLoss = 200;             // 止损点数
extern int TakeProfit = 400;           // 止盈点数
extern bool UseTrailingStop = true;    // 使用追踪止损
extern int TrailingStop = 150;         // 追踪止损点数
extern int TrailingStep = 30;          // 追踪止损步长

// 移动平均线参数
extern int FastMA_Period = 10;         // 快速MA周期
extern int SlowMA_Period = 20;         // 慢速MA周期
extern int SignalMA_Period = 5;        // 信号MA周期
extern int MA_Shift = 0;               // MA位移
extern int MA_Method = MODE_EMA;       // MA方法
extern int MA_Price = PRICE_CLOSE;     // MA价格类型

// MACD参数
extern int MACD_FastEMA = 12;          // MACD快速EMA周期
extern int MACD_SlowEMA = 26;          // MACD慢速EMA周期
extern int MACD_SignalPeriod = 9;      // MACD信号周期

// 全局变量
double g_point;
int g_digits;
int g_trend_direction = 0;             // 0:无趋势, 1:上升趋势, -1:下降趋势

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // 初始化点值
    g_digits = Digits;
    g_point = Point;
    if(g_digits == 3 || g_digits == 5)
        g_point *= 10;
        
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // 检查是否有足够的历史数据
    if(Bars < 100)
        return;
        
    // 管理现有订单
    ManageOrders();
    
    // 检查是否已有订单
    if(OrdersTotal() > 0)
        return;
        
    // 计算指标
    double fast_ma = iMA(NULL, 0, FastMA_Period, MA_Shift, MA_Method, MA_Price, 0);
    double slow_ma = iMA(NULL, 0, SlowMA_Period, MA_Shift, MA_Method, MA_Price, 0);
    double signal_ma = iMA(NULL, 0, SignalMA_Period, MA_Shift, MA_Method, MA_Price, 0);
    
    double macd_main = iMACD(NULL, 0, MACD_FastEMA, MACD_SlowEMA, MACD_SignalPeriod, PRICE_CLOSE, MODE_MAIN, 0);
    double macd_signal = iMACD(NULL, 0, MACD_FastEMA, MACD_SlowEMA, MACD_SignalPeriod, PRICE_CLOSE, MODE_SIGNAL, 0);
    
    // 判断趋势
    bool trend_up = (fast_ma > slow_ma) && (Close[0] > signal_ma) && (macd_main > macd_signal);
    bool trend_down = (fast_ma < slow_ma) && (Close[0] < signal_ma) && (macd_main < macd_signal);
    
    // 执行交易
    if(trend_up && g_trend_direction != 1)
    {
        OpenBuy();
        g_trend_direction = 1;
    }
    else if(trend_down && g_trend_direction != -1)
    {
        OpenSell();
        g_trend_direction = -1;
    }
}

//+------------------------------------------------------------------+
//| 开仓买入                                                          |
//+------------------------------------------------------------------+
void OpenBuy()
{
    double sl = Ask - StopLoss * g_point;
    double tp = Ask + TakeProfit * g_point;
    
    int ticket = OrderSend(Symbol(), OP_BUY, LotSize, Ask, 3, sl, tp, 
                          "XAUUSD Trend Buy", MagicNumber, 0, clrGreen);
                          
    if(ticket < 0)
        Print("OrderSend failed with error #", GetLastError());
}

//+------------------------------------------------------------------+
//| 开仓卖出                                                          |
//+------------------------------------------------------------------+
void OpenSell()
{
    double sl = Bid + StopLoss * g_point;
    double tp = Bid - TakeProfit * g_point;
    
    int ticket = OrderSend(Symbol(), OP_SELL, LotSize, Bid, 3, sl, tp, 
                          "XAUUSD Trend Sell", MagicNumber, 0, clrRed);
                          
    if(ticket < 0)
        Print("OrderSend failed with error #", GetLastError());
}

//+------------------------------------------------------------------+
//| 管理现有订单                                                       |
//+------------------------------------------------------------------+
void ManageOrders()
{
    for(int i = 0; i < OrdersTotal(); i++)
    {
        if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
            if(OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
            {
                if(OrderType() == OP_BUY)
                {
                    // 追踪止损
                    if(UseTrailingStop)
                    {
                        if(Bid - OrderOpenPrice() > TrailingStop * g_point)
                        {
                            if(OrderStopLoss() < Bid - TrailingStop * g_point)
                            {
                                bool modified = OrderModify(OrderTicket(), OrderOpenPrice(),
                                                          Bid - TrailingStop * g_point,
                                                          OrderTakeProfit(), 0, clrGreen);
                                if(!modified)
                                    Print("OrderModify failed with error #", GetLastError());
                            }
                        }
                    }
                }
                else if(OrderType() == OP_SELL)
                {
                    // 追踪止损
                    if(UseTrailingStop)
                    {
                        if(OrderOpenPrice() - Ask > TrailingStop * g_point)
                        {
                            if(OrderStopLoss() > Ask + TrailingStop * g_point || OrderStopLoss() == 0)
                            {
                                bool modified = OrderModify(OrderTicket(), OrderOpenPrice(),
                                                          Ask + TrailingStop * g_point,
                                                          OrderTakeProfit(), 0, clrRed);
                                if(!modified)
                                    Print("OrderModify failed with error #", GetLastError());
                            }
                        }
                    }
                }
            }
        }
    }
} 