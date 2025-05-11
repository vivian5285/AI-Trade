from flask import Flask, render_template, request, redirect, url_for, flash
import os
from dotenv import load_dotenv
import json
import pandas as pd
import plotly
import plotly.graph_objs as go
from binance.client import Client
import requests
import hmac
import hashlib
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# 加载配置
def load_config():
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {
        'binance_api_key': '',
        'binance_api_secret': '',
        'lbank_api_key': '',
        'lbank_api_secret': '',
        'trading_settings': {
            'trading_pair': 'BTC-USDT',
            'leverage': '10',
            'quantity': '0.001',
            'stop_loss': '0.3',
            'take_profit': '0.6'
        }
    }

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

# 路由
@app.route('/')
def dashboard():
    config = load_config()
    
    # 获取账户信息
    binance_balance = get_binance_balance(config) if config['binance_api_key'] else None
    lbank_balance = get_lbank_balance(config) if config['lbank_api_key'] else None
    
    # 获取交易历史
    binance_trades = get_binance_trades(config) if config['binance_api_key'] else []
    lbank_trades = get_lbank_trades(config) if config['lbank_api_key'] else []
    
    # 生成图表
    binance_chart = create_balance_chart(binance_trades) if binance_trades else None
    lbank_chart = create_balance_chart(lbank_trades) if lbank_trades else None
    
    return render_template('dashboard.html',
                         binance_balance=binance_balance,
                         lbank_balance=lbank_balance,
                         binance_chart=binance_chart,
                         lbank_chart=lbank_chart)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    config = load_config()
    
    if request.method == 'POST':
        # 更新API密钥
        config['binance_api_key'] = request.form.get('binance_api_key')
        config['binance_api_secret'] = request.form.get('binance_api_secret')
        config['lbank_api_key'] = request.form.get('lbank_api_key')
        config['lbank_api_secret'] = request.form.get('lbank_api_secret')
        
        # 更新交易设置
        config['trading_settings'] = {
            'trading_pair': request.form.get('trading_pair'),
            'leverage': request.form.get('leverage'),
            'quantity': request.form.get('quantity'),
            'stop_loss': request.form.get('stop_loss'),
            'take_profit': request.form.get('take_profit')
        }
        
        save_config(config)
        flash('Settings updated successfully')
        return redirect(url_for('settings'))
        
    return render_template('settings.html',
                         config=config,
                         trading_settings=config['trading_settings'])

# API函数
def get_binance_balance(config):
    try:
        client = Client(config['binance_api_key'], config['binance_api_secret'])
        account = client.futures_account_balance()
        return {balance['asset']: float(balance['balance']) for balance in account}
    except Exception as e:
        flash(f'Error getting Binance balance: {str(e)}')
        return None

def get_lbank_balance(config):
    try:
        timestamp = str(int(time.time() * 1000))
        params = {
            'api_key': config['lbank_api_key'],
            'timestamp': timestamp
        }
        sign = generate_lbank_sign(params, config['lbank_api_secret'])
        params['sign'] = sign
        
        response = requests.get('https://api.lbank.info/v2/user/account', params=params)
        data = response.json()
        
        if data['result']:
            return {balance['asset']: float(balance['balance']) for balance in data['data']}
        return None
    except Exception as e:
        flash(f'Error getting LBank balance: {str(e)}')
        return None

def get_binance_trades(config):
    try:
        client = Client(config['binance_api_key'], config['binance_api_secret'])
        trades = client.futures_account_trades()
        return trades
    except Exception as e:
        flash(f'Error getting Binance trades: {str(e)}')
        return []

def get_lbank_trades(config):
    try:
        timestamp = str(int(time.time() * 1000))
        params = {
            'api_key': config['lbank_api_key'],
            'timestamp': timestamp
        }
        sign = generate_lbank_sign(params, config['lbank_api_secret'])
        params['sign'] = sign
        
        response = requests.get('https://api.lbank.info/v2/order_history', params=params)
        data = response.json()
        
        if data['result']:
            return data['data']
        return []
    except Exception as e:
        flash(f'Error getting LBank trades: {str(e)}')
        return []

def generate_lbank_sign(params, api_secret):
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
    return hmac.new(
        api_secret.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest()

def create_balance_chart(trades):
    if not trades:
        return None
        
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
    df['balance'] = df['realizedPnl'].cumsum()
    
    trace = go.Scatter(
        x=df['timestamp'],
        y=df['balance'],
        mode='lines',
        name='Balance'
    )
    
    layout = go.Layout(
        title='Account Balance Over Time',
        xaxis={'title': 'Time'},
        yaxis={'title': 'Balance (USDT)'}
    )
    
    fig = go.Figure(data=[trace], layout=layout)
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 