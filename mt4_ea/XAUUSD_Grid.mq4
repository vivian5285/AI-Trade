//+------------------------------------------------------------------+
//|                                                XAUUSD_Grid.mq4 |
//|                                                                  |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024"
#property link      ""
#property version   "1.00"
#property strict

// 输入参数
extern double LotSize = 0.1;           // 基础交易手数
extern int GridStep = 100;             // 网格间距(点数)
extern int GridLevels = 5;             // 网格层数
extern double LotMultiplier = 1.5;     // 手数乘数
extern int MagicNumber = 12346;        // EA识别号
extern int StopLoss = 500;             // 总止损点数
extern int TakeProfit = 200;           // 总止盈点数
extern bool UseTrailingStop = true;    // 使用追踪止损
extern int TrailingStop = 300;         // 追踪止损点数
extern int TrailingStep = 50;          // 追踪止损步长

// 全局变量
double g_point;
int g_digits;
double g_grid_prices[];                // 网格价格数组
int g_grid_orders[];                   // 网格订单数组

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
        
    // 初始化网格价格数组
    ArrayResize(g_grid_prices, GridLevels * 2);
    ArrayResize(g_grid_orders, GridLevels * 2);
    ArrayInitialize(g_grid_orders, 0);
    
    // 计算网格价格
    double base_price = NormalizeDouble(Close[0], g_digits);
    for(int i = 0; i < GridLevels; i++)
    {
        g_grid_prices[i] = NormalizeDouble(base_price + (i + 1) * GridStep * g_point, g_digits);
        g_grid_prices[i + GridLevels] = NormalizeDouble(base_price - (i + 1) * GridStep * g_point, g_digits);
    }
    
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
    
    // 检查是否需要开新订单
    CheckGridLevels();
}

//+------------------------------------------------------------------+
//| 检查网格水平                                                       |
//+------------------------------------------------------------------+
void CheckGridLevels()
{
    double current_price = NormalizeDouble(Close[0], g_digits);
    
    // 检查上方网格
    for(int i = 0; i < GridLevels; i++)
    {
        if(current_price >= g_grid_prices[i] && g_grid_orders[i] == 0)
        {
            OpenSell(i);
            break;
        }
    }
    
    // 检查下方网格
    for(int i = GridLevels; i < GridLevels * 2; i++)
    {
        if(current_price <= g_grid_prices[i] && g_grid_orders[i] == 0)
        {
            OpenBuy(i);
            break;
        }
    }
}

//+------------------------------------------------------------------+
//| 开仓买入                                                          |
//+------------------------------------------------------------------+
void OpenBuy(int grid_index)
{
    double lot = LotSize * MathPow(LotMultiplier, grid_index - GridLevels);
    double sl = Bid - StopLoss * g_point;
    double tp = Bid + TakeProfit * g_point;
    
    int ticket = OrderSend(Symbol(), OP_BUY, lot, Bid, 3, sl, tp, 
                          "XAUUSD Grid Buy", MagicNumber, 0, clrGreen);
                          
    if(ticket > 0)
    {
        g_grid_orders[grid_index] = ticket;
        Print("Grid Buy order opened at level ", grid_index);
    }
    else
        Print("OrderSend failed with error #", GetLastError());
}

//+------------------------------------------------------------------+
//| 开仓卖出                                                          |
//+------------------------------------------------------------------+
void OpenSell(int grid_index)
{
    double lot = LotSize * MathPow(LotMultiplier, grid_index);
    double sl = Ask + StopLoss * g_point;
    double tp = Ask - TakeProfit * g_point;
    
    int ticket = OrderSend(Symbol(), OP_SELL, lot, Ask, 3, sl, tp, 
                          "XAUUSD Grid Sell", MagicNumber, 0, clrRed);
                          
    if(ticket > 0)
    {
        g_grid_orders[grid_index] = ticket;
        Print("Grid Sell order opened at level ", grid_index);
    }
    else
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
                // 更新网格订单数组
                for(int j = 0; j < GridLevels * 2; j++)
                {
                    if(g_grid_orders[j] == OrderTicket())
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
                        break;
                    }
                }
            }
        }
    }
} 