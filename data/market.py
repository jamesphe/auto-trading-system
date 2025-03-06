from typing import Dict, List, Any, Callable
import logging
import threading
import time
import pandas as pd
from datetime import datetime, timedelta
import random
from data.storage import SQLiteStorage
from data.sources.akshare_source import AKShareDataSource
import akshare as ak

class MarketDataClient:
    """行情数据客户端"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger("data.MarketDataClient")
        self.logger.info(f"初始化行情客户端，配置: {self.config}")
        self.subscriptions = {}  # symbol -> handlers
        self.running = False
        self.simulator_thread = None
        
        # 初始化数据源
        data_source = self.config.get("data_source", "akshare")  # 默认使用akshare
        self.logger.info(f"使用数据源: {data_source}")
        
        if data_source == "akshare":
            self.data_source = AKShareDataSource()
            self.use_real_data = True
            self.logger.info("已初始化 AKShare 数据源")
        elif data_source == "simulated":
            self.data_source = None
            self.use_real_data = False
            self.logger.info("使用模拟数据源，不生成行情")
        else:
            self.data_source = None
            self.use_real_data = False
            self.logger.warning(f"未知数据源: {data_source}，使用模拟数据源")
        
        # 初始化存储
        storage_config = self.config.get("storage", {})
        if not storage_config:
            self.logger.warning("未找到存储配置，使用默认配置")
            storage_config = {
                "db_path": "trading.db",
                "save_market_data": True,
                "save_interval": 60
            }
        self.logger.debug(f"使用存储配置: {storage_config}")
        self.storage = SQLiteStorage(storage_config)
    
    def subscribe(self, symbols: List[str], handlers: Dict[str, Callable]):
        """订阅行情数据"""
        for symbol in symbols:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = handlers
                self.logger.info(f"订阅行情: {symbol}")
            else:
                # 更新现有订阅的处理器
                self.subscriptions[symbol].update(handlers)
        
        # 根据配置决定是否启动模拟器或实时数据获取
        if not self.running and self.subscriptions:
            if self.use_real_data:
                self._start_real_data_fetching()  # 启动实时数据获取
            else:
                self.start_simulator()  # 启动模拟器
    
    def _start_real_data_fetching(self):
        """启动实时数据获取"""
        if self.running:
            return
        
        self.running = True
        self.real_data_thread = threading.Thread(
            target=self._fetch_real_market_data,
            name="RealMarketDataFetcher",
            daemon=True
        )
        self.real_data_thread.start()
        self.logger.info("启动实时行情数据获取")
    
    def unsubscribe(self, symbol: str):
        """取消订阅
        
        Args:
            symbol: 标的代码
        """
        if symbol in self.subscriptions:
            del self.subscriptions[symbol]
            self.logger.info(f"取消订阅: {symbol}")
    
    def get_history(self, symbol: str, 
                   start: datetime, 
                   end: datetime, 
                   timeframe: str = "1d") -> pd.DataFrame:
        """获取历史K线数据
        
        Args:
            symbol: 标的代码
            start: 开始时间
            end: 结束时间
            timeframe: 时间周期
            
        Returns:
            pd.DataFrame: 历史数据
        """
        if not self.use_real_data:
            return self._get_simulated_history(symbol, start, end, timeframe)
        
        code = symbol.split('.')[0]
        try:
            # 使用akshare获取历史数据
            df = ak.stock_zh_a_hist(symbol=code, 
                                  start_date=start.strftime("%Y%m%d"),
                                  end_date=end.strftime("%Y%m%d"),
                                  adjust="qfq")  # 前复权数据
            
            if df.empty:
                raise ValueError(f"获取历史数据为空: {symbol}")
            
            # 重命名列以统一格式
            df = df.rename(columns={
                "日期": "timestamp",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount"
            })
            
            # 转换日期格式
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 按时间排序
            df = df.sort_values('timestamp')
            
            return df
            
        except Exception as e:
            if self.config.get("mode") == "live":
                raise  # live模式下直接抛出异常
            else:
                # 非live模式下使用模拟数据
                self.logger.warning(f"使用模拟数据替代: {str(e)}")
                return self._get_simulated_history(symbol, start, end, timeframe)
    
    def _get_simulated_history(self, symbol: str, 
                             start: datetime,
                             end: datetime,
                             timeframe: str = "1d") -> pd.DataFrame:
        """生成模拟的历史数据"""
        days = (end - start).days + 1
        dates = [start + timedelta(days=i) for i in range(days)]
        
        # 生成随机价格
        base_price = 100.0
        data = []
        
        for date in dates:
            open_price = base_price * (1 + random.uniform(-0.02, 0.02))
            high_price = open_price * (1 + random.uniform(0, 0.03))
            low_price = open_price * (1 - random.uniform(0, 0.03))
            close_price = low_price + random.uniform(0, high_price - low_price)
            volume = random.randint(10000, 1000000)
            
            data.append({
                'timestamp': date,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
            
            # 更新基准价格
            base_price = close_price
        
        return pd.DataFrame(data)
    
    def start_simulator(self):
        """启动行情模拟器"""
        if self.running:
            return
        
        self.running = True
        self.simulator_thread = threading.Thread(
            target=self._simulate_market_data,
            name="MarketDataSimulator",
            daemon=True
        )
        self.simulator_thread.start()
        self.logger.info("启动行情模拟器")
    
    def stop_simulator(self):
        """停止行情模拟器"""
        self.running = False
        if self.simulator_thread:
            self.simulator_thread.join(timeout=1.0)
        self.logger.info("停止行情模拟器")
    
    def _simulate_market_data(self):
        try:
            if self.use_real_data:
                self._fetch_real_market_data()
            else:
                self._simulate_fake_data()
        except Exception as e:
            self.logger.error(f"市场数据处理异常: {e}", exc_info=True)
            raise

    def _fetch_real_market_data(self):
        """获取真实市场数据"""
        update_interval = self.config.get("update_interval", 30)  # 默认30秒
        self.logger.info(f"设置行情更新间隔: {update_interval}秒")
        
        last_update_time = 0
        last_log_time = 0  # 添加日志时间控制
        
        while self.running:
            try:
                current_time = time.time()
                time_since_last_update = current_time - last_update_time
                
                # 如果距离上次更新时间不足间隔时间，则等待
                if time_since_last_update < update_interval:
                    time.sleep(0.1)  # 短暂休眠以避免CPU占用
                    continue
                
                symbols = list(self.subscriptions.keys())
                # 控制日志输出频率
                if current_time - last_log_time > 30:
                    self.logger.debug(f"开始获取行情数据: {symbols}")
                    last_log_time = current_time
                
                # 使用 AKShare 数据源获取实时数据
                for symbol in symbols:
                    try:
                        # 从 AKShare 获取实时数据
                        quotes = self.data_source.get_realtime_quotes([symbol])
                        if not quotes:  # 检查列表是否为空
                            continue
                            
                        quote = quotes[0]  # 获取第一个报价数据
                        # 转换为标准格式
                        market_data = {
                            "symbol": symbol,
                            "timestamp": datetime.now().isoformat(),
                            "data_type": "tick",
                            "price": float(quote["price"]),
                            "volume": int(quote["volume"]),
                            "amount": float(quote.get("amount", 0)),
                            "open": float(quote["open"]),
                            "high": float(quote["high"]),
                            "low": float(quote["low"]),
                            "close": float(quote["price"])  # 最新价作为收盘价
                        }
                        
                        # 保存到数据库
                        self.storage.save("market_data", {
                            **market_data,
                            "created_at": datetime.now().isoformat()
                        })
                        
                        # 触发回调
                        if "tick" in self.subscriptions[symbol]:
                            self.subscriptions[symbol]["tick"](market_data)
                            
                    except Exception as e:
                        self.logger.error(f"获取{symbol}行情数据失败: {e}")
                        if self.config.get("mode") == "live":
                            raise  # live模式下直接抛出异常
                
                # 更新最后更新时间
                last_update_time = current_time
                
            except Exception as e:
                self.logger.error(f"获取行情数据失败: {e}")
                if self.config.get("mode") == "live":
                    raise  # live模式下直接抛出异常
                time.sleep(1)  # 出错后等待1秒再重试

    def _simulate_fake_data(self):
        """模拟市场数据生成"""
        try:
            prices = {}  # 记录每个股票的当前价格
            prev_close = {}  # 记录前收盘价
            
            # 为600580设置特定的初始价格和前收盘价
            prices["600580.SH"] = 25.0  # 当前价格
            prev_close["600580.SH"] = 24.0  # 前收盘价（低于当前价格）
            
            # 记录是否已经生成过开盘K线
            opening_kline_generated = False
            
            while self.running:
                current_time = datetime.now()
                
                # 复制订阅列表避免迭代时修改
                symbols = list(self.subscriptions.keys())
                
                # 模拟9:30开盘时生成高开K线
                is_market_open = (
                    not opening_kline_generated 
                    and current_time.hour == 9 
                    and current_time.minute == 30
                )
                if is_market_open:
                    for symbol in symbols:
                        if symbol == "600580.SH":
                            # 生成高开K线 (开盘价高于前收盘价2.5%)
                            open_price = prev_close[symbol] * 1.025
                            kline_data = {
                                "symbol": symbol,
                                "open": open_price,
                                "high": open_price * 1.01,
                                "low": open_price * 0.99,
                                "close": open_price * 1.005,
                                "volume": random.randint(10000, 50000),
                                "timestamp": current_time.isoformat(),
                                "timeframe": "1m",
                                "data_type": "kline"
                            }
                            
                            # 调用K线处理器
                            if "kline" in self.subscriptions[symbol]:
                                self.subscriptions[symbol]["kline"](kline_data)
                                
                            # 更新当前价格
                            prices[symbol] = kline_data["close"]
                            
                    opening_kline_generated = True
                
                # 为每个订阅的股票生成模拟数据
                for symbol in symbols:
                    # 初始化价格
                    if symbol not in prices and symbol != "600580.SH":
                        prices[symbol] = random.uniform(10.0, 100.0)
                        prev_close[symbol] = (
                            prices[symbol] * random.uniform(0.95, 1.05)
                        )
                        
                    # 模拟价格波动
                    if symbol == "600580.SH":
                        # 600580价格持续上涨
                        # 偏向上涨
                        price_change = (
                            prices[symbol] * random.uniform(0.001, 0.005)
                        )
                    else:
                        # 其他股票正常波动
                        price_change = (
                            prices[symbol] * random.uniform(-0.005, 0.005)
                        )
                        
                    prices[symbol] += price_change
                    
                    # 生成tick数据
                    tick_data = {
                        "symbol": symbol,
                        "price": prices[symbol],
                        "volume": random.randint(100, 10000),
                        "timestamp": current_time.isoformat(),
                        "data_type": "tick"
                    }
                    
                    # 保存到数据库
                    self.storage.save("market_data", {
                        "symbol": symbol,
                        "timestamp": current_time.isoformat(),
                        "data_type": "tick",
                        "price": prices[symbol],
                        "volume": tick_data["volume"],
                        "open": None,
                        "high": None,
                        "low": None,
                        "close": None,
                        "created_at": current_time.isoformat()
                    })
                    
                    # 生成K线数据
                    kline_data = {
                        "symbol": symbol,
                        "open": prices[symbol],
                        "high": prices[symbol] * 1.001,
                        "low": prices[symbol] * 0.999,
                        "close": prices[symbol],
                        "volume": random.randint(10000, 50000),
                        "timestamp": current_time.isoformat(),
                        "timeframe": "1m",
                        "data_type": "kline"
                    }
                    
                    # 保存到数据库
                    self.storage.save("market_data", {
                        "symbol": symbol,
                        "timestamp": current_time.isoformat(),
                        "data_type": "kline",
                        "open": kline_data["open"],
                        "high": kline_data["high"],
                        "low": kline_data["low"],
                        "close": kline_data["close"],
                        "volume": kline_data["volume"],
                        "created_at": current_time.isoformat()
                    })
                    
                    # 添加调试日志
                    if self.config.get("debug_mode"):
                        self.logger.debug(
                            f"生成行情数据: {symbol}, "
                            f"时间={current_time.strftime('%H:%M:%S')}, "
                            f"价格={prices[symbol]:.2f}, "
                            f"成交量={tick_data['volume']}"
                        )
                    
                    # 调用处理器
                    if "tick" in self.subscriptions[symbol]:
                        self.subscriptions[symbol]["tick"](tick_data)
                
                # 每秒生成一次数据
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"模拟市场数据生成异常: {e}", exc_info=True)
            raise 

    def _process_market_data(self, data: Dict[str, Any]):
        """处理市场数据"""
        try:
            self.logger.debug(f"处理市场数据: {data}")
            
            # 构造K线数据
            kline_data = {
                "symbol": data["symbol"],
                "timestamp": datetime.now().isoformat(),
                "open": float(data["open"]),
                "high": float(data["high"]),
                "low": float(data["low"]),
                "close": float(data["close"]),
                "volume": int(data["volume"]),
                "data_type": "kline"
            }
            
            self.logger.info(f"发送K线数据: {data['symbol']}")
            # 发送给所有订阅者
            for handlers in self.subscriptions.values():
                if "kline" in handlers:
                    handlers["kline"](kline_data)
                    
        except Exception as e:
            self.logger.error(f"处理市场数据错误: {str(e)}", exc_info=True) 

    def close(self):
        """关闭行情连接，清理资源"""
        self.logger.info("关闭行情连接")
        # 如果有需要清理的资源，在这里添加清理代码 

    def get_realtime_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情数据"""
        if not self.use_real_data:
            return self._get_simulated_quotes(symbols)
        
        for symbol in symbols:
            code = symbol.split('.')[0]
            try:
                df = ak.stock_zh_a_spot_em()
                if df.empty:
                    raise ValueError(f"获取行情数据为空: {symbol}")
                
                stock_data = df[df['代码'] == code]
                if stock_data.empty:
                    raise ValueError(f"未找到股票行情数据: {symbol}")
                
                # 处理真实数据...
                
            except Exception as e:
                if self.config.get("mode") == "live":
                    raise  # live模式下直接抛出异常
                else:
                    # 非live模式下可以使用测试数据
                    self.logger.warning(f"使用测试数据替代: {str(e)}")
                    return self._get_simulated_quotes(symbols) 