//+------------------------------------------------------------------+
//|                                              XAUUSD_Scalping.mq4 |
//|                                                                  |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024"
#property link      ""
#property version   "1.00"
#property strict

// 输入参数
extern double LotSize = 0.1;           // 交易手数
extern int StopLoss = 50;              // 止损点数
extern int TakeProfit = 100;           // 止盈点数
extern int MagicNumber = 12345;        // EA识别号
extern int RSI_Period = 14;            // RSI周期
extern int BB_Period = 20;             // 布林带周期
extern double BB_Deviation = 2.0;      // 布林带标准差
extern int RSI_Overbought = 70;        // RSI超买水平
extern int RSI_Oversold = 30;          // RSI超卖水平
extern bool UseTrailingStop = true;    // 使用追踪止损
extern int TrailingStop = 30;          // 追踪止损点数
extern int TrailingStep = 5;           // 追踪止损步长

// 全局变量
double g_point;
int g_digits;

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
        
    // 计算指标
    double rsi = iRSI(NULL, 0, RSI_Period, PRICE_CLOSE, 0);
    double bb_upper = iBands(NULL, 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_UPPER, 0);
    double bb_lower = iBands(NULL, 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_LOWER, 0);
    double bb_middle = iBands(NULL, 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_MAIN, 0);
    
    // 检查是否已有订单
    if(OrdersTotal() > 0)
    {
        // 管理现有订单
        ManageOrders();
        return;
    }
    
    // 交易信号
    bool buySignal = (rsi < RSI_Oversold) && (Close[0] < bb_lower);
    bool sellSignal = (rsi > RSI_Overbought) && (Close[0] > bb_upper);
    
    // 执行交易
    if(buySignal)
        OpenBuy();
    else if(sellSignal)
        OpenSell();
}

//+------------------------------------------------------------------+
//| 开仓买入                                                          |
//+------------------------------------------------------------------+
void OpenBuy()
{
    double sl = Ask - StopLoss * g_point;
    double tp = Ask + TakeProfit * g_point;
    
    int ticket = OrderSend(Symbol(), OP_BUY, LotSize, Ask, 3, sl, tp, 
                          "XAUUSD Scalping Buy", MagicNumber, 0, clrGreen);
                          
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
                          "XAUUSD Scalping Sell", MagicNumber, 0, clrRed);
                          
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
                // 追踪止损
                if(UseTrailingStop)
                {
                    if(OrderType() == OP_BUY)
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
                    else if(OrderType() == OP_SELL)
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