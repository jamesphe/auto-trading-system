from core.strategy import BaseStrategy
import numpy as np
from typing import Dict, Any

class LowOpenStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any] = None):
        self.thresholds = {}
        self.orders_placed = False
        self.positions = {}  # 初始化持仓信息
        super().__init__(config)
        
    def initialize(self):
        """初始化策略"""
        # 从配置中读取参数
        for symbol, stock_config in self.config.get("stocks", {}).items():
            # 读取持仓信息
            position_info = stock_config.get("position", {})
            self.positions[symbol] = {
                "volume": position_info.get("volume", 0),
                "cost": position_info.get("cost", 0.0)
            }
            
            self.logger.info(
                f"加载股票 {symbol} 持仓信息:\n"
                f"  持仓量: {self.positions[symbol]['volume']}\n"
                f"  成本价: {self.positions[symbol]['cost']:.2f}"
            )
            
            strategy_config = stock_config.get("low_open", {})
            
            self.threshold = strategy_config.get("threshold")
            self.stop_loss_threshold = strategy_config.get("stop_loss_threshold", -0.05)
            self.orders_placed = False

    def on_market_open(self, context):
        """开盘处理"""
        symbol = context.symbol
        open_price = context.current_price
        
        if open_price < self.threshold:
            position = self.positions.get(symbol, {"volume": 0})
            if position["volume"] > 0:
                # 从配置获取卖出价格和比例
                sell_price = self.threshold - 0.5  # 低于阈值0.5元
                sell_ratio = 0.4  # 卖出40%
                sell_volume = int(position["volume"] * sell_ratio)
                
                if sell_volume > 0:
                    self.place_limit_order(
                        price=sell_price,
                        volume=sell_volume,
                        direction='SELL'
                    )

    def on_time(self, context):
        """定时检查"""
        symbol = context.symbol
        position = self.positions.get(symbol, {"volume": 0})
        
        if context.current_time == "09:45:00":
            # 从配置获取反弹目标价
            bounce_price = self.threshold - 0.2  # 低于阈值0.2元
            if context.current_price < bounce_price and position["volume"] > 0:
                # 从配置获取卖出比例
                sell_ratio = 0.6  # 卖出60%
                sell_volume = int(position["volume"] * sell_ratio)
                
                if sell_volume > 0:
                    self.place_market_order(
                        volume=sell_volume,
                        direction='SELL'
                    )
            
        # 检查跌幅
        daily_return = (context.current_price / context.prev_close - 1) * 100
        if daily_return < self.stop_loss_threshold:
            # 停止交易,等待尾盘清仓
            self.stop_trading = True
        elif (context.current_price >= self.threshold + 0.3 and 
              not self.orders_placed and position["volume"] > 0):
            # 设置限价单
            self.place_limit_order(
                price=self.threshold + 0.3,
                volume=position["volume"],
                direction='SELL'
            )
            self.orders_placed = True 