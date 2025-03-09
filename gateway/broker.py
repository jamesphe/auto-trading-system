import logging
from typing import Dict, Any, Optional, List
import uuid
import time
import random
from datetime import datetime

from core.order import Order, OrderStatus, OrderType

class TradeGateway:
    """交易网关基类"""
    
    def __init__(self, config: Dict[str, Any] = None, engine=None, market_client=None):
        self.config = config or {}
        self.logger = logging.getLogger("gateway.TradeGateway")
        self.logger.info("初始化交易网关")
        self.connected = False
        self.market_client = market_client  # 直接存储market_client引用
        
        # 抑制 pandas SettingWithCopyWarning
        import pandas as pd
        pd.options.mode.chained_assignment = None
    
    def connect(self) -> bool:
        """连接到交易系统
        
        Returns:
            bool: 是否成功连接
        """
        raise NotImplementedError("子类必须实现connect方法")
    
    def disconnect(self) -> bool:
        """断开与交易系统的连接
        
        Returns:
            bool: 是否成功断开
        """
        raise NotImplementedError("子类必须实现disconnect方法")
    
    def place_order(self, order: Order) -> str:
        """下单
        
        Args:
            order: Order对象，包含下单信息
            
        Returns:
            str: 订单ID
        """
        try:
            # 模拟下单
            order_id = str(uuid.uuid4())
            self.logger.info(
                f"下单:\n"
                f"  订单ID: {order_id}\n"
                f"  股票: {order.symbol}\n"
                f"  价格: {order.price}\n"
                f"  数量: {order.quantity}\n"
                f"  类型: {order.order_type}"
            )
            return order_id
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            return None
    
    def cancel_order(self, broker_order_id: str) -> bool:
        """取消订单
        
        Args:
            broker_order_id: 券商订单ID
            
        Returns:
            bool: 是否成功
        """
        raise NotImplementedError("子类必须实现cancel_order方法")
    
    def query_order(self, broker_order_id: str) -> Optional[Dict[str, Any]]:
        """查询订单
        
        Args:
            broker_order_id: 券商订单ID
            
        Returns:
            Optional[Dict[str, Any]]: 订单信息
        """
        raise NotImplementedError("子类必须实现query_order方法")
    
    def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息
        
        Returns:
            Dict[str, Any]: 账户信息
        """
        raise NotImplementedError("子类必须实现get_account_info方法")
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """获取持仓信息
        
        Returns:
            List[Dict[str, Any]]: 持仓信息
        """
        raise NotImplementedError("子类必须实现get_positions方法")
    
    def set_market_client(self, market_client):
        """设置市场数据客户端"""
        self.market_client = market_client
        self.logger.info("设置市场数据客户端")

    def get_stock_config(self, symbol: str) -> Dict[str, Any]:
        """获取股票配置信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict[str, Any]: 股票配置信息
        """
        try:
            # 从配置文件中读取股票配置
            import os
            import json
            
            config_path = os.path.join("config", "stocks", f"{symbol}.json")
            self.logger.debug(f"读取股票配置文件: {config_path}")
            
            if not os.path.exists(config_path):
                self.logger.warning(f"股票配置文件不存在: {config_path}")
                return None
                
            with open(config_path, "r", encoding="utf-8") as f:
                stock_config = json.load(f)
                
            self.logger.debug(f"获取到股票配置: {stock_config}")
            return stock_config
            
        except Exception as e:
            self.logger.error(f"获取股票配置失败: {e}")
            return None

class SimulatedTradeGateway(TradeGateway):
    """模拟交易网关"""
    
    def __init__(self, config: Dict[str, Any] = None, engine=None, market_client=None):
        super().__init__(config, engine, market_client)
        self.orders = {}  # broker_order_id -> order_info
        self.positions = {}  # symbol -> quantity
        self.position_costs = {}  # symbol -> average_cost
        self.prices = {}  # symbol -> current_price
        self.account_balance = self.config.get("initial_balance", 1000000.0)
        self.slippage = self.config.get("slippage", 0.001)  # 滑点
        self.commission_rate = self.config.get("commission_rate", 0.0003)  # 佣金率
        
        # 模拟延迟
        self.min_latency = self.config.get("min_latency", 0.05)  # 最小延迟(秒)
        self.max_latency = self.config.get("max_latency", 0.2)  # 最大延迟(秒)
        
        # 模拟成交概率
        self.fill_probability = self.config.get("fill_probability", 0.95)
        
        self.connected = True
        self.logger.info("初始化模拟交易网关")
    
    def connect(self) -> bool:
        """连接到模拟交易系统
        
        Returns:
            bool: 是否成功连接
        """
        self.connected = True
        self.logger.info("连接到模拟交易系统")
        return True
    
    def disconnect(self) -> bool:
        """断开与模拟交易系统的连接
        
        Returns:
            bool: 是否成功断开
        """
        self.connected = False
        self.logger.info("断开与模拟交易系统的连接")
        return True
    
    def _simulate_latency(self):
        """模拟网络延迟"""
        latency = random.uniform(self.min_latency, self.max_latency)
        time.sleep(latency)
    
    def place_order(self, order: Order) -> Optional[str]:
        """下单处理"""
        try:
            # 生成内部订单ID
            broker_order_id = str(uuid.uuid4())
            
            # 模拟延迟
            time.sleep(random.uniform(self.min_latency, self.max_latency))
            
            # 调整价格(考虑滑点)
            adjusted_price = self._calculate_price_with_slippage(order)
            
            # 检查资金是否足够
            required_amount = abs(adjusted_price * order.quantity)
            commission = required_amount * self.commission_rate
            
            if required_amount + commission > self.account_balance:
                self.logger.warning(f"资金不足: 需要{required_amount + commission}, 当前{self.account_balance}")
                return None
            
            # 更新账户余额
            self.account_balance -= (required_amount + commission)
            
            # 保存订单
            self.orders[broker_order_id] = {
                "order": order,
                "adjusted_price": adjusted_price,
                "commission": commission,
                "status": "FILLED"  # 模拟情况下直接成交
            }
            
            # 更新持仓和成本
            if order.symbol not in self.positions:
                self.positions[order.symbol] = 0
                self.position_costs[order.symbol] = 0
            
            if order.quantity > 0:  # 买入
                new_cost = (
                    (self.position_costs.get(order.symbol, 0) * self.positions.get(order.symbol, 0) +
                     adjusted_price * order.quantity) /
                    (self.positions.get(order.symbol, 0) + order.quantity)
                )
                self.position_costs[order.symbol] = new_cost
            
            self.positions[order.symbol] += order.quantity
            self.prices[order.symbol] = adjusted_price  # 更新当前价格
            
            return broker_order_id
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            return None
    
    def _calculate_price_with_slippage(self, order: Order) -> float:
        """计算考虑滑点的价格"""
        if order.order_type == "MARKET":
            # 市价单加入滑点
            adjusted_price = order.price * (1 + self.slippage * (1 if order.quantity > 0 else -1))
        else:
            # 限价单不调整价格
            adjusted_price = order.price
        return adjusted_price
    
    def cancel_order(self, broker_order_id: str) -> bool:
        """取消订单
        
        Args:
            broker_order_id: 券商订单ID
            
        Returns:
            bool: 是否成功
        """
        if not self.connected:
            raise ConnectionError("未连接到交易系统")
        
        # 模拟网络延迟
        self._simulate_latency()
        
        order_info = self.orders.get(broker_order_id)
        if not order_info:
            self.logger.warning(f"取消订单失败，订单不存在: {broker_order_id}")
            return False
        
        if order_info["status"] not in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]:
            self.logger.warning(f"取消订单失败，订单状态不允许取消: {broker_order_id}, {order_info['status']}")
            return False
        
        # 更新订单状态
        order_info["status"] = OrderStatus.CANCELLED
        order_info["update_time"] = datetime.now()
        
        self.logger.info(f"取消订单成功: {broker_order_id}")
        return True
    
    def query_order(self, broker_order_id: str) -> Optional[Dict[str, Any]]:
        """查询订单
        
        Args:
            broker_order_id: 券商订单ID
            
        Returns:
            Optional[Dict[str, Any]]: 订单信息
        """
        if not self.connected:
            raise ConnectionError("未连接到交易系统")
        
        # 模拟网络延迟
        self._simulate_latency()
        
        order_info = self.orders.get(broker_order_id)
        if not order_info:
            return None
        
        return {
            "broker_order_id": order_info["broker_order_id"],
            "symbol": order_info["symbol"],
            "price": order_info["price"],
            "quantity": order_info["quantity"],
            "order_type": order_info["order_type"],
            "status": order_info["status"],
            "filled_quantity": order_info["filled_quantity"],
            "avg_price": order_info["avg_price"],
            "commission": order_info["commission"],
            "create_time": order_info["create_time"],
            "update_time": order_info["update_time"]
        }
    
    def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息
        
        Returns:
            Dict[str, Any]: 账户信息
        """
        if not self.connected:
            raise ConnectionError("未连接到交易系统")
        
        # 模拟网络延迟
        self._simulate_latency()
        
        return {
            "balance": self.account_balance,
            "frozen": sum(
                (o["quantity"] - o["filled_quantity"]) * o["price"]
                for o in self.orders.values()
                if o["status"] in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]
            ),
            "available": self.account_balance - sum(
                (o["quantity"] - o["filled_quantity"]) * o["price"]
                for o in self.orders.values()
                if o["status"] in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]
            )
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """获取持仓信息
        
        Returns:
            List[Dict[str, Any]]: 持仓信息
        """
        if not self.connected:
            raise ConnectionError("未连接到交易系统")
        
        # 模拟网络延迟
        self._simulate_latency()
        
        return [
            {
                "symbol": symbol,
                "quantity": quantity,
                "cost_price": 0.0,  # 实际应该计算平均成本价
                "market_price": 0.0,  # 实际应该获取当前市场价
                "profit_loss": 0.0  # 实际应该计算盈亏
            }
            for symbol, quantity in self.positions.items()
            if quantity != 0
        ]

    def get_account(self) -> Dict[str, float]:
        """获取账户信息
        
        Returns:
            Dict[str, float]: 账户信息，包含余额和可用资金
        """
        # 计算持仓市值
        positions_value = sum(
            pos * self.prices.get(sym, 0) 
            for sym, pos in self.positions.items()
        )
        
        return {
            "balance": self.account_balance + positions_value,  # 总资产
            "available": self.account_balance,  # 可用资金
            "positions_value": positions_value,  # 持仓市值
            "initial_balance": self.config.get("initial_balance", 1000000.0)  # 初始资金
        }

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取持仓信息
        
        Returns:
            Dict[str, Dict[str, Any]]: 持仓信息，按标的代码索引
        """
        positions = {}
        for symbol, quantity in self.positions.items():
            if quantity > 0:  # 只返回有持仓的标的
                positions[symbol] = {
                    "quantity": quantity,
                    "cost": self.position_costs.get(symbol, 0),  # 持仓成本
                    "current_price": self.prices.get(symbol, 0),  # 当前价格
                }
        return positions 