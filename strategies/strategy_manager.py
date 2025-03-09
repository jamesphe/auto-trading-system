from typing import Dict, List
import logging
from strategies.high_open import HighOpenStrategy
from strategies.normal_open import NormalOpenStrategy
from strategies.low_open import LowOpenStrategy
from strategies.auto_trade import AutoTradeStrategy
from strategies.chandelier_exit_strategy import ChandelierExitStrategy
from core.strategy import Strategy


class StrategyManager:
    def __init__(self, broker=None):
        # 配置根日志记录器
        logging.basicConfig(level=logging.DEBUG)
        
        # 设置logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # 如果还没有处理器，添加一个控制台处理器
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            # 分成多行以符合PEP8行长度限制
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - '
                '%(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # 每个股票关联的策略列表
        self.symbol_strategies: Dict[str, List[Strategy]] = {}
        self.broker = broker
        
        # 从broker获取market_client
        if hasattr(broker, 'market_client'):
            self.market_client = broker.market_client
        elif hasattr(broker, 'engine') and hasattr(broker.engine, 'market_client'):
            self.market_client = broker.engine.market_client
        else:
            self.market_client = None
            self.logger.warning("无法从broker获取market_client")
        
        self.logger.debug("StrategyManager 初始化完成")  # 添加初始化日志
        
    def initialize(self, config: dict):
        """根据配置初始化策略"""
        try:
            stocks_config = {}
            
            # 收集所有股票的配置
            for symbol, stock_config in config.get("stocks", {}).items():
                self.logger.debug(f"股票代码: {symbol}, 配置信息: {stock_config}")
                stocks_config[symbol] = stock_config
            
            for symbol in config.get("symbols", []):
                self.symbol_strategies[symbol] = []
                
                # 获取股票特定的配置
                stock_config = stocks_config.get(symbol, {})
                strategies = stock_config.get("strategies", {})
                
                # 为每个策略配置添加market_client
                if self.market_client:
                    self.logger.debug(
                        f"使用market_client初始化策略: "
                        f"{type(self.market_client).__name__}"
                    )
                else:
                    self.logger.error("market_client未初始化，策略可能无法正常运行")
                
                # 为每个股票创建策略实例
                if strategies.get("high_open", {}).get("enabled", False):
                    self.logger.debug(f"为 {symbol} 初始化 HighOpen 策略")
                    strategy_config = {
                        "type": "HighOpen",
                        "symbols": [symbol],
                        "stocks": stocks_config
                    }
                    strategy = HighOpenStrategy(strategy_config)
                    strategy.initialize()
                    self.symbol_strategies[symbol].append(strategy)
                
                if strategies.get("normal_open", {}).get("enabled", False):
                    self.logger.debug(f"为 {symbol} 初始化 NormalOpen 策略")
                    strategy = NormalOpenStrategy()
                    strategy.initialize(strategies["normal_open"])
                    self.symbol_strategies[symbol].append(strategy)
                
                if strategies.get("low_open", {}).get("enabled", False):
                    self.logger.debug(f"为 {symbol} 初始化 LowOpen 策略")
                    strategy = LowOpenStrategy()
                    strategy.initialize(strategies["low_open"])
                    self.symbol_strategies[symbol].append(strategy)
                
                if strategies.get("auto_trade", {}).get("enabled", False):
                    self.logger.debug(f"为 {symbol} 初始化 AutoTrade 策略")
                    strategy_config = {
                        "symbol": symbol,
                        "name": stock_config.get("name", ""),
                        "position": stock_config.get("position", {}),
                        "strategies": strategies
                    }
                    strategy = AutoTradeStrategy(
                        config=strategy_config,
                        broker=self.broker
                    )
                    strategy.initialize()
                    self.symbol_strategies[symbol].append(strategy)
                
                if strategies.get("chandelier_exit", {}).get("enabled", False):
                    self.logger.debug(f"为 {symbol} 初始化 ChandelierExit 策略")
                    strategy_config = {
                        "symbol": symbol,
                        "name": stock_config.get("name", ""),
                        "position": stock_config.get("position", {}),
                        "strategies": strategies,
                        "market_client": self.market_client  # 添加market_client到配置中
                    }
                    strategy = ChandelierExitStrategy(
                        config=strategy_config,
                        broker=self.broker
                    )
                    strategy.initialize()
                    self.symbol_strategies[symbol].append(strategy)
                    self.logger.info(f"成功为 {symbol} 添加 ChandelierExit 策略")
            
            self.logger.info(f"策略初始化完成，已注册策略: {self.symbol_strategies}")
            
        except Exception as e:
            self.logger.error(f"策略初始化失败: {str(e)}", exc_info=True)
    
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
                self.logger.error(
                    f"策略 {strategy.__class__.__name__} 执行错误 "
                    f"(股票: {symbol}): {str(e)}", 
                    exc_info=True
                ) 