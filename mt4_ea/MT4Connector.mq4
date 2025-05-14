//+------------------------------------------------------------------+
//|                                                    MT4Connector.mq4 |
//|                                                                     |
//|                                                                     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024"
#property link      ""
#property version   "1.00"
#property strict

// 全局变量
int socket = INVALID_SOCKET;
bool isConnected = false;
string server = "localhost";
int port = 8222;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    // 初始化Socket
    socket = SocketCreate();
    if(socket == INVALID_SOCKET)
    {
        Print("Socket创建失败");
        return INIT_FAILED;
    }
    
    // 绑定端口
    if(!SocketBind(socket, server, port))
    {
        Print("Socket绑定失败");
        SocketClose(socket);
        return INIT_FAILED;
    }
    
    // 开始监听
    if(!SocketListen(socket, 1))
    {
        Print("Socket监听失败");
        SocketClose(socket);
        return INIT_FAILED;
    }
    
    Print("MT4连接器已启动");
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(socket != INVALID_SOCKET)
    {
        SocketClose(socket);
    }
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
    if(!isConnected)
    {
        // 等待客户端连接
        int clientSocket = SocketAccept(socket);
        if(clientSocket != INVALID_SOCKET)
        {
            isConnected = true;
            Print("客户端已连接");
        }
        return;
    }
    
    // 处理客户端请求
    string request = "";
    if(SocketIsReadable(socket))
    {
        char buffer[1024];
        int bytes = SocketRead(socket, buffer, 1024);
        if(bytes > 0)
        {
            request = CharArrayToString(buffer);
            ProcessRequest(request);
        }
    }
}

//+------------------------------------------------------------------+
//| 处理客户端请求                                                      |
//+------------------------------------------------------------------+
void ProcessRequest(string request)
{
    // 解析JSON请求
    string command = "";
    string params = "";
    
    // 解析命令和参数
    int pos = StringFind(request, "\"command\":");
    if(pos >= 0)
    {
        int start = StringFind(request, "\"", pos + 10) + 1;
        int end = StringFind(request, "\"", start);
        command = StringSubstr(request, start, end - start);
    }
    
    pos = StringFind(request, "\"params\":");
    if(pos >= 0)
    {
        int start = StringFind(request, "{", pos + 8);
        int end = StringFind(request, "}", start);
        params = StringSubstr(request, start, end - start + 1);
    }
    
    // 处理命令
    string response = "";
    if(command == "GET_BALANCE")
    {
        response = GetBalance();
    }
    else if(command == "GET_POSITION")
    {
        response = GetPosition(params);
    }
    else if(command == "GET_HISTORY")
    {
        response = GetHistory(params);
    }
    else if(command == "PLACE_ORDER")
    {
        response = PlaceOrder(params);
    }
    else if(command == "CANCEL_ORDER")
    {
        response = CancelOrder(params);
    }
    else if(command == "GET_ORDER")
    {
        response = GetOrder(params);
    }
    else if(command == "GET_OPEN_ORDERS")
    {
        response = GetOpenOrders(params);
    }
    else if(command == "GET_TRADES")
    {
        response = GetTrades(params);
    }
    else if(command == "SET_LEVERAGE")
    {
        response = SetLeverage(params);
    }
    else if(command == "GET_TICKER")
    {
        response = GetTicker(params);
    }
    
    // 发送响应
    if(response != "")
    {
        SocketSend(socket, response);
    }
}

//+------------------------------------------------------------------+
//| 获取账户余额                                                        |
//+------------------------------------------------------------------+
string GetBalance()
{
    double balance = AccountBalance();
    return StringFormat("{\"balance\":%.2f}", balance);
}

//+------------------------------------------------------------------+
//| 获取当前持仓                                                        |
//+------------------------------------------------------------------+
string GetPosition(string params)
{
    string symbol = "";
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    for(int i = 0; i < OrdersTotal(); i++)
    {
        if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
            if(OrderSymbol() == symbol)
            {
                return StringFormat(
                    "{\"position\":{\"type\":%d,\"volume\":%.2f,\"price\":%.5f,\"sl\":%.5f,\"tp\":%.5f}}",
                    OrderType(),
                    OrderLots(),
                    OrderOpenPrice(),
                    OrderStopLoss(),
                    OrderTakeProfit()
                );
            }
        }
    }
    
    return "{\"position\":null}";
}

//+------------------------------------------------------------------+
//| 获取历史数据                                                        |
//+------------------------------------------------------------------+
string GetHistory(string params)
{
    string symbol = "";
    string interval = "1m";
    int limit = 100;
    
    // 解析参数
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    pos = StringFind(params, "\"interval\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 11) + 1;
        int end = StringFind(params, "\"", start);
        interval = StringSubstr(params, start, end - start);
    }
    
    pos = StringFind(params, "\"limit\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 7);
        int end = StringFind(params, ",", start);
        limit = (int)StringToInteger(StringSubstr(params, start + 1, end - start - 1));
    }
    
    // 获取历史数据
    string result = "{\"data\":[";
    int timeframe = PERIOD_M1;
    
    if(interval == "5m") timeframe = PERIOD_M5;
    else if(interval == "15m") timeframe = PERIOD_M15;
    else if(interval == "30m") timeframe = PERIOD_M30;
    else if(interval == "1h") timeframe = PERIOD_H1;
    else if(interval == "4h") timeframe = PERIOD_H4;
    else if(interval == "1d") timeframe = PERIOD_D1;
    
    for(int i = 0; i < limit; i++)
    {
        if(i > 0) result += ",";
        result += StringFormat(
            "{\"time\":\"%s\",\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%.2f}",
            TimeToStr(iTime(symbol, timeframe, i)),
            iOpen(symbol, timeframe, i),
            iHigh(symbol, timeframe, i),
            iLow(symbol, timeframe, i),
            iClose(symbol, timeframe, i),
            iVolume(symbol, timeframe, i)
        );
    }
    
    result += "]}";
    return result;
}

//+------------------------------------------------------------------+
//| 下单                                                               |
//+------------------------------------------------------------------+
string PlaceOrder(string params)
{
    string symbol = "";
    int type = 0;
    double volume = 0;
    double price = 0;
    int magic = 0;
    
    // 解析参数
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    pos = StringFind(params, "\"type\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 6);
        int end = StringFind(params, ",", start);
        type = (int)StringToInteger(StringSubstr(params, start + 1, end - start - 1));
    }
    
    pos = StringFind(params, "\"volume\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 8);
        int end = StringFind(params, ",", start);
        volume = StringToDouble(StringSubstr(params, start + 1, end - start - 1));
    }
    
    pos = StringFind(params, "\"price\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 7);
        int end = StringFind(params, ",", start);
        price = StringToDouble(StringSubstr(params, start + 1, end - start - 1));
    }
    
    pos = StringFind(params, "\"magic\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 7);
        int end = StringFind(params, "}", start);
        magic = (int)StringToInteger(StringSubstr(params, start + 1, end - start - 1));
    }
    
    // 下单
    int ticket = OrderSend(symbol, type, volume, price, 3, 0, 0, "", magic);
    
    if(ticket > 0)
    {
        return StringFormat("{\"order\":{\"ticket\":%d,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,\"price\":%.5f}}",
            ticket, symbol, type, volume, price);
    }
    else
    {
        return StringFormat("{\"error\":\"%s\"}", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| 取消订单                                                           |
//+------------------------------------------------------------------+
string CancelOrder(string params)
{
    int ticket = 0;
    
    // 解析参数
    int pos = StringFind(params, "\"order_id\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 10);
        int end = StringFind(params, "}", start);
        ticket = (int)StringToInteger(StringSubstr(params, start + 1, end - start - 1));
    }
    
    // 取消订单
    if(OrderSelect(ticket, SELECT_BY_TICKET))
    {
        bool result = OrderDelete(ticket);
        return StringFormat("{\"success\":%s}", result ? "true" : "false");
    }
    
    return "{\"success\":false}";
}

//+------------------------------------------------------------------+
//| 获取订单信息                                                        |
//+------------------------------------------------------------------+
string GetOrder(string params)
{
    int ticket = 0;
    
    // 解析参数
    int pos = StringFind(params, "\"order_id\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 10);
        int end = StringFind(params, "}", start);
        ticket = (int)StringToInteger(StringSubstr(params, start + 1, end - start - 1));
    }
    
    // 获取订单信息
    if(OrderSelect(ticket, SELECT_BY_TICKET))
    {
        return StringFormat(
            "{\"order\":{\"ticket\":%d,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,\"price\":%.5f,\"sl\":%.5f,\"tp\":%.5f}}",
            OrderTicket(),
            OrderSymbol(),
            OrderType(),
            OrderLots(),
            OrderOpenPrice(),
            OrderStopLoss(),
            OrderTakeProfit()
        );
    }
    
    return "{\"order\":null}";
}

//+------------------------------------------------------------------+
//| 获取未完成订单                                                      |
//+------------------------------------------------------------------+
string GetOpenOrders(string params)
{
    string symbol = "";
    
    // 解析参数
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    // 获取未完成订单
    string result = "{\"orders\":[";
    bool first = true;
    
    for(int i = 0; i < OrdersTotal(); i++)
    {
        if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
            if(OrderSymbol() == symbol)
            {
                if(!first) result += ",";
                first = false;
                
                result += StringFormat(
                    "{\"ticket\":%d,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,\"price\":%.5f,\"sl\":%.5f,\"tp\":%.5f}",
                    OrderTicket(),
                    OrderSymbol(),
                    OrderType(),
                    OrderLots(),
                    OrderOpenPrice(),
                    OrderStopLoss(),
                    OrderTakeProfit()
                );
            }
        }
    }
    
    result += "]}";
    return result;
}

//+------------------------------------------------------------------+
//| 获取交易历史                                                        |
//+------------------------------------------------------------------+
string GetTrades(string params)
{
    string symbol = "";
    
    // 解析参数
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    // 获取交易历史
    string result = "{\"trades\":[";
    bool first = true;
    
    for(int i = 0; i < OrdersHistoryTotal(); i++)
    {
        if(OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
        {
            if(OrderSymbol() == symbol)
            {
                if(!first) result += ",";
                first = false;
                
                result += StringFormat(
                    "{\"ticket\":%d,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,\"price\":%.5f,\"profit\":%.2f,\"time\":\"%s\"}",
                    OrderTicket(),
                    OrderSymbol(),
                    OrderType(),
                    OrderLots(),
                    OrderOpenPrice(),
                    OrderProfit(),
                    TimeToStr(OrderCloseTime())
                );
            }
        }
    }
    
    result += "]}";
    return result;
}

//+------------------------------------------------------------------+
//| 设置杠杆                                                           |
//+------------------------------------------------------------------+
string SetLeverage(string params)
{
    string symbol = "";
    int leverage = 0;
    
    // 解析参数
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    pos = StringFind(params, "\"leverage\":");
    if(pos >= 0)
    {
        int start = StringFind(params, ":", pos + 10);
        int end = StringFind(params, "}", start);
        leverage = (int)StringToInteger(StringSubstr(params, start + 1, end - start - 1));
    }
    
    // 设置杠杆
    bool result = MarketInfo(symbol, MODE_MARGINREQUIRED) > 0;
    return StringFormat("{\"success\":%s}", result ? "true" : "false");
}

//+------------------------------------------------------------------+
//| 获取当前行情                                                        |
//+------------------------------------------------------------------+
string GetTicker(string params)
{
    string symbol = "";
    
    // 解析参数
    int pos = StringFind(params, "\"symbol\":");
    if(pos >= 0)
    {
        int start = StringFind(params, "\"", pos + 9) + 1;
        int end = StringFind(params, "\"", start);
        symbol = StringSubstr(params, start, end - start);
    }
    
    // 获取行情
    return StringFormat(
        "{\"ticker\":{\"symbol\":\"%s\",\"bid\":%.5f,\"ask\":%.5f,\"last\":%.5f,\"volume\":%.2f}}",
        symbol,
        MarketInfo(symbol, MODE_BID),
        MarketInfo(symbol, MODE_ASK),
        MarketInfo(symbol, MODE_LAST),
        MarketInfo(symbol, MODE_VOLUME)
    );
} 