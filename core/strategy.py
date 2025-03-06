from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional
import logging
from datetime import datetime
import pandas as pd

from core.order import Order
from models.order import OrderModel
from utils.db import get_session

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
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 加载全局配置
        try:
            with open("config.json", "r") as f:
                import json
                self.global_config = json.load(f)
        except Exception as e:
            self.logger.error(f"加载全局配置失败: {str(e)}")
            self.global_config = {}
        
        # 初始化微信推送
        try:
            from utils.wechat_pusher import WeChatPusher
            wechat_config = self.global_config.get("wechat_config")
            if wechat_config and wechat_config.get("webhook_url"):
                self.wechat_pusher = WeChatPusher(
                    webhook_url=wechat_config["webhook_url"]
                )
                self.logger.info("微信群机器人推送服务初始化成功")
            else:
                self.logger.warning("未找到微信推送配置")
        except Exception as e:
            self.logger.error(f"微信推送服务初始化失败: {str(e)}")
        
        # 让子类完成初始化
        self._init()
        
        # 初始化股票特定配置
        if self.config:
            self.symbol = self.config.get("symbol")
            self.name = self.config.get("name")
            
            # 初始化持仓信息
            position_info = self.config.get("position", {})
            self.positions[self.symbol] = {
                "quantity": position_info.get("volume", 0),
                "cost": position_info.get("cost", 0)
            }
            
            # 获取策略特定参数
            self.strategy_params = self.config.get("strategies", {}).get(
                self.__class__.__name__.lower(), {}
            )
        
        # 最后调用initialize
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
        """下单"""
        try:
            # 创建订单对象
            order = Order(
                symbol=symbol,
                price=price,
                quantity=abs(quantity),
                order_type=order_type,
                strategy_id=self.__class__.__name__
            )
            
            if self.broker:
                # 通过broker下单
                result = self.broker.place_order(order)
                if result:
                    if isinstance(result, Order):
                        order_result = result
                    else:
                        # 如果返回的是订单ID字符串，创建新的Order对象
                        order_result = Order(
                            symbol=symbol,
                            price=price,
                            quantity=abs(quantity),
                            order_type=order_type,
                            strategy_id=self.__class__.__name__,
                            order_id=str(result),
                            status="SUBMITTED"
                        )
                    
                    # 保存订单到数据库
                    with get_session() as session:
                        order_model = OrderModel(
                            order_id=order_result.order_id,
                            symbol=symbol,
                            price=price,
                            quantity=quantity,
                            order_type=order_type,
                            strategy_id=self.__class__.__name__,
                            status=order_result.status
                        )
                        session.add(order_model)
                        session.commit()
                    
                    # 发送微信通知
                    message = (
                        f"交易提醒\n"
                        f"策略: {self.__class__.__name__}\n"
                        f"操作: {'买入' if quantity > 0 else '卖出'}\n"
                        f"股票: {symbol}\n"
                        f"价格: {price:.2f}\n"
                        f"数量: {abs(quantity)}\n"
                        f"订单号: {order_result.order_id}"
                    )
                    self._send_wechat_message(message)
                    return order_result
                else:
                    self.logger.error("下单失败：broker返回空结果")
                    return None
            else:
                self.logger.error("broker未设置")
                return None
                
        except Exception as e:
            self.logger.error(f"下单失败: {str(e)}")
            return None
    
    def _send_wechat_message(self, message: str):
        """发送微信消息，添加股票名称信息"""
        try:
            if hasattr(self, 'wechat_pusher'):
                # 在消息中添加股票名称
                stock_info = (f"[{self.name}({self.symbol})]"
                            if hasattr(self, 'name') else "")
                formatted_message = f"{stock_info}\n{message}"
                self.wechat_pusher.send(formatted_message)
            else:
                self.logger.warning("未配置微信推送服务")
        except Exception as e:
            self.logger.error(f"发送微信消息失败: {str(e)}")
    
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