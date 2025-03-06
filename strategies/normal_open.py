from core.strategy import BaseStrategy
import numpy as np
from typing import Dict, Any

class NormalOpenStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any] = None):
        self.thresholds = {}
        self.boll_mid = {}
        self.position_adjusted = False
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
            
            strategy_config = stock_config.get("normal_open", {})
            
            self.upper_threshold = strategy_config.get("upper_threshold")
            self.lower_threshold = strategy_config.get("lower_threshold")
            self.boll_mid = strategy_config.get("boll_mid")
            self.volume_ratio_threshold = strategy_config.get("volume_ratio_threshold", 1.2)
            self.position_adjusted = False

    def monitor_boll(self, context):
        """监控布林带"""
        symbol = context.symbol
        if context.current_time <= "09:30:00":
            if context.current_price >= self.boll_mid:
                # 从配置获取卖出价格和比例
                sell_price = self.upper_threshold - 0.3  # 接近上轨
                sell_ratio = 0.7  # 卖出70%
                
                # 使用实际持仓计算卖出数量
                position = self.positions.get(symbol, {"volume": 0})
                sell_volume = int(position["volume"] * sell_ratio)
                
                if sell_volume > 0:
                    self.place_limit_order(
                        price=sell_price,
                        volume=sell_volume,
                        direction='SELL'
                    )
                
        if context.current_price < self.lower_threshold:
            # 清仓
            position = self.positions.get(symbol, {"volume": 0})
            if position["volume"] > 0:
                self.place_market_order(
                    volume=position["volume"],
                    direction='SELL'
                )
                # 清空持仓记录
                self.positions[symbol] = {
                    "volume": 0,
                    "cost": 0.0
                }

    def on_time(self, context):
        """定时检查"""
        symbol = context.symbol
        if context.current_time <= "14:30:00":
            volume_ratio = context.get_volume_ratio()
            position = self.positions.get(symbol, {"volume": 0})
            
            if volume_ratio > self.volume_ratio_threshold and position["volume"] > 0:
                # 从配置获取目标价格
                target_price = self.upper_threshold + 1.5  # 高于上轨1.5元
                self.place_limit_order(
                    price=target_price,
                    volume=position["volume"],
                    direction='SELL'
                )
            else:
                # 清仓
                if position["volume"] > 0:
                    self.place_market_order(
                        volume=position["volume"],
                        direction='SELL'
                    )
                    # 清空持仓记录
                    self.positions[symbol] = {
                        "volume": 0,
                        "cost": 0.0
                    } 