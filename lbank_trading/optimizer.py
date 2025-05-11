import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import logging
from sklearn.model_selection import ParameterGrid
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import optuna
import joblib
from concurrent.futures import ProcessPoolExecutor
import json
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from .backtest import BacktestEngine, BacktestResult

@dataclass
class OptimizationResult:
    best_params: Dict[str, Any]
    best_score: float
    all_results: List[Dict[str, Any]]
    optimization_history: pd.DataFrame

class StrategyOptimizer:
    def __init__(self, 
                 trading_pair: str,
                 start_date: str,
                 end_date: str,
                 initial_capital: float = 10000):
        """
        初始化策略优化器
        
        Args:
            trading_pair: 交易对
            start_date: 优化开始日期
            end_date: 优化结束日期
            initial_capital: 初始资金
        """
        self.trading_pair = trading_pair
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        
        # 定义参数空间
        self.param_space = {
            'fast_ema': range(5, 21, 2),
            'slow_ema': range(20, 51, 5),
            'rsi_period': range(10, 31, 2),
            'rsi_overbought': range(65, 81, 5),
            'rsi_oversold': range(15, 36, 5),
            'bb_period': range(15, 41, 5),
            'bb_std': [1.5, 2.0, 2.5],
            'stop_loss': [0.01, 0.02, 0.03],
            'take_profit': [0.02, 0.03, 0.04]
        }
        
        # 初始化优化历史
        self.optimization_history = []
        
    def objective(self, trial: optuna.Trial) -> float:
        """优化目标函数"""
        # 生成参数
        params = {
            'fast_ema': trial.suggest_int('fast_ema', 5, 20),
            'slow_ema': trial.suggest_int('slow_ema', 20, 50),
            'rsi_period': trial.suggest_int('rsi_period', 10, 30),
            'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 80),
            'rsi_oversold': trial.suggest_int('rsi_oversold', 15, 35),
            'bb_period': trial.suggest_int('bb_period', 15, 40),
            'bb_std': trial.suggest_float('bb_std', 1.5, 2.5),
            'stop_loss': trial.suggest_float('stop_loss', 0.01, 0.03),
            'take_profit': trial.suggest_float('take_profit', 0.02, 0.04)
        }
        
        # 运行回测
        backtest = BacktestEngine(
            start_date=self.start_date,
            end_date=self.end_date,
            trading_pair=self.trading_pair,
            initial_capital=self.initial_capital
        )
        
        # 设置参数
        backtest.set_parameters(params)
        
        # 运行回测
        result = backtest.run_backtest()
        
        # 计算优化目标（综合评分）
        score = self._calculate_score(result)
        
        # 记录优化历史
        self.optimization_history.append({
            'params': params,
            'score': score,
            'total_return': result.total_return,
            'max_drawdown': result.max_drawdown,
            'sharpe_ratio': result.sharpe_ratio,
            'win_rate': result.win_rate
        })
        
        return score
        
    def _calculate_score(self, result: BacktestResult) -> float:
        """计算策略评分"""
        # 综合评分公式
        score = (
            result.total_return * 0.3 +  # 总收益率权重
            (1 - result.max_drawdown) * 0.2 +  # 最大回撤权重
            result.sharpe_ratio * 0.2 +  # 夏普比率权重
            result.win_rate * 0.2 +  # 胜率权重
            (result.profit_factor - 1) * 0.1  # 盈亏比权重
        )
        
        return score
        
    def optimize(self, n_trials: int = 100) -> OptimizationResult:
        """运行优化过程"""
        # 创建优化研究
        study = optuna.create_study(direction='maximize')
        
        # 运行优化
        study.optimize(self.objective, n_trials=n_trials)
        
        # 获取最佳结果
        best_params = study.best_params
        best_score = study.best_value
        
        # 转换优化历史为DataFrame
        history_df = pd.DataFrame(self.optimization_history)
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_results=self.optimization_history,
            optimization_history=history_df
        )
        
    def plot_optimization_results(self, result: OptimizationResult):
        """绘制优化结果图表"""
        # 设置图表风格
        plt.style.use('seaborn')
        
        # 创建子图
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # 绘制参数重要性
        param_importance = pd.DataFrame({
            'parameter': list(result.best_params.keys()),
            'importance': [abs(v) for v in result.best_params.values()]
        })
        sns.barplot(data=param_importance, x='importance', y='parameter', ax=ax1)
        ax1.set_title('Parameter Importance')
        
        # 绘制优化历史
        result.optimization_history['score'].plot(ax=ax2)
        ax2.set_title('Optimization History')
        ax2.set_xlabel('Trial')
        ax2.set_ylabel('Score')
        
        # 绘制参数分布
        for param in ['total_return', 'max_drawdown']:
            sns.histplot(data=result.optimization_history, x=param, ax=ax3)
        ax3.set_title('Parameter Distribution')
        
        # 绘制相关性热图
        corr_matrix = result.optimization_history[['score', 'total_return', 'max_drawdown', 'sharpe_ratio', 'win_rate']].corr()
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', ax=ax4)
        ax4.set_title('Correlation Matrix')
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图表
        plt.savefig('optimization_results.png')
        plt.close()
        
    def save_results(self, result: OptimizationResult, filename: str = 'optimization_results.json'):
        """保存优化结果"""
        # 准备保存数据
        save_data = {
            'best_params': result.best_params,
            'best_score': result.best_score,
            'optimization_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'trading_pair': self.trading_pair,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'all_results': result.all_results
        }
        
        # 保存到文件
        with open(filename, 'w') as f:
            json.dump(save_data, f, indent=4)
            
    def load_results(self, filename: str = 'optimization_results.json') -> OptimizationResult:
        """加载优化结果"""
        with open(filename, 'r') as f:
            data = json.load(f)
            
        return OptimizationResult(
            best_params=data['best_params'],
            best_score=data['best_score'],
            all_results=data['all_results'],
            optimization_history=pd.DataFrame(data['all_results'])
        )
        
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建优化器
    optimizer = StrategyOptimizer(
        trading_pair='BTC-USDT',
        start_date='2024-01-01',
        end_date='2024-02-01',
        initial_capital=10000
    )
    
    # 运行优化
    result = optimizer.optimize(n_trials=100)
    
    # 绘制结果
    optimizer.plot_optimization_results(result)
    
    # 保存结果
    optimizer.save_results(result) 