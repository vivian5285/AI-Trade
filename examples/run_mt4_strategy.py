import os
import time
from dotenv import load_dotenv
from config.mt4_strategy_config import MT4StrategyConfig
from strategies.mt4_strategy import MT4Strategy

def main():
    # 加载环境变量
    load_dotenv()
    
    # 创建配置
    config = MT4StrategyConfig()
    if not config.validate():
        print("配置验证失败")
        return
        
    # 创建策略
    strategy = MT4Strategy(config.to_dict())
    if not strategy.initialize():
        print("策略初始化失败")
        return
        
    print("策略已启动")
    
    try:
        while True:
            # 获取当前行情
            ticker = strategy.client.get_ticker()
            if not ticker:
                print("获取行情失败")
                time.sleep(1)
                continue
                
            # 处理行情数据
            strategy.on_tick(ticker)
            
            # 等待下一个tick
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n策略已停止")
    except Exception as e:
        print(f"策略运行出错: {e}")
    finally:
        # 断开连接
        strategy.client.disconnect()

if __name__ == "__main__":
    main() 