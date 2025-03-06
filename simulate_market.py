import os
import sys
import time
import random
import json
import logging
from datetime import datetime, timedelta

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# 导入项目模块
from core.engine import RuleEngine
from data.storage import SQLiteStorage
from data.market import MarketDataClient
from strategies.high_open import HighOpenStrategy
from gateway.broker import SimulatedTradeGateway
from core.risk import RiskManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("market_simulator")

# 全局变量
prices = {}  # 全局价格字典，供其他模块使用
volumes = {}  # 全局成交量字典

class MarketSimulator:
    def __init__(self, config, engine):
        self.config = config
        self.engine = engine
        self.market_client = MarketDataClient(config.get("market_data", {}))
        self.symbols = config["strategy"]["symbols"]
        
        # 初始化价格和成交量
        global prices, volumes  # 使用全局变量
        for symbol in self.symbols:
            stock_config = config["strategy"]["stocks"][symbol]
            base_price = stock_config["high_open"]["price_threshold"]
            prices[symbol] = base_price  # 更新全局价格字典
            volumes[symbol] = 0
        
        # 实例变量引用全局变量
        self.prices = prices
        self.volumes = volumes
    
    def start(self):
        """启动模拟"""
        try:
            # 不再订阅行情数据，直接生成模拟数据
            self.simulate_trading_day()
        except KeyboardInterrupt:
            logger.info("收到中断信号,准备退出...")
    
    def simulate_trading_day(self):
        """模拟一个完整的交易日"""
        open_time = datetime.now().replace(hour=9, minute=30)
        
        # 为每个股票生成开盘K线
        for symbol in self.symbols:
            stock_config = self.config["strategy"]["stocks"][symbol]
            base_price = self.prices[symbol]
            high_open_ratio = stock_config["high_open"]["high_open_ratio"]
            
            # 生成开盘高开K线
            open_price = base_price * (1 + high_open_ratio)
            open_kline = {
                "symbol": symbol,
                "timestamp": open_time.isoformat(),
                "open": open_price,
                "high": open_price * 1.01,
                "low": open_price * 0.99,
                "close": open_price,
                "volume": 50000,
                "data_type": "kline"
            }
            
            # 发送开盘K线
            self.engine.on_market_data("kline", open_kline)
        
        # 模拟交易时段
        self.simulate_trading_session(open_time, 120)
    
    def simulate_trading_session(self, start_time, minutes):
        """模拟交易时段"""
        update_interval = self.config["market_data"].get("update_interval", 30)
        global prices  # 声明使用全局变量
        
        for minute in range(minutes):
            current_time = start_time + timedelta(minutes=minute)
            
            # 为每个股票生成行情数据
            for symbol in self.symbols:
                current_price = self.prices[symbol]
                
                # 生成价格变化
                if minute <= 30:  # 前30分钟偏向上涨
                    price_change = current_price * random.uniform(0.001, 0.003)
                else:  # 其他时间双向波动
                    price_change = current_price * random.uniform(-0.002, 0.002)
                    
                current_price += price_change
                self.prices[symbol] = current_price
                prices[symbol] = current_price  # 同时更新全局价格字典
                
                # 生成并发送行情数据
                tick_data = {
                    "symbol": symbol,
                    "price": current_price,
                    "volume": random.randint(100, 1000),
                    "timestamp": current_time.isoformat(),
                    "data_type": "tick"
                }
                
                kline_data = {
                    "symbol": symbol,
                    "open": current_price,
                    "high": current_price * 1.001,
                    "low": current_price * 0.999,
                    "close": current_price,
                    "volume": random.randint(10000, 50000),
                    "timestamp": current_time.isoformat(),
                    "timeframe": "1m",
                    "data_type": "kline"
                }
                
                # 发送行情数据（不记录日志）
                self.engine.on_market_data("tick", tick_data)
                self.engine.on_market_data("kline", kline_data)
                
                # 每5分钟显示一次价格信息
                if minute % 5 == 0:
                    base_price = self.config["strategy"]["stocks"][symbol]["high_open"]["price_threshold"]
                    logger.info(
                        f"行情更新 - {symbol} | "
                        f"时间: {current_time.strftime('%H:%M')} | "
                        f"价格: {current_price:.2f} | "
                        f"涨幅: {((current_price/base_price)-1)*100:.2f}%"
                    )
            
            time.sleep(update_interval / 1000)  # 使用配置的更新间隔


if __name__ == "__main__":
    try:
        # 加载配置
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # 初始化组件
        storage = SQLiteStorage(config.get("storage", {}))
        engine = RuleEngine(config.get("engine", {}))
        trade_gateway = SimulatedTradeGateway(config.get("trade", {}))
        
        # 设置引擎组件
        engine.storage = storage
        engine.trade_gateway = trade_gateway
        engine.risk_manager = RiskManager(config.get("risk", {}))
        
        # 初始化策略
        for symbol in config["strategy"]["symbols"]:
            strategy_config = {
                "stocks": {
                    symbol: config["strategy"]["stocks"][symbol]
                },
                "common": config["strategy"]["common"]
            }
            strategy = HighOpenStrategy(strategy_config)
            engine.register_strategy(f"high_open_{symbol}", strategy)
        
        # 启动交易系统
        engine.start()
        logger.info("交易系统启动")
        
        # 创建并启动市场模拟器
        simulator = MarketSimulator(config, engine)
        simulator.start()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号,准备退出...")
    finally:
        # 停止交易系统
        engine.stop()
        logger.info("模拟结束") 