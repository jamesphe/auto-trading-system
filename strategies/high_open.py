from typing import Dict, Any
import logging
from datetime import datetime, time

from core.strategy import BaseStrategy
from core.order import Order, OrderStatus
import numpy as np

class HighOpenStrategy(BaseStrategy):
    """高开策略
    
    当股票开盘价高于前一日收盘价的一定百分比时买入，
    当股票价格上涨到一定百分比时卖出，或者当价格下跌到止损点时卖出。
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化策略
        
        Args:
            config: 策略配置
        """
        # 首先设置日志
        self.logger = logging.getLogger("strategy.HighOpen")
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # 确保调用父类初始化
        super().__init__(config)
        
        # 设置配置
        self.config = config or {}
        self.logger.debug(f"策略初始化配置: {self.config}")
        
        # 初始化持仓信息
        self.positions = {}
        stocks_config = self.config.get("stocks", {})
        for symbol, stock_config in stocks_config.items():
            position_info = stock_config.get("position", {})
            self.positions[symbol] = {
                "volume": position_info.get("volume", 0),
                "cost": position_info.get("cost", 0.0),
                "entry_time": datetime.now()
            }
            self.logger.info(
                f"加载股票 {symbol} 持仓信息:\n"
                f"  持仓量: {self.positions[symbol]['volume']}\n"
                f"  成本价: {self.positions[symbol]['cost']:.2f}"
            )
        
        # 设置其他参数
        self.symbols = config.get("symbols", [])
        self.threshold = config.get("threshold", 0.0)
        self.profit_target = config.get("profit_target", 0.05)
        self.stop_loss = config.get("stop_loss", 0.03)
        
        # 其他初始化...
        self.initialize()  # 调用 initialize 方法完成其他初始化
        
    def initialize(self):
        """初始化策略"""
        self.logger.debug(f"开始初始化策略，配置: {self.config}")
        stocks_config = self.config.get("stocks", {})
        self.logger.debug(f"股票配置: {stocks_config}")  # 这里显示为空
        
        for symbol, stock_config in stocks_config.items():
            # 读取持仓信息
            position_info = stock_config.get("position", {})
            self.positions[symbol] = {
                "volume": position_info.get("volume", 0),
                "cost": position_info.get("cost", 0.0),
                "entry_time": datetime.now()
            }
            
            self.logger.info(
                f"加载股票 {symbol} 持仓信息:\n"
                f"  持仓量: {self.positions[symbol]['volume']}\n"
                f"  成本价: {self.positions[symbol]['cost']:.2f}"
            )
            
            # 设置策略参数
            strategy_config = stock_config.get("high_open", {})
            self.price_threshold = strategy_config.get("price_threshold", 0.0)
            self.high_open_ratio = strategy_config.get("high_open_ratio", 0.02)
            self.profit_target = strategy_config.get("profit_target", 0.05)
            self.stop_loss = strategy_config.get("stop_loss", 0.03)
            self.volume_window = strategy_config.get("volume_check_window", 30)
            
            self.logger.info(
                f"初始化高开策略 {symbol}，参数: "
                f"price_threshold={self.price_threshold}, "
                f"high_open_ratio={self.high_open_ratio:.2%}, "
                f"profit_target={self.profit_target:.2%}, "
                f"stop_loss={self.stop_loss:.2%}, "
                f"volume_window={self.volume_window}"
            )
        
        # 注册事件处理器
        self.register_event("market.kline", self.on_kline)
        self.register_event("market.tick", self.on_tick)
        self.register_event("开盘事件", self.on_market_open)
        
        # 添加调试日志
        self.logger.debug("策略配置详情:")
        for key, value in self.config.items():
            self.logger.debug(f"  {key}: {value}")
    
    def on_kline(self, kline_data: Dict[str, Any]):
        """处理K线数据"""
        self.logger.debug(f"收到K线数据: {kline_data}")
        symbol = kline_data["symbol"]
        
        # 记录前收盘价
        if self._is_previous_day_close(kline_data["timestamp"]):
            self.prev_close[symbol] = kline_data["close"]
            self.logger.info(f"记录前收盘价: {symbol}={kline_data['close']:.2f}")
            self.logger.debug(f"当前所有前收盘价记录: {self.prev_close}")
        
        # 检查是否是开盘时的高开
        if self._is_high_open(kline_data):
            # 执行买入
            self.buy_stock(symbol, kline_data["open"])
    
    def on_tick(self, tick_data: Dict[str, Any]):
        """处理tick数据"""
        symbol = tick_data["symbol"]
        self.logger.debug(f"开始处理TICK数据: {tick_data}")
        
        self.logger.debug(f"当前持仓: {self.positions}")
        # 检查是否需要止盈/止损
        position = self.positions.get(symbol, {"volume": 0, "cost": 0.0})
        
        # 如果没有持仓或成本为0，跳过止盈止损检查
        if position["volume"] == 0 or position["cost"] == 0:
            self.logger.debug(f"股票 {symbol} 不在持仓中，跳过止盈止损检查")
            return
        
        current_price = tick_data["price"]
        
        self.logger.debug(
            f"检查止盈止损:\n"
            f"  当前价格: {current_price}\n"
            f"  持仓信息: {position}\n"
            f"  止盈目标: {self.profit_target}\n"
            f"  止损线: {self.stop_loss}"
        )
        
        # 计算收益率
        profit_rate = (current_price - position["cost"]) / position["cost"]
        
        # 止盈/止损检查
        if profit_rate >= self.profit_target:
            self.logger.debug(f"触发止盈: 收益率={profit_rate:.2%} >= {self.profit_target:.2%}")
            self.sell_stock(symbol, current_price, "止盈")
        elif profit_rate <= -self.stop_loss:
            self.logger.debug(f"触发止损: 收益率={profit_rate:.2%} <= -{self.stop_loss:.2%}")
            self.sell_stock(symbol, current_price, "止损")
        else:
            self.logger.debug("未触发止盈止损条件")
    
    def on_market_open(self, context):
        """开盘时检查是否满足高开条件"""
        open_price = context.current_price
        
        # 使用价格阈值判断
        if self.price_threshold > 0 and open_price >= self.price_threshold:
            self.check_volume(context)
            
    def check_volume(self, context):
        """检查成交量并执行交易"""
        # 检查5分钟成交量
        five_min_volume = context.get_volume(minutes=5)
        avg_volume = context.get_average_volume(days=self.volume_window)
        
        if five_min_volume > avg_volume:
            # 卖出价格设置为当前价格加上固定金额
            sell_price = context.current_price + 1.0
            sell_ratio = 0.5  # 卖出50%
            self.place_limit_order(
                price=sell_price,
                volume=int(context.position * sell_ratio),  # 确保为整数
                direction='SELL'
            )
        else:
            # 从配置获取卖出比例
            sell_ratio = 0.8  # 卖出80%
            self.place_market_order(
                volume=context.position * sell_ratio,
                direction='SELL'
            )

    def on_time(self, context):
        """定时检查"""
        current_time = datetime.strptime(context.current_time, "%H:%M:%S").time()
        check_time = time(10, 0)  # 10:00:00
        
        if current_time <= check_time:
            hold_price = context.current_price + 0.3
            if context.current_price >= hold_price:
                if not self.position_reduced:
                    keep_ratio = 0.2
                    self.place_market_order(
                        volume=int(context.position * (1 - keep_ratio)),
                        direction='SELL'
                    )
                    self.position_reduced = True
            else:
                # 清仓
                self.place_market_order(
                    volume=context.position,
                    direction='SELL'
                )
    
    def buy_stock(self, symbol: str, price: float):
        """买入股票"""
        position_size = self.config.get("position_size", 100)
        order = self.place_order(symbol, price, position_size)
        if order:
            self.logger.info(f"创建订单: {order}")
            self.logger.info(f"买入 {symbol}: 价格={price}, 数量={position_size}")
            
            # 更新持仓信息
            current_position = self.positions.get(symbol, {"volume": 0, "cost": 0.0})
            new_volume = current_position["volume"] + position_size
            new_cost = ((current_position["volume"] * current_position["cost"]) + 
                       (position_size * price)) / new_volume
            
            self.positions[symbol] = {
                "volume": new_volume,
                "cost": new_cost,
                "entry_time": datetime.now()
            }
            
            self.logger.info(
                f"更新持仓信息:\n"
                f"  持仓量: {new_volume}\n"
                f"  成本价: {new_cost:.2f}"
            )
    
    def sell_stock(self, symbol: str, price: float, reason: str):
        """卖出股票"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        quantity = position["volume"]
        cost = position["cost"]
        
        # 创建卖出订单
        order = self.place_order(
            symbol=symbol,
            price=price,
            quantity=-quantity,
            order_type="LIMIT"
        )
        
        if order is None:
            self.logger.error(f"创建卖出订单失败: {symbol}")
            return
        
        # 计算收益
        profit = (price - cost) * quantity
        profit_ratio = (price - cost) / cost
        
        self.logger.info(
            f"卖出 {symbol}:\n"
            f"  价格={price:.2f}\n"
            f"  数量={quantity}\n"
            f"  原因={reason}\n"
            f"  收益={profit:.2f}\n"
            f"  收益率={profit_ratio:.2%}"
        )
        
        # 清空持仓记录
        self.positions[symbol] = {
            "volume": 0,
            "cost": 0.0
        }
    
    def on_order_update(self, order: Order):
        """订单状态更新回调
        
        Args:
            order: 更新后的订单对象
        """
        super().on_order_update(order)
        
        # 处理订单成交
        if order.status == OrderStatus.FILLED:
            symbol = order.symbol
            
            # 如果是买入订单成交，更新持仓的平均成本
            if order.quantity > 0 and symbol in self.positions:
                position = self.positions[symbol]
                position["avg_price"] = order.avg_fill_price
                self.logger.info(f"买入订单成交: {symbol}, 均价={order.avg_fill_price}")
            
            # 如果是卖出订单成交，记录交易结果
            elif order.quantity < 0:
                self.logger.info(f"卖出订单成交: {symbol}, 均价={order.avg_fill_price}")
    
    def _is_previous_day_close(self, timestamp) -> bool:
        """判断是否是前一交易日收盘K线
        
        Args:
            timestamp: K线时间戳
            
        Returns:
            bool: 是否是前一交易日收盘K线
        """
        # 实际应用中需要根据交易日历判断
        # 这里简化处理，假设任何15:00的K线都是收盘K线
        dt = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp)
        return dt.hour == 15 and dt.minute == 0
    
    def _is_today_open(self, timestamp) -> bool:
        """判断是否是当日开盘K线
        
        Args:
            timestamp: K线时间戳
            
        Returns:
            bool: 是否是当日开盘K线
        """
        # 实际应用中需要根据交易日历判断
        # 这里简化处理，假设任何9:30的K线都是开盘K线
        dt = timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(timestamp)
        return dt.hour == 9 and dt.minute == 30
    
    def _is_high_open(self, kline_data: Dict[str, Any]) -> bool:
        """判断是否是高开
        
        Args:
            kline_data: K线数据
            
        Returns:
            bool: 是否高开
        """
        self.logger.debug(f"开始判断是否高开: {kline_data}")
        symbol = kline_data["symbol"]
        timestamp = kline_data["timestamp"]
        
        # 检查是否是开盘时间
        is_open_time = self._is_today_open(timestamp)
        self.logger.debug(f"是否开盘时间: {is_open_time}")
        if not is_open_time:
            return False
            
        # 获取开盘价
        open_price = kline_data["open"]
        
        # 获取前收盘价
        prev_close = self.prev_close.get(symbol)
        self.logger.debug(f"前收盘价: {prev_close}")
        if not prev_close:
            self.logger.warning(f"未找到前收盘价: {symbol}")
            return False
        
        # 计算开盘涨幅，使用high_open_ratio作为百分比阈值
        open_change = (open_price - prev_close) / prev_close
        self.logger.debug(
            f"开盘涨幅计算: open={open_price:.2f}, "
            f"prev_close={prev_close:.2f}, "
            f"change={open_change:.2%}, "
            f"threshold={self.high_open_ratio:.2%}"
        )
        
        # 使用high_open_ratio判断是否高开
        is_high = open_change >= self.high_open_ratio
        
        if is_high:
            self.logger.info(
                f"检测到高开: {symbol}, "
                f"开盘价={open_price:.2f}, "
                f"前收={prev_close:.2f}, "
                f"涨幅={open_change:.2%}"
            )
            
        return is_high

    def on_order_status(self, order_data):
        """处理订单状态更新"""
        order_id = order_data["order_id"]
        status = order_data["status"]
        symbol = order_data["symbol"]
        
        self.logger.info(f"订单状态更新: {order_id}, {status}")
        
        # 处理成交
        if status == OrderStatus.FILLED:
            if symbol in self.positions:
                # 更新持仓均价
                self.positions[symbol]["avg_price"] = order_data["avg_fill_price"]
                self.logger.info(f"更新持仓均价: {symbol}={order_data['avg_fill_price']}") 

    def execute(self, market_data):
        try:
            self.logger.debug(f"开始执行策略，市场数据: {market_data}")
            symbol = market_data["symbol"]
            
            # 添加策略状态日志
            self.logger.debug(f"当前策略状态:")
            self.logger.debug(f"  持仓: {self.positions}")
            self.logger.debug(f"  前收盘价记录: {self.prev_close}")
            
            if self._is_high_open(market_data):
                self.logger.info(f"触发高开策略买入信号: {symbol}")
                self.buy_stock(symbol, market_data["open"])
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"策略执行错误: {str(e)}", exc_info=True)
            return None 

    def on_market_data(self, data_type: str, data: dict):
        """处理市场数据的入口方法"""
        symbol = data["symbol"]
        if symbol not in self.symbols:
            return
            
        self.logger.info(f"收到市场数据: {symbol} {data_type}")
        self.logger.debug(f"数据详情: {data}")
        
        try:
            if data_type == "tick":
                self.on_tick(data)
            elif data_type == "kline":
                self.on_kline(data)
            else:
                self.logger.warning(f"未知的数据类型: {data_type}")
        except Exception as e:
            self.logger.error(f"处理市场数据错误: {str(e)}", exc_info=True) 