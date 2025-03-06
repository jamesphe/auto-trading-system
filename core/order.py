from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
import uuid

class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = 1      # 待处理
    SUBMITTED = 2    # 已提交
    PARTIAL_FILLED = 3  # 部分成交
    FILLED = 4       # 全部成交
    CANCELLED = 5    # 已取消
    REJECTED = 6     # 已拒绝

class OrderType(Enum):
    """订单类型枚举"""
    MARKET = 1  # 市价单
    LIMIT = 2   # 限价单

@dataclass
class Order:
    """订单数据类"""
    symbol: str                      # 标的代码
    price: float                     # 委托价格
    quantity: int                    # 委托数量
    order_type: str = "LIMIT"        # 订单类型
    strategy_id: str = ""            # 策略ID
    
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    broker_order_id: str = ""        # 券商订单ID
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0         # 成交数量
    avg_fill_price: float = 0.0      # 成交均价
    commission: float = 0.0          # 佣金
    create_time: datetime = field(default_factory=datetime.now)
    update_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = None  # 元数据
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.metadata:
            self.metadata = {}
    
    def update(self, status: OrderStatus = None, 
              filled_quantity: int = None,
              avg_fill_price: float = None,
              broker_order_id: str = None):
        """更新订单状态
        
        Args:
            status: 新状态
            filled_quantity: 已成交数量
            avg_fill_price: 平均成交价格
            broker_order_id: 券商订单ID
        """
        if status:
            self.status = status
        if filled_quantity is not None:
            self.filled_quantity = filled_quantity
        if avg_fill_price is not None:
            self.avg_fill_price = avg_fill_price
        if broker_order_id:
            self.broker_order_id = broker_order_id
        
        self.update_time = datetime.now()
    
    def is_active(self) -> bool:
        """订单是否活跃"""
        return self.status in [OrderStatus.PENDING, 
                              OrderStatus.SUBMITTED, 
                              OrderStatus.PARTIAL_FILLED]
    
    def __str__(self) -> str:
        return (f"Order(id={self.order_id}, symbol={self.symbol}, "
                f"price={self.price}, qty={self.quantity}, "
                f"filled={self.filled_quantity}, status={self.status.name})")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "order_id": self.order_id,
            "broker_order_id": self.broker_order_id,
            "symbol": self.symbol,
            "price": self.price,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "strategy_id": self.strategy_id,
            "status": self.status.name,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "create_time": self.create_time.isoformat(),
            "update_time": self.update_time.isoformat()
        }

class OrderManager:
    """订单管理器"""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.logger = logging.getLogger(__name__)
        
    def add_order(self, order: Order) -> bool:
        """添加订单
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否成功
        """
        if order.order_id in self.orders:
            self.logger.warning(f"订单已存在: {order.order_id}")
            return False
        self.orders[order.order_id] = order
        return True
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            Optional[Order]: 订单对象
        """
        return self.orders.get(order_id)
    
    def update_order(self, order_id: str, **kwargs) -> bool:
        """更新订单
        
        Args:
            order_id: 订单ID
            **kwargs: 更新参数
            
        Returns:
            bool: 是否成功
        """
        order = self.get_order(order_id)
        if order is None:
            return False
        order.update(**kwargs)
        return True
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """获取活跃订单
        
        Args:
            symbol: 标的代码过滤
            
        Returns:
            list[Order]: 活跃订单列表
        """
        active_orders = [o for o in self.orders.values() if o.is_active()]
        if symbol:
            active_orders = [o for o in active_orders if o.symbol == symbol]
        return active_orders
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 是否成功
        """
        order = self.get_order(order_id)
        if order and order.is_active():
            order.update(status=OrderStatus.CANCELLED)
            return True
        return False 

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """获取指定标的的订单"""
        return [
            order for order in self.orders.values()
            if order.symbol == symbol
        ]

    def get_position(self, symbol: str) -> int:
        """获取持仓数量"""
        position = 0
        for order in self.get_orders_by_symbol(symbol):
            if order.status == OrderStatus.FILLED:
                position += order.quantity
        return position 