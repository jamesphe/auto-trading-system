from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional
import logging
from datetime import datetime
import pandas as pd

from core.order import Order, OrderStatus

class Strategy(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = {}
        self.positions = {}
        
    def initialize(self, config: Dict[str, Any]):
        """初始化策略参数"""
        self.config = config
        self.logger.info(f"初始化策略参数: {config}")
        
    @abstractmethod
    def execute(self, market_data: Dict[str, Any]) -> bool:
        """执行策略"""
        pass

class BaseStrategy(ABC):
    """策略基类，所有交易策略都应继承此类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化策略
        
        Args:
            config: 策略配置
        """
        self.config = config or {}
        self.positions = {}  # 持仓信息
        self.strategy_id = None  # 策略ID
        
        # 让子类先完成自己的初始化
        self._init()
        
        # 然后再调用initialize
        self.initialize()
    
    def _init(self):
        """子类初始化，在initialize之前调用"""
        pass
    
    @abstractmethod
    def initialize(self):
        """初始化策略，注册事件处理器"""
        pass
    
    def register_event(self, event_type: str, handler: Callable):
        """注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        self.event_handlers[event_type] = handler
        self.logger.debug(f"注册事件处理器: {event_type}")
    
    def on_event(self, event_type: str, event_data: Any):
        """事件触发处理
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
        """
        if event_type in self.event_handlers:
            self.logger.debug(f"处理事件: {event_type}")
            self.event_handlers[event_type](event_data)
    
    def set_gateway(self, gateway):
        """设置交易网关"""
        self.gateway = gateway
        
    def place_order(self, symbol: str, price: float, quantity: int, 
                   order_type: str = "LIMIT") -> Optional[Order]:
        """下单
        
        Args:
            symbol: 股票代码
            price: 价格
            quantity: 数量（正数为买入，负数为卖出）
            order_type: 订单类型，默认为限价单
            
        Returns:
            Order: 订单对象
        """
        if self.gateway is None:
            self.logger.error("交易网关未初始化")
            return None
            
        try:
            # 确定交易方向
            direction = "BUY" if quantity > 0 else "SELL"
            abs_quantity = abs(quantity)  # 取绝对值作为实际数量
            
            # 创建订单对象
            order = Order(
                symbol=symbol,
                price=price,
                quantity=abs_quantity,
                direction=direction,  # 添加明确的交易方向
                order_type=order_type,
                strategy_id=self.__class__.__name__
            )
            
            # 通过网关下单
            order_id = self.gateway.place_order(order)
            if order_id:
                order.order_id = order_id
                return order
            return None
        except Exception as e:
            self.logger.error(f"下单失败: {str(e)}")
            return None
    
    def on_order_update(self, order: Order):
        """订单状态更新回调
        
        Args:
            order: 更新后的订单对象
        """
        self.logger.info(f"订单更新: {order}")
    
    def get_position(self, symbol: str) -> int:
        """获取当前持仓
        
        Args:
            symbol: 标的代码
            
        Returns:
            int: 持仓数量
        """
        # 实际实现中需要从账户管理模块获取
        return self.positions.get(symbol, {"quantity": 0})["quantity"]
    
    def get_historical_data(self, symbol: str, 
                           start: datetime, 
                           end: datetime, 
                           timeframe: str = "1d") -> pd.DataFrame:
        """获取历史数据
        
        Args:
            symbol: 标的代码
            start: 开始时间
            end: 结束时间
            timeframe: 时间周期
            
        Returns:
            pd.DataFrame: 历史数据
        """
        # 实际实现中需要从数据模块获取
        return pd.DataFrame()
    
    def buy_stock(self, symbol: str, price: float):
        """买入股票"""
        position_size = self.config.get("position_size", 100)
        order = self.place_order(symbol, price, position_size)
        if order:
            self.logger.info(f"创建订单: {order}")
            self.logger.info(f"买入 {symbol}: 价格={price}, 数量={position_size}")
            # 添加到持仓
            self.positions[symbol] = {
                "entry_price": price,
                "quantity": position_size,
                "entry_time": datetime.now()
            }
        else:
            self.logger.error(f"创建订单失败: {symbol}, 价格={price}") 