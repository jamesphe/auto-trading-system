from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

from core.order import Order, OrderStatus

class RiskRule:
    """风控规则基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.name = self.__class__.__name__
    
    def check(self, order: Order, context: Dict[str, Any]) -> bool:
        """检查订单是否满足风控规则
        
        Args:
            order: 订单对象
            context: 上下文信息
            
        Returns:
            bool: 是否通过检查
        """
        raise NotImplementedError("风控规则必须实现check方法")

class MaxOrderValueRule(RiskRule):
    """最大订单金额规则"""
    
    def check(self, order: Order, context: Dict[str, Any]) -> bool:
        max_value = self.config.get("max_order_value", 1000000)
        order_value = abs(order.price * order.quantity)
        return order_value <= max_value

class MaxPositionRule(RiskRule):
    """最大持仓规则"""
    
    def check(self, order: Order, context: Dict[str, Any]) -> bool:
        max_position = self.config.get("max_position", 1000)
        current_position = context.get("positions", {}).get(order.symbol, 0)
        new_position = current_position + order.quantity
        return abs(new_position) <= max_position

class OrderFrequencyRule(RiskRule):
    """订单频率规则"""
    
    def check(self, order: Order, context: Dict[str, Any]) -> bool:
        max_orders = self.config.get("max_orders_per_minute", 5)
        recent_orders = context.get("recent_orders", [])
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        recent_count = sum(1 for o in recent_orders 
                         if o.create_time >= one_minute_ago 
                         and o.strategy_id == order.strategy_id)
        return recent_count < max_orders

class RiskManager:
    """风控管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.rules = []
        self.recent_orders = []  # 最近的订单
        self.positions = {}  # symbol -> position
        
        # 初始化风控规则
        self._init_rules()
    
    def _init_rules(self):
        """初始化风控规则"""
        # 添加默认规则
        self.add_rule(MaxOrderValueRule(self.config.get("max_order_value_rule")))
        self.add_rule(MaxPositionRule(self.config.get("max_position_rule")))
        self.add_rule(OrderFrequencyRule(self.config.get("order_frequency_rule")))
        
        # 添加自定义规则
        custom_rules = self.config.get("custom_rules", [])
        for rule_config in custom_rules:
            rule_type = rule_config.pop("type")
            if rule_type == "MaxOrderValue":
                self.add_rule(MaxOrderValueRule(rule_config))
            elif rule_type == "MaxPosition":
                self.add_rule(MaxPositionRule(rule_config))
            elif rule_type == "OrderFrequency":
                self.add_rule(OrderFrequencyRule(rule_config))
    
    def add_rule(self, rule: RiskRule):
        """添加风控规则
        
        Args:
            rule: 风控规则
        """
        self.rules.append(rule)
        self.logger.info(f"添加风控规则: {rule.name}")
    
    def check_order(self, order: Order) -> bool:
        """检查订单是否满足所有风控规则
        
        Args:
            order: 订单对象
            
        Returns:
            bool: 是否通过所有规则检查
        """
        context = {
            "positions": self.positions,
            "recent_orders": self.recent_orders
        }
        
        for rule in self.rules:
            if not rule.check(order, context):
                self.logger.warning(f"订单未通过风控规则 {rule.name}: {order}")
                return False
        
        # 通过所有规则，记录订单
        self.recent_orders.append(order)
        # 保留最近1000个订单
        if len(self.recent_orders) > 1000:
            self.recent_orders = self.recent_orders[-1000:]
        
        return True
    
    def update_position(self, symbol: str, quantity: int):
        """更新持仓信息
        
        Args:
            symbol: 标的代码
            quantity: 持仓变化量
        """
        current = self.positions.get(symbol, 0)
        self.positions[symbol] = current + quantity 