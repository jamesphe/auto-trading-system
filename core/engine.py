import logging
from typing import Dict, List, Any, Callable, Optional
import threading
import time
from datetime import datetime

from core.strategy import BaseStrategy
from core.order import OrderManager, Order, OrderStatus
from data.market import MarketDataClient
from gateway.broker import TradeGateway, SimulatedTradeGateway
from utils.metrics import MetricsCollector

class RuleEngine:
    """规则引擎，负责策略执行和事件处理"""
    
    def __init__(self, config: Dict[str, Any] = None, gateway=None):
        """初始化规则引擎"""
        self.config = config or {}
        
        # 设置日志
        self.logger = logging.getLogger("engine.RuleEngine")
        # 确保日志级别设置为DEBUG
        self.logger.setLevel(logging.ERROR)
        
        # 添加控制台处理器(如果还没有的话)
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        self.logger.debug("初始化规则引擎")
        
        # 初始化组件
        self.storage = None  # 需要外部设置
        self.trade_gateway = SimulatedTradeGateway(self.config.get("trade", {}))
        self.risk_manager = None  # 初始化风控管理器为 None
        self.order_manager = OrderManager()
        self.metrics = MetricsCollector(self.config.get("metrics", {}))
        
        # 其他配置
        self.rule_workers = self.config.get("rule_workers", 4)
        self.running = False
        
        # 事件队列和锁
        self.event_queue = []
        self.event_lock = threading.Lock()
        
        # 策略字典
        self.strategies = []
        
        # 配置
        self.max_orders_per_sec = self.config.get("max_orders_per_sec", 10)
        self.market_client = MarketDataClient(self.config.get("market_data", {}))
        
        self.gateway = gateway
        self.strategy_manager = None  # 添加策略管理器属性
    
    def register_strategy(self, strategy_id: str, strategy: BaseStrategy):
        """注册策略"""
        self.logger.info(f"注册策略: {strategy_id}")
        self.logger.debug(f"当前策略数量: {len(self.strategies)}")
        self.strategies.append(strategy)
        self.logger.debug(f"注册后策略数量: {len(self.strategies)}")
        
        # 设置交易网关
        if hasattr(strategy, 'set_gateway') and self.gateway:
            strategy.set_gateway(self.gateway)
            self.logger.debug(f"为策略 {strategy_id} 设置交易网关")
    
    def _process_market_data(self, event):
        """处理市场数据"""
        if self.strategy_manager:
            try:
                self.strategy_manager.on_market_data(event.data)
            except Exception as e:
                self.logger.error(f"策略执行错误: {str(e)}", exc_info=True)
    
    def on_market_data(self, data_type: str, data: Dict[str, Any]):
        """处理市场数据"""
        try:
            self.logger.debug(f"收到市场数据: {data_type}")
            self.logger.debug(f"数据内容: {data}")
            
            # 转换为事件
            event_type = f"market.{data_type}"
            self.add_event(event_type, data)
            
            # 对于K线数据，直接执行策略
            if data_type == "kline":
                for strategy in self.strategies:
                    strategy.execute(data)
            
            # 记录指标
            self.metrics.increment("market_data_received", 
                                {"type": data_type, "symbol": data.get("symbol")})
        except Exception as e:
            self.logger.error(f"处理市场数据错误: {str(e)}", exc_info=True)
    
    def add_event(self, event_type: str, event_data: Any):
        """添加事件到队列"""
        with self.event_lock:
            self.logger.debug(
                f"添加事件到队列:\n"
                f"  类型: {event_type}\n"
                f"  数据: {event_data}"
            )
            self.event_queue.append((event_type, event_data, datetime.now()))
    
    def get_next_event(self):
        """获取下一个事件
        
        Returns:
            tuple: (event_type, event_data) 或 None
        """
        with self.event_lock:
            if self.event_queue:
                event_type, event_data, event_time = self.event_queue.pop(0)
                # 计算事件延迟
                latency = (datetime.now() - event_time).total_seconds()
                self.metrics.observe("event_latency_seconds", latency, 
                                   {"type": event_type})
                return event_type, event_data
            return None
    
    def process_events(self):
        """处理事件队列"""
        print("开始处理事件循环")  # 临时调试语句
        while self.running:
            event = self.get_next_event()
            if event:
                event_type, event_data = event
                self.logger.debug(
                    f"开始处理事件:\n"
                    f"  类型: {event_type}\n"
                    f"  数据: {event_data}\n"
                    f"  注册策略数: {len(self.strategies)}"
                )
                
                # 创建一个Event对象来传递给_process_market_data
                class Event:
                    def __init__(self, type_, data):
                        self.type = type_
                        self.data = data
                
                # 处理市场数据
                if event_type.startswith("market."):
                    self._process_market_data(Event(event_type, event_data))
                    self.logger.debug(f"事件 {event_type} 处理完成")
            else:
                # 如果没有事件，短暂休眠
                time.sleep(0.01)
    
    def place_order(self, order: Order) -> Optional[str]:
        """下单处理"""
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 风控检查
            if self.risk_manager:  # 添加空值检查
                if not self.risk_manager.check_order(order):
                    self.logger.warning(f"订单未通过风控检查: {order}")
                    return None
            else:
                self.logger.warning("风控管理器未设置，跳过风控检查")
            
            # 提交订单到交易网关
            broker_order_id = self.trade_gateway.place_order(order)
            if not broker_order_id:
                self.logger.error(f"提交订单失败: {order}")
                return None
            
            # 更新订单状态
            order.update(status=OrderStatus.SUBMITTED, broker_order_id=broker_order_id)
            
            # 保存订单到数据库
            self.storage.save("orders", order.to_dict())
            
            # 记录指标
            self.metrics.increment("order_placed_total", 
                                 {"strategy": order.strategy_id, "symbol": order.symbol})
            self.metrics.observe("order_processing_seconds",
                               time.time() - start_time,
                               {"strategy": order.strategy_id})
            
            return order.order_id
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            order.update(status=OrderStatus.REJECTED)
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 是否成功
        """
        order = self.order_manager.get_order(order_id)
        if not order or not order.is_active():
            return False
        
        try:
            success = self.trade_gateway.cancel_order(order.broker_order_id)
            if success:
                self.order_manager.update_order(order_id, status=OrderStatus.CANCELLED)
                self.metrics.increment("order_cancelled_total", 
                                      {"strategy": order.strategy_id})
            return success
        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            self.metrics.increment("order_error_total", 
                                  {"strategy": order.strategy_id, "error": str(e)})
            return False
    
    def start(self):
        """启动引擎"""
        if self.running:
            return
        
        self.running = True
        self.logger.info("启动规则引擎")
        
        # 启动事件处理线程
        for i in range(self.rule_workers):
            threading.Thread(target=self.process_events, 
                           name=f"EventProcessor-{i}",
                           daemon=True).start()
        
        # 启动订单状态监听
        threading.Thread(target=self.monitor_orders, 
                       name="OrderMonitor",
                       daemon=True).start()
    
    def stop(self):
        """停止引擎"""
        self.running = False
        self.logger.info("停止规则引擎")
    
    def monitor_orders(self):
        """监控订单状态"""
        while self.running:
            try:
                # 获取活跃订单
                active_orders = self.order_manager.get_active_orders()
                
                for order in active_orders:
                    # 查询订单状态
                    if order.broker_order_id:
                        order_info = self.trade_gateway.query_order(order.broker_order_id)
                        if order_info:
                            # 更新订单状态
                            self.order_manager.update_order(
                                order.order_id,
                                status=order_info["status"],
                                filled_quantity=order_info["filled_quantity"],
                                avg_fill_price=order_info["avg_price"]
                            )
                            
                            # 通知策略
                            # 遍历策略列表查找对应的策略
                            for strategy in self.strategies:
                                if hasattr(strategy, 'strategy_id') and strategy.strategy_id == order.strategy_id:
                                    strategy.on_order_update(order)
                                    break
            except Exception as e:
                self.logger.error(f"监控订单异常: {e}")
            
            # 每秒检查一次
            time.sleep(1)
    
    def execute_order(self, order: Order):
        """执行订单"""
        try:
            # 风控检查
            if self.risk_manager:  # 添加空值检查
                if not self.risk_manager.check_order(order):
                    return False
            else:
                self.logger.warning("风控管理器未设置，跳过风控检查")
            
            # 发送订单到交易网关
            order_info = self.trade_gateway.place_order(order)
            if order_info:
                # 更新订单状态
                self.order_manager.update_order(
                    order.order_id,
                    broker_order_id=order_info["broker_order_id"],
                    status=order_info["status"]
                )
                return True
        except Exception as e:
            self.logger.error(f"执行订单失败: {e}")
            return False

    def set_risk_manager(self, risk_manager):
        """设置风控管理器
        
        Args:
            risk_manager: 风控管理器实例
        """
        self.risk_manager = risk_manager
        self.logger.info("设置风控管理器") 