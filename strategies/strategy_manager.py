from typing import Dict, List
from strategies.high_open import HighOpenStrategy
from strategies.normal_open import NormalOpenStrategy
from strategies.low_open import LowOpenStrategy
from strategies.auto_trade import AutoTradeStrategy
from core.strategy import Strategy


class StrategyManager:
    def __init__(self, broker=None):
        # 每个股票关联的策略列表
        self.symbol_strategies: Dict[str, List[Strategy]] = {}
        self.broker = broker
        
    def initialize(self, config: dict):
        """根据配置初始化策略"""
        stocks_config = {}
        
        # 收集所有股票的配置
        for symbol, stock_config in config.get("stocks", {}).items():
            print(f"股票代码: {symbol}, 配置信息: {stock_config}")
            stocks_config[symbol] = stock_config
        
        for symbol in config.get("symbols", []):
            self.symbol_strategies[symbol] = []
            
            # 为每个股票创建策略实例，传入完整配置
            if config.get("high_open", {}).get("enabled", False):
                strategy_config = {
                    "type": "HighOpen",
                    "symbols": [symbol],
                    "stocks": stocks_config  # 传入完整的股票配置
                }
                strategy = HighOpenStrategy(strategy_config)
                strategy.initialize()
                self.symbol_strategies[symbol].append(strategy)
                
            if config.get("normal_open", {}).get("enabled", False):
                strategy = NormalOpenStrategy()
                strategy.initialize(config["normal_open"].get("params", {}))
                self.symbol_strategies[symbol].append(strategy)
                
            if config.get("low_open", {}).get("enabled", False):
                strategy = LowOpenStrategy()
                strategy.initialize(config["low_open"].get("params", {}))
                self.symbol_strategies[symbol].append(strategy)
            
            if config.get("auto_trade", {}).get("enabled", False):
                strategy_config = {
                    "type": "AutoTrade",
                    "symbols": [symbol],
                    "stocks": stocks_config,
                    "auto_trade": config.get("auto_trade", {})
                }
                strategy = AutoTradeStrategy(
                    strategy_config, 
                    broker=self.broker
                )
                strategy.initialize()
                self.symbol_strategies[symbol].append(strategy)
    
    def get_strategies(self, symbol: str) -> List[Strategy]:
        """获取股票关联的所有策略"""
        return self.symbol_strategies.get(symbol, [])
    
    def on_market_data(self, market_data: dict):
        """处理市场数据"""
        symbol = market_data["symbol"]
        strategies = self.get_strategies(symbol)
        
        for strategy in strategies:
            try:
                strategy.execute(market_data)
            except Exception as e:
                logging.error(f"策略执行错误: {str(e)}", exc_info=True) 