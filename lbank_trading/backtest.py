import pandas as pd
import numpy as np
import talib
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import requests
import json
from typing import Dict, List, Tuple
import logging
from dataclasses import dataclass
import seaborn as sns

@dataclass
class BacktestResult:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Dict]
    equity_curve: pd.Series

class BacktestEngine:
    def __init__(self, 
                 start_date: str,
                 end_date: str,
                 trading_pair: str,
                 initial_capital: float = 10000,
                 commission: float = 0.001):
        """
        初始化回测引擎
        
        Args:
            start_date: 回测开始日期 (YYYY-MM-DD)
            end_date: 回测结束日期 (YYYY-MM-DD)
            trading_pair: 交易对
            initial_capital: 初始资金
            commission: 手续费率
        """
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        self.trading_pair = trading_pair
        self.initial_capital = initial_capital
        self.commission = commission
        
        # 回测结果
        self.positions = []
        self.trades = []
        self.equity_curve = []
        self.current_capital = initial_capital
        
        # 加载历史数据
        self.data = self._load_historical_data()
        
    def _load_historical_data(self) -> pd.DataFrame:
        """加载历史K线数据"""
        # 这里使用LBank的API获取历史数据
        # 实际使用时需要替换为真实的API调用
        url = f"https://api.lbank.info/v2/kline"
        params = {
            "symbol": self.trading_pair,
            "size": 1000,
            "type": "1min"
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            # 转换为DataFrame
            df = pd.DataFrame(data['data'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 重命名列
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            
            # 转换数据类型
            for col in df.columns:
                df[col] = pd.to_numeric(df[col])
                
            return df
            
        except Exception as e:
            logging.error(f"Error loading historical data: {e}")
            return pd.DataFrame()
            
    def calculate_indicators(self) -> pd.DataFrame:
        """计算技术指标"""
        df = self.data.copy()
        
        # 计算EMA
        df['fast_ema'] = talib.EMA(df['close'], timeperiod=12)
        df['slow_ema'] = talib.EMA(df['close'], timeperiod=26)
        
        # 计算RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # 计算布林带
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            df['close'],
            timeperiod=20,
            nbdevup=2,
            nbdevdn=2
        )
        
        return df
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        df['signal'] = 0
        
        # 趋势信号
        df['trend_signal'] = np.where(df['fast_ema'] > df['slow_ema'], 1, -1)
        
        # RSI信号
        df['rsi_signal'] = 0
        df.loc[df['rsi'] < 30, 'rsi_signal'] = 1
        df.loc[df['rsi'] > 70, 'rsi_signal'] = -1
        
        # 布林带信号
        df['bb_signal'] = 0
        df.loc[df['close'] < df['bb_lower'], 'bb_signal'] = 1
        df.loc[df['close'] > df['bb_upper'], 'bb_signal'] = -1
        
        # 综合信号
        df['signal'] = np.where(
            (df['trend_signal'] == 1) & 
            (df['rsi_signal'] == 1) & 
            (df['bb_signal'] == 1),
            1,
            np.where(
                (df['trend_signal'] == -1) & 
                (df['rsi_signal'] == -1) & 
                (df['bb_signal'] == -1),
                -1,
                0
            )
        )
        
        return df
        
    def run_backtest(self) -> BacktestResult:
        """运行回测"""
        # 计算指标和信号
        df = self.calculate_indicators()
        df = self.generate_signals(df)
        
        # 初始化回测变量
        position = 0
        entry_price = 0
        entry_time = None
        
        # 遍历数据
        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            current_time = df.index[i]
            signal = df['signal'].iloc[i]
            
            # 开仓
            if signal != 0 and position == 0:
                position = signal
                entry_price = current_price
                entry_time = current_time
                self.positions.append({
                    'type': 'entry',
                    'time': current_time,
                    'price': current_price,
                    'position': position
                })
                
            # 平仓
            elif position != 0 and (
                (position == 1 and signal == -1) or
                (position == -1 and signal == 1)
            ):
                # 计算收益
                pnl = (current_price - entry_price) * position
                commission = abs(pnl) * self.commission
                net_pnl = pnl - commission
                
                # 更新资金
                self.current_capital += net_pnl
                
                # 记录交易
                self.trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'position': position,
                    'pnl': pnl,
                    'commission': commission,
                    'net_pnl': net_pnl
                })
                
                # 重置仓位
                position = 0
                entry_price = 0
                entry_time = None
                
            # 记录权益曲线
            self.equity_curve.append(self.current_capital)
            
        # 计算回测结果
        return self._calculate_results()
        
    def _calculate_results(self) -> BacktestResult:
        """计算回测结果统计"""
        if not self.trades:
            return BacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                profit_factor=0,
                total_return=0,
                max_drawdown=0,
                sharpe_ratio=0,
                trades=[],
                equity_curve=pd.Series()
            )
            
        # 计算基本统计
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t['net_pnl'] > 0])
        losing_trades = len([t for t in self.trades if t['net_pnl'] <= 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 计算收益统计
        total_profit = sum([t['net_pnl'] for t in self.trades if t['net_pnl'] > 0])
        total_loss = abs(sum([t['net_pnl'] for t in self.trades if t['net_pnl'] <= 0]))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # 计算收益率
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital
        
        # 计算最大回撤
        equity_curve = pd.Series(self.equity_curve)
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())
        
        # 计算夏普比率
        returns = pd.Series([t['net_pnl'] for t in self.trades])
        sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if len(returns) > 1 else 0
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades=self.trades,
            equity_curve=equity_curve
        )
        
    def plot_results(self, result: BacktestResult):
        """绘制回测结果图表"""
        # 设置图表风格
        plt.style.use('seaborn')
        
        # 创建子图
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
        
        # 绘制权益曲线
        result.equity_curve.plot(ax=ax1, label='Equity Curve')
        ax1.set_title('Equity Curve')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Capital')
        ax1.grid(True)
        
        # 绘制回撤
        rolling_max = result.equity_curve.expanding().max()
        drawdowns = (result.equity_curve - rolling_max) / rolling_max
        drawdowns.plot(ax=ax2, label='Drawdown')
        ax2.set_title('Drawdown')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Drawdown')
        ax2.grid(True)
        
        # 绘制交易分布
        trade_returns = pd.Series([t['net_pnl'] for t in result.trades])
        sns.histplot(trade_returns, ax=ax3, bins=50)
        ax3.set_title('Trade Returns Distribution')
        ax3.set_xlabel('Return')
        ax3.set_ylabel('Frequency')
        ax3.grid(True)
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图表
        plt.savefig('backtest_results.png')
        plt.close()
        
    def print_results(self, result: BacktestResult):
        """打印回测结果"""
        print("\n=== 回测结果 ===")
        print(f"总交易次数: {result.total_trades}")
        print(f"盈利交易: {result.winning_trades}")
        print(f"亏损交易: {result.losing_trades}")
        print(f"胜率: {result.win_rate:.2%}")
        print(f"盈亏比: {result.profit_factor:.2f}")
        print(f"总收益率: {result.total_return:.2%}")
        print(f"最大回撤: {result.max_drawdown:.2%}")
        print(f"夏普比率: {result.sharpe_ratio:.2f}")
        
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建回测引擎
    backtest = BacktestEngine(
        start_date='2024-01-01',
        end_date='2024-02-01',
        trading_pair='BTC-USDT',
        initial_capital=10000,
        commission=0.001
    )
    
    # 运行回测
    result = backtest.run_backtest()
    
    # 打印结果
    backtest.print_results(result)
    
    # 绘制图表
    backtest.plot_results(result) 