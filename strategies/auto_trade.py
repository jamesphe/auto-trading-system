from typing import Dict, Any
import logging
from datetime import datetime, timedelta
import numpy as np
import talib as ta
from core.strategy import BaseStrategy
from core.order import Order, OrderStatus
import os
import json

class AutoTradeStrategy(BaseStrategy):
    """自动盯盘交易策略
    
    结合价格、成交量、RSI和BOLL等技术指标进行交易决策
    """
    
    def __init__(self, config: Dict[str, Any] = None, broker=None):
        """初始化策略"""
        self.broker = broker  # 需要在super().__init__之前设置broker
        self.logger = logging.getLogger("strategy.AutoTrade")
        self.logger.setLevel(logging.INFO)
        
        # 初始化数据缓存
        self.daily_price_cache = {}  # 日线价格数据
        self.daily_volume_cache = {}  # 日线成交量数据
        self.daily_indicators = {}  # 日线技术指标缓存
        self.intraday_price_cache = {}  # 日内TICK价格数据
        self.intraday_volume_cache = {}  # 日内TICK成交量数据
        self.subscriptions = {}  # 初始化订阅列表
        
        super().__init__(config)
    
    def _init(self):
        """初始化策略"""
        pass  # 因为我们已经在__init__中完成了初始化
    
    def _load_daily_history_data(self):
        """加载历史日线数据"""
        self.logger.debug("开始加载历史日线数据")
        try:
            if not self.broker:
                self.logger.error("broker未设置")
                return
            
            if not hasattr(self.broker, 'market_client'):
                self.logger.error("broker没有market_client属性")
                return
                
            # 获取当前时间和30天前的时间
            end = datetime.now()
            start = end - timedelta(days=30)  # 获取近30天数据
            self.logger.debug(f"历史数据时间范围: {start} 到 {end}")
            
            self.logger.debug(f"当前订阅列表: {self.subscriptions}")
            # 遍历订阅的股票代码
            for symbol in self.subscriptions:
                self.logger.debug(f"开始获取 {symbol} 的历史数据")
                # 通过market_client获取历史数据
                df = self.broker.market_client.get_history(
                    symbol=symbol,
                    start=start,
                    end=end,
                    timeframe="1d"
                )
                
                self.logger.debug(f"获取到的数据: {df}")
                
                if df.empty:
                    self.logger.warning(f"获取{symbol}的历史数据为空")
                    continue
                    
                # 将数据保存到缓存中
                self.daily_price_cache[symbol] = df['close'].values.tolist()
                self.daily_volume_cache[symbol] = df['volume'].values.tolist()
                
                self.logger.info(
                    f"加载{symbol}历史数据:\n"
                    f"  数据长度: {len(df)}\n"
                    f"  开始日期: {df['timestamp'].iloc[0]}\n" 
                    f"  结束日期: {df['timestamp'].iloc[-1]}"
                )
                
        except Exception as e:
            self.logger.error(f"加载历史数据失败: {e}", exc_info=True)
            raise

    def _calculate_daily_indicators(self):
        """计算日线技术指标"""
        for symbol in self.daily_price_cache:
            # 将列表转换为numpy数组，并确保数据类型为float64
            prices = np.array(self.daily_price_cache[symbol], dtype=np.float64)
            volumes = np.array(self.daily_volume_cache[symbol], dtype=np.float64)
            
            if len(prices) < self.boll_period:
                continue
            
            # 计算RSI
            rsi = ta.RSI(prices, timeperiod=self.rsi_period)[-1]
            
            # 计算BOLL
            upper, middle, lower = ta.BBANDS(
                prices,
                timeperiod=self.boll_period,
                nbdevup=self.boll_std,
                nbdevdn=self.boll_std
            )
            
            # 计算成交量均线
            volume_ma = ta.MA(volumes, timeperiod=self.volume_ma_period)[-1]
            current_volume = volumes[-1]
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 0
            
            self.daily_indicators[symbol] = {
                "rsi": rsi,
                "boll_upper": upper[-1],
                "boll_middle": middle[-1],
                "boll_lower": lower[-1],
                "volume_ratio": volume_ratio
            }

    def calculate_indicators(self, symbol: str) -> Dict[str, float]:
        """计算技术指标
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 包含各项技术指标的字典
        """
        if symbol not in self.intraday_price_cache:
            return None
        
        # 使用缓存的日线指标
        daily_indicators = self.daily_indicators.get(symbol)
        if not daily_indicators:
            return None
        
        current_price = self.intraday_price_cache[symbol][-1]
        
        # 合并日线指标和当前价格
        indicators = daily_indicators.copy()
        indicators["current_price"] = current_price
        
        self.logger.debug(f"计算出的技术指标: {indicators}")
        return indicators
        
    def check_buy_signals(self, indicators: Dict[str, float]) -> bool:
        """检查买入信号
        
        Args:
            indicators: 技术指标数据
            
        Returns:
            bool: 是否有买入信号
        """
        # RSI超卖
        rsi_signal = indicators["rsi"] <= self.rsi_oversold
        
        # 价格接近布林下轨
        price = indicators["current_price"]
        boll_signal = price <= indicators["boll_lower"] * 1.01
        
        # 放量信号
        volume_signal = indicators["volume_ratio"] >= self.volume_ratio_threshold
        
        # 综合信号
        return rsi_signal and boll_signal and volume_signal
        
    def check_sell_signals(self, indicators: Dict[str, float]) -> bool:
        """检查卖出信号
        
        Args:
            indicators: 技术指标数据
            
        Returns:
            bool: 是否有卖出信号
        """
        # RSI超买
        rsi_signal = indicators["rsi"] >= self.rsi_overbought
        
        # 价格接近布林上轨
        price = indicators["current_price"]
        boll_signal = price >= indicators["boll_upper"] * 0.99
        
        # 成交量萎缩信号（当前成交量低于均线的50%）
        volume_shrink = indicators["volume_ratio"] <= 0.5
        
        # 价格动量减弱信号（可以通过比较当前价格与前一个周期的移动平均价格）
        price_momentum = price < indicators["boll_middle"]
        
        # 组合卖出信号：
        # 1. RSI超买 且 (价格接近布林上轨 或 成交量萎缩)
        # 2. 或者 价格突破布林上轨 且 成交量萎缩
        # 3. 或者 RSI超买 且 价格动量减弱
        return (rsi_signal and (boll_signal or volume_shrink)) or \
               (boll_signal and volume_shrink) or \
               (rsi_signal and price_momentum)
        
    def on_tick(self, tick_data: Dict[str, Any]):
        """处理TICK数据"""
        symbol = tick_data["symbol"]
        current_price = tick_data["price"]
        volume = tick_data["volume"]
        
        self.logger.debug(
            f"收到TICK数据:\n"
            f"  股票代码: {symbol}\n"
            f"  当前价格: {current_price}\n"
            f"  成交量: {volume}"
        )
        
        # 更新日内数据缓存
        if symbol not in self.intraday_price_cache:
            self.logger.debug(f"初始化{symbol}的日内数据缓存")
            self.intraday_price_cache[symbol] = []
            self.intraday_volume_cache[symbol] = []
            
        self.intraday_price_cache[symbol].append(current_price)
        self.intraday_volume_cache[symbol].append(volume)
        
        # 添加调试日志
        self.logger.debug(
            f"更新数据缓存 - 股票: {symbol}\n"
            f"  当前价格: {current_price}\n"
            f"  当前成交量: {volume}\n"
            f"  价格历史数据长度: {len(self.intraday_price_cache[symbol])}\n"
            f"  成交量历史数据长度: {len(self.intraday_volume_cache[symbol])}\n"
            f"  需要数据长度: {max(self.boll_period, self.rsi_period)}"
        )
        
        # 保持固定长度的历史数据
        max_length = max(self.boll_period, self.rsi_period) * 2
        if len(self.intraday_price_cache[symbol]) > max_length:
            self.logger.debug(f"裁剪{symbol}的历史数据至{max_length}条")
            self.intraday_price_cache[symbol] = self.intraday_price_cache[symbol][-max_length:]
            self.intraday_volume_cache[symbol] = self.intraday_volume_cache[symbol][-max_length:]
            
        # 计算指标
        self.logger.debug(f"开始计算{symbol}的技术指标")
        indicators = self.calculate_indicators(symbol)
        if not indicators:
            self.logger.debug(f"为{symbol}计算的指标为空，跳过处理")
            return
            
        self.logger.debug(
            f"计算出的技术指标:\n"
            f"  RSI: {indicators.get('rsi', 'N/A')}\n"
            f"  BOLL上轨: {indicators.get('boll_upper', 'N/A')}\n"
            f"  BOLL中轨: {indicators.get('boll_middle', 'N/A')}\n"
            f"  BOLL下轨: {indicators.get('boll_lower', 'N/A')}\n"
            f"  量比: {indicators.get('volume_ratio', 'N/A')}"
        )
            
        position = self.positions.get(symbol, {"volume": 0, "cost": 0.0})
        self.logger.debug(
            f"当前持仓信息:\n"
            f"  股票: {symbol}\n"
            f"  持仓量: {position['volume']}\n"
            f"  成本: {position['cost']}"
        )
        
        # 检查止盈止损
        if position["volume"] > 0:
            profit_rate = (current_price - position["cost"]) / position["cost"]
            self.logger.debug(
                f"止盈止损检查:\n"
                f"  当前收益率: {profit_rate:.2%}\n"
                f"  止盈目标: {self.profit_target:.2%}\n"
                f"  止损线: {-self.stop_loss:.2%}"
            )
            
            if profit_rate >= self.profit_target:
                self.logger.info(f"触发止盈信号，收益率: {profit_rate:.2%}")
                self.sell_stock(symbol, current_price, "止盈")
                return
            elif profit_rate <= -self.stop_loss:
                self.logger.info(f"触发止损信号，收益率: {profit_rate:.2%}")
                self.sell_stock(symbol, current_price, "止损")
                return
                
        # 检查交易信号
        if position["volume"] == 0:
            buy_signal = self.check_buy_signals(indicators)
            self.logger.debug(
                f"买入信号检查:\n"
                f"  是否满足买入条件: {buy_signal}\n"
                f"  RSI: {indicators['rsi']:.2f} (阈值: {self.rsi_oversold})\n"
                f"  价格/布林下轨: {current_price/indicators['boll_lower']:.2f}\n"
                f"  量比: {indicators['volume_ratio']:.2f} (阈值: {self.volume_ratio_threshold})"
            )
            if buy_signal:
                self.buy_stock(symbol, current_price)
        elif position["volume"] > 0:
            sell_signal = self.check_sell_signals(indicators)
            self.logger.debug(
                f"卖出信号检查:\n"
                f"  是否满足卖出条件: {sell_signal}\n"
                f"  RSI: {indicators['rsi']:.2f} (阈值: {self.rsi_overbought})\n"
                f"  价格/布林上轨: {current_price/indicators['boll_upper']:.2f}"
            )
            if sell_signal:
                self.sell_stock(symbol, current_price, "技术指标")

    def get_available_cash(self) -> float:
        """获取可用现金"""
        if hasattr(self, 'broker'):
            return self.broker.get_account_info().get('available_cash', 0.0)
        return 0.0

    def buy_stock(self, symbol: str, price: float):
        """买入股票"""
        # 计算买入数量
        available_cash = self.get_available_cash()
        position_value = available_cash * self.position_limit
        quantity = int(position_value / price / 100) * 100  # 确保为整手
        
        if quantity == 0:
            return
            
        order = self.place_order(
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_type="LIMIT"
        )
        
        if order:
            self.logger.info(
                f"创建买入订单:\n"
                f"  股票: {symbol}\n"
                f"  价格: {price:.2f}\n"
                f"  数量: {quantity}"
            )
            
    def sell_stock(self, symbol: str, price: float, reason: str):
        """卖出股票"""
        position = self.positions.get(symbol)
        if not position or position["volume"] == 0:
            return
            
        order = self.place_order(
            symbol=symbol,
            price=price,
            quantity=-position["volume"],
            order_type="LIMIT"
        )
        
        if order:
            profit = (price - position["cost"]) * position["volume"]
            profit_rate = (price - position["cost"]) / position["cost"]
            
            self.logger.info(
                f"创建卖出订单:\n"
                f"  股票: {symbol}\n"
                f"  价格: {price:.2f}\n"
                f"  数量: {position['volume']}\n"
                f"  原因: {reason}\n"
                f"  收益: {profit:.2f}\n"
                f"  收益率: {profit_rate:.2%}"
            ) 

    def initialize(self):
        """实现抽象方法initialize"""
        self.logger.debug("开始初始化 AutoTradeStrategy")
        
        # 初始化技术指标参数
        config = self.config.get("auto_trade", {})
        self.logger.debug(f"策略配置: {config}")
        
        # 初始化持仓信息
        self.positions = {}
        symbols = self.config.get("symbols", [])
        for symbol in symbols:
            # 从配置文件中读取持仓信息
            stock_config = self.broker.get_stock_config(symbol)
            if stock_config and "position" in stock_config:
                self.positions[symbol] = stock_config["position"]
                self.logger.info(
                    f"加载{symbol}持仓信息:\n"
                    f"  数量: {stock_config['position']['volume']}\n"
                    f"  成本: {stock_config['position']['cost']}"
                )
        
        self.logger.debug(f"初始化持仓信息: {self.positions}")
        
        # RSI参数
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.rsi_overbought = config.get("rsi_overbought", 70)
        
        # BOLL参数
        self.boll_period = config.get("boll_period", 20)
        self.boll_std = config.get("boll_std", 2)
        
        # 成交量参数
        self.volume_ma_period = config.get("volume_ma_period", 20)
        self.volume_ratio_threshold = config.get("volume_ratio_threshold", 2.0)
        
        # 止盈止损参数
        self.profit_target = config.get("profit_target", 0.05)
        self.stop_loss = config.get("stop_loss", 0.03)
        
        # 仓位控制
        self.position_limit = config.get("position_limit", 0.5)
        
        # 获取策略配置中的股票列表
        symbols = self.config.get("symbols", [])
        self.logger.debug(f"配置的股票列表: {symbols}")
        
        if not symbols:
            self.logger.warning("未配置交易股票列表")
        else:
            for symbol in symbols:
                self.subscriptions[symbol] = True
            
            self.logger.debug(f"开始加载历史数据，订阅列表: {self.subscriptions}")
            # 加载历史日线数据
            self._load_daily_history_data()
            # 计算初始技术指标
            self._calculate_daily_indicators()
        
        self.logger.info("AutoTradeStrategy initialized") 
