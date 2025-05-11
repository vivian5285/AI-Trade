import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
import queue
import logging
from typing import Dict, List
import json
import requests
from dotenv import load_dotenv
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)

class TradingMonitor:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 初始化数据
        self.trading_data = {
            'equity': [],
            'positions': [],
            'trades': [],
            'pnl': []
        }
        
        # 创建数据队列
        self.data_queue = queue.Queue()
        
        # 初始化Dash应用
        self.app = dash.Dash(__name__)
        self.setup_layout()
        self.setup_callbacks()
        
    def setup_layout(self):
        """设置Dash应用布局"""
        self.app.layout = html.Div([
            html.H1('LBank Trading Bot Monitor', style={'textAlign': 'center'}),
            
            # 实时数据概览
            html.Div([
                html.Div([
                    html.H3('账户概览'),
                    html.Div(id='account-overview')
                ], className='six columns'),
                
                html.Div([
                    html.H3('当前持仓'),
                    html.Div(id='current-positions')
                ], className='six columns')
            ], className='row'),
            
            # 图表区域
            html.Div([
                dcc.Graph(id='equity-curve'),
                dcc.Graph(id='pnl-distribution'),
                dcc.Graph(id='trade-history')
            ]),
            
            # 自动刷新间隔
            dcc.Interval(
                id='interval-component',
                interval=5*1000,  # 5秒更新一次
                n_intervals=0
            )
        ])
        
    def setup_callbacks(self):
        """设置Dash回调函数"""
        @self.app.callback(
            [Output('account-overview', 'children'),
             Output('current-positions', 'children'),
             Output('equity-curve', 'figure'),
             Output('pnl-distribution', 'figure'),
             Output('trade-history', 'figure')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            # 更新数据
            self.update_data()
            
            # 生成账户概览
            account_overview = self.generate_account_overview()
            
            # 生成当前持仓
            positions_table = self.generate_positions_table()
            
            # 生成权益曲线
            equity_fig = self.generate_equity_curve()
            
            # 生成收益分布
            pnl_fig = self.generate_pnl_distribution()
            
            # 生成交易历史
            trade_fig = self.generate_trade_history()
            
            return account_overview, positions_table, equity_fig, pnl_fig, trade_fig
            
    def update_data(self):
        """更新交易数据"""
        try:
            # 从队列获取新数据
            while not self.data_queue.empty():
                data = self.data_queue.get()
                self.process_new_data(data)
                
        except Exception as e:
            logging.error(f"Error updating data: {e}")
            
    def process_new_data(self, data: Dict):
        """处理新数据"""
        if 'equity' in data:
            self.trading_data['equity'].append({
                'timestamp': datetime.now(),
                'value': data['equity']
            })
            
        if 'position' in data:
            self.trading_data['positions'].append({
                'timestamp': datetime.now(),
                'position': data['position']
            })
            
        if 'trade' in data:
            self.trading_data['trades'].append({
                'timestamp': datetime.now(),
                'trade': data['trade']
            })
            
        if 'pnl' in data:
            self.trading_data['pnl'].append({
                'timestamp': datetime.now(),
                'value': data['pnl']
            })
            
    def generate_account_overview(self) -> html.Div:
        """生成账户概览"""
        if not self.trading_data['equity']:
            return html.Div('No data available')
            
        latest_equity = self.trading_data['equity'][-1]['value']
        initial_equity = self.trading_data['equity'][0]['value']
        total_return = (latest_equity - initial_equity) / initial_equity
        
        return html.Div([
            html.P(f'当前权益: {latest_equity:.2f} USDT'),
            html.P(f'总收益率: {total_return:.2%}'),
            html.P(f'总交易次数: {len(self.trading_data["trades"])}'),
            html.P(f'当前持仓数量: {len(self.trading_data["positions"])}')
        ])
        
    def generate_positions_table(self) -> html.Table:
        """生成持仓表格"""
        if not self.trading_data['positions']:
            return html.Table([])
            
        return html.Table([
            html.Thead(
                html.Tr([
                    html.Th('交易对'),
                    html.Th('方向'),
                    html.Th('数量'),
                    html.Th('开仓价格'),
                    html.Th('当前价格'),
                    html.Th('未实现盈亏')
                ])
            ),
            html.Tbody([
                html.Tr([
                    html.Td(pos['position']['symbol']),
                    html.Td(pos['position']['side']),
                    html.Td(pos['position']['amount']),
                    html.Td(pos['position']['entry_price']),
                    html.Td(pos['position']['current_price']),
                    html.Td(pos['position']['unrealized_pnl'])
                ]) for pos in self.trading_data['positions']
            ])
        ])
        
    def generate_equity_curve(self) -> go.Figure:
        """生成权益曲线"""
        if not self.trading_data['equity']:
            return go.Figure()
            
        df = pd.DataFrame(self.trading_data['equity'])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['value'],
            mode='lines',
            name='Equity'
        ))
        
        fig.update_layout(
            title='Equity Curve',
            xaxis_title='Time',
            yaxis_title='Equity (USDT)',
            showlegend=True
        )
        
        return fig
        
    def generate_pnl_distribution(self) -> go.Figure:
        """生成收益分布图"""
        if not self.trading_data['pnl']:
            return go.Figure()
            
        pnl_values = [p['value'] for p in self.trading_data['pnl']]
        
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=pnl_values,
            nbinsx=50,
            name='PnL Distribution'
        ))
        
        fig.update_layout(
            title='PnL Distribution',
            xaxis_title='PnL (USDT)',
            yaxis_title='Frequency',
            showlegend=True
        )
        
        return fig
        
    def generate_trade_history(self) -> go.Figure:
        """生成交易历史图"""
        if not self.trading_data['trades']:
            return go.Figure()
            
        df = pd.DataFrame([
            {
                'timestamp': t['timestamp'],
                'pnl': t['trade']['pnl']
            } for t in self.trading_data['trades']
        ])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['pnl'].cumsum(),
            mode='lines',
            name='Cumulative PnL'
        ))
        
        fig.update_layout(
            title='Trade History',
            xaxis_title='Time',
            yaxis_title='Cumulative PnL (USDT)',
            showlegend=True
        )
        
        return fig
        
    def add_data(self, data: Dict):
        """添加新数据到队列"""
        self.data_queue.put(data)
        
    def run(self, host: str = 'localhost', port: int = 8050):
        """运行监控系统"""
        self.app.run_server(host=host, port=port, debug=True)
        
if __name__ == "__main__":
    # 创建监控实例
    monitor = TradingMonitor()
    
    # 运行监控系统
    monitor.run() 