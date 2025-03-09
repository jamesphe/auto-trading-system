from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from core.strategy import BaseStrategy

class ChandelierExitStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any] = None, broker=None):
        """初始化策略"""
        self.broker = broker  # 需要在super().__init__之前设置broker
        
        # 初始化数据缓存
        self.daily_price_cache = {}   # 日线价格数据缓存
        self.daily_volume_cache = {}  # 日线成交量数据缓存
        self.hourly_price_cache = {}  # 小时线价格数据缓存
        self.hourly_volume_cache = {} # 小时线成交量数据缓存
        
        # 直接从config中获取market_client
        self.market_client = config.get('market_client') if config else None
        super().__init__(config)

    def _init(self):
        """初始化策略特定变量"""
        # 设置日志级别为DEBUG
        self.logger.setLevel('DEBUG')
        
        self.position = 0
        self.entry_price = 0
        self.current_stop = 0
        self.add_count = 0
        self.initial_size = 0
        
        # 默认参数
        self.default_params = {
            'daily_lookback': 22,      # 日线回看周期
            'hourly_lookback': 8,      # 小时线回看周期
            'daily_multiplier': 3.0,   # 日线ATR倍数
            'hourly_multiplier': 2.0,  # 小时线ATR倍数
            'initial_stop_atr': 2.0,   # 初始止损ATR倍数
            'risk_per_trade': 0.01,    # 每笔交易风险比例
            'first_exit_ratio': 0.5,   # 首次止盈比例
            'max_add_times': 2,        # 最大加仓次数
            'target_type': 'atr',      # 目标价类型：fixed/atr/prev_high
            'target_value': 3.0,       # 目标价值(ATR倍数或百分比)
            'add_position_ratio': 0.3,  # 加仓比例
            'drawdown_exit': 0.3,      # 回撤止盈比例
            'volume_check_ratio': 0.05, # 流动性检查阈值
            'volatility_exit': 1.5,    # 波动率退出倍数
            'margin_limit': 0.8        # 保证金使用率限制
        }

        # 添加以下属性初始化
        self.highest_price = 0
        self.initial_atr = None
        self.profit_taken = False
        self.gateway = None  # 如果需要使用gateway

    def initialize(self):
        """初始化策略参数"""
        self.logger.debug("开始初始化 ChandelierExitStrategy")
        
        if not self.config:
            self.logger.warning("未找到配置信息")
            self.params = self.default_params
            return

        self.symbol = self.config.get("symbol")
        self.name = self.config.get("name")
        
        # 初始化持仓信息
        position_info = self.config.get("position", {})
        self.positions[self.symbol] = {
            "volume": position_info.get("volume", 0),
            "cost": position_info.get("cost", 0)
        }
        
        # 获取策略特定参数
        strategy_params = self.config.get("strategies", {}).get(
            "chandelier_exit", {}
        )
        
        # 使用配置文件中的参数覆盖默认参数
        self.params = {**self.default_params, **strategy_params}
        
        # 获取至少20天的日线数据
        end_date = datetime.now()
        start_date = end_date - pd.Timedelta(days=45)
        
        self.logger.debug(
            f"开始获取历史数据:\n"
            f"  股票代码: {self.symbol}\n"
            f"  时间范围: {start_date} - {end_date}"
        )
        
        history_df = self.market_client.get_history(
            symbol=self.symbol,  # 确保格式为 "300076.SZ"
            start=start_date,
            end=end_date,
            timeframe="1d"
        )
        
        self.logger.debug(
            f"获取到的历史数据:\n"
            f"  数据类型: {type(history_df)}\n"
            f"  数据内容: {history_df}"
        )
        
        if history_df is not None and not history_df.empty:
            self.history_data = {
                'daily_close': history_df['close'].tolist(),
                'daily_high': history_df['high'].tolist(),
                'daily_low': history_df['low'].tolist(),
                'daily_volume': history_df['volume'].tolist(),
                'hourly_close': [],  # 小时线数据将在需要时更新
                'hourly_high': [],
                'hourly_low': []
            }
            
            self.logger.info(
                f"成功加载历史数据:\n"
                f"  数据长度: {len(self.history_data['daily_close'])}天\n"
                f"  最新收盘价: {self.history_data['daily_close'][-1]:.2f}"
            )
        else:
            self.logger.error(
                "历史数据无效:\n"
                f"  history_df: {history_df}\n"
                f"  是否为None: {history_df is None}\n"
                f"  是否为空: {history_df.empty if history_df is not None else True}"
            )
            self.history_data = None

        self.logger.info(
            f"策略初始化完成:\n"
            f"  股票: {self.name}({self.symbol})\n"
            f"  当前持仓: {self.positions[self.symbol]}\n"
            f"  策略参数: {self.params}"
        )

    def calculate_atr(self, high: np.array, low: np.array, close: np.array, period: int) -> float:
        """计算ATR"""
        tr = np.maximum(high - low, 
             np.maximum(np.abs(high - np.roll(close, 1)), 
                       np.abs(low - np.roll(close, 1))))
        return np.mean(tr[-period:])

    def update_trailing_stop(self, data: Dict) -> float:
        """更新吊灯止损位"""
        # 计算日线ATR和最高价
        daily_atr = self.calculate_atr(
            data['daily_high'], 
            data['daily_low'], 
            data['daily_close'], 
            self.params['daily_lookback']
        )
        self.logger.debug(f"日线ATR: {daily_atr:.2f}")
        
        daily_high = np.max(data['daily_high'][-self.params['daily_lookback']:])
        daily_stop = daily_high - self.params['daily_multiplier'] * daily_atr
        self.logger.debug(f"日线止损位: {daily_stop:.2f}")

        # 计算小时线ATR和最高价
        hourly_atr = self.calculate_atr(
            data['hourly_high'],
            data['hourly_low'],
            data['hourly_close'],
            self.params['hourly_lookback']
        )
        self.logger.debug(f"小时线ATR: {hourly_atr:.2f}")
        
        hourly_high = np.max(data['hourly_high'][-self.params['hourly_lookback']:])
        hourly_stop = hourly_high - self.params['hourly_multiplier'] * hourly_atr
        self.logger.debug(f"小时线止损位: {hourly_stop:.2f}")

        # 取较高的止损位
        self.current_stop = max(daily_stop, hourly_stop)
        self.logger.debug(f"最终止损位: {self.current_stop:.2f}")
        return self.current_stop

    def check_entry(self, data: Dict) -> bool:
        """检查入场条件"""
        try:
            # 确保有足够的历史数据
            if len(data.get('daily_close', [])) < 20 or len(data.get('daily_high', [])) < 20:
                self.logger.debug("历史数据不足20天，跳过入场检查")
                return False
            
            # 计算均线
            ema5 = pd.Series(data['daily_close']).ewm(span=5).mean()
            ema20 = pd.Series(data['daily_close']).ewm(span=20).mean()
            
            # 检查条件
            price_breakout = data['daily_close'][-1] > np.max(data['daily_high'][-20:-1])
            ema_cross = ema5.iloc[-1] > ema20.iloc[-1] and ema5.iloc[-2] <= ema20.iloc[-2]
            volume_active = data['daily_volume'][-1] > np.mean(data['daily_volume'][-5:])
            
            self.logger.debug(
                f"入场条件检查:\n"
                f"  价格突破: {price_breakout}\n"
                f"  均线交叉: {ema_cross}\n"
                f"  成交量活跃: {volume_active}\n"
                f"  当前价格: {data['daily_close'][-1]:.2f}\n"
                f"  EMA5: {ema5.iloc[-1]:.2f}\n"
                f"  EMA20: {ema20.iloc[-1]:.2f}"
            )
            
            return price_breakout and ema_cross and volume_active
        except Exception as e:
            self.logger.error(f"检查入场条件时发生错误: {str(e)}")
            return False

    def calculate_position_size(self, price: float, stop: float) -> float:
        """计算仓位大小"""
        account_value = self.gateway.get_account_value() if self.gateway else 100000
        risk_amount = account_value * self.params['risk_per_trade']
        self.initial_size = int(risk_amount / (price - stop))
        return self.initial_size

    def check_add_position(self, current_price: float, current_atr: float) -> Optional[int]:
        """检查是否可以加仓"""
        if (current_price > self.entry_price * 1.03 and 
            self.add_count < self.params['max_add_times']):
            
            new_size = int(self.initial_size * (0.5 ** self.add_count))
            self.add_count += 1
            return new_size
        return None

    def check_exit(self, current_price: float) -> bool:
        """检查是否需要退出"""
        return current_price < self.current_stop

    def check_take_profit(self, current_price: float) -> Optional[int]:
        """检查是否需要止盈"""
        if not hasattr(self, 'highest_price'):
            self.highest_price = self.entry_price
        
        # 更新最高价
        self.highest_price = max(self.highest_price, current_price)
        
        # 计算回撤百分比
        drawdown = (self.highest_price - current_price) / self.highest_price
        
        # 分批止盈逻辑
        if not hasattr(self, 'profit_taken'):
            self.profit_taken = False
            
        # 首次止盈
        if not self.profit_taken and current_price >= self.entry_price * 1.1:
            self.profit_taken = True
            return int(self.position * self.params['first_exit_ratio'])
            
        # 回撤止盈
        if drawdown >= 0.3:  # 30%回撤止盈
            return int(self.position * 0.3)
            
        return None

    def check_volatility_exit(self, current_atr: float) -> bool:
        """检查波动率是否过大需要减仓"""
        if not hasattr(self, 'initial_atr'):
            self.initial_atr = current_atr
            return False
            
        return current_atr > self.initial_atr * 1.5  # ATR增加50%时减仓

    def check_risk_matrix(self, data: Dict) -> Optional[int]:
        """检查风险控制矩阵"""
        try:
            # 添加基本检查
            if not self.position or self.position <= 0:
                return None
            
            # 添加数据有效性检查
            if len(data['daily_volume']) < 5 or len(data['daily_high']) < 15:
                self.logger.warning("数据长度不足，跳过风险检查")
                return None
            
            # 流动性风险检查
            avg_volume = np.mean(data['daily_volume'][-5:])
            volume_ratio = data['daily_volume'][-1] / avg_volume
            self.logger.debug(f"流动性检查 - 当前成交量/平均成交量: {volume_ratio:.2f}")
            
            if volume_ratio < 0.05:
                self.logger.debug("触发流动性风险控制")
                return int(self.position * 0.5)
            
            # 波动性风险检查
            current_atr = self.calculate_atr(
                data['daily_high'][-15:],
                data['daily_low'][-15:],
                data['daily_close'][-15:],
                15
            )
            if hasattr(self, 'initial_atr'):
                atr_ratio = current_atr / self.initial_atr
                self.logger.debug(f"波动率检查 - 当前ATR/初始ATR: {atr_ratio:.2f}")
                
            if self.check_volatility_exit(current_atr):
                self.logger.debug("触发波动率风险控制")
                return int(self.position * 0.5)
            
            # 隔夜风险检查
            if datetime.now().hour >= 14:
                margin_ratio = self.gateway.get_margin_ratio() if self.gateway else 0.5
                self.logger.debug(f"隔夜风险检查 - 保证金使用率: {margin_ratio:.2f}")
                
                if margin_ratio > 0.8:
                    self.logger.debug("触发保证金风险控制")
                    return int(self.position * 0.3)
            
            return None
            
        except Exception as e:
            self.logger.error(f"风险矩阵检查失败: {str(e)}")
            return None

    def place_order(self, symbol: str, price: float, quantity: int, reason: str, order_type: str = "MARKET"):
        """重写下单方法，添加订单管理"""
        # 添加基本检查
        if not symbol or not price or not quantity:
            self.logger.error("订单参数无效")
            return None
        
        # 添加持仓检查
        if quantity < 0 and abs(quantity) > self.get_position(symbol):
            self.logger.error("卖出数量大于持仓量")
            return None
        
        return super().place_order(symbol, price, quantity, reason, order_type)

    def on_bar(self, data: Dict):
        """处理K线数据"""
        try:
            # 添加数据有效性检查
            required_fields = ['daily_close', 'daily_high', 'daily_low', 'daily_volume']
            for field in required_fields:
                if field not in data or len(data[field]) < self.params['daily_lookback']:
                    self.logger.warning(f"数据字段 {field} 不存在或长度不足")
                    return
                
            # 更新止损位
            self.update_trailing_stop(data)
            current_price = data['daily_close'][-1]
            current_position = self.get_position(self.symbol)
            
            self.logger.debug(
                f"K线更新:\n"
                f"  当前价格: {current_price:.2f}\n"
                f"  当前持仓: {current_position}\n"
                f"  止损价位: {self.current_stop:.2f}"
            )

            # 检查平仓
            if current_position > 0 and self.check_exit(current_price):
                self.logger.debug(
                    f"触发止损平仓:\n"
                    f"  当前价格: {current_price:.2f}\n"
                    f"  止损价位: {self.current_stop:.2f}\n"
                    f"  平仓数量: {current_position}"
                )
                self.place_order(
                    symbol=self.symbol,
                    price=current_price,
                    quantity=-current_position,
                    reason="触发吊灯止损",
                    order_type="MARKET"
                )
                return

            # 检查入场
            if current_position == 0 and self.check_entry(data):
                self.entry_price = current_price
                size = self.calculate_position_size(current_price, self.current_stop)
                self.place_order(
                    symbol=self.symbol,
                    price=current_price,
                    quantity=size,
                    reason="吊灯策略入场",
                    order_type="LIMIT"
                )
                return

            # 检查加仓
            if current_position > 0:
                current_atr = self.calculate_atr(
                    data['daily_high'],
                    data['daily_low'],
                    data['daily_close'],
                    14
                )
                add_size = self.check_add_position(current_price, current_atr)
                if add_size:
                    self.place_order(
                        symbol=self.symbol,
                        price=current_price,
                        quantity=add_size,
                        reason="吊灯策略加仓",
                        order_type="LIMIT"
                    )

            # 检查止盈
            if current_position > 0:
                profit_exit_size = self.check_take_profit(current_price)
                if profit_exit_size:
                    self.place_order(
                        symbol=self.symbol,
                        price=current_price,
                        quantity=-profit_exit_size,
                        reason="止盈",
                        order_type="LIMIT"
                    )
                    
                # 检查风险矩阵
                risk_exit_size = self.check_risk_matrix(data)
                if risk_exit_size:
                    self.place_order(
                        symbol=self.symbol,
                        price=current_price,
                        quantity=-risk_exit_size,
                        reason="风险控制",
                        order_type="MARKET"
                    )

        except Exception as e:
            self.logger.error(f"处理K线数据出错: {str(e)}")
            self._send_wechat_message(f"策略运行异常: {str(e)}")

    def on_tick(self, tick_data: Dict[str, Any]):
        """处理TICK数据"""
        try:
            symbol = tick_data["symbol"]
            current_price = tick_data["price"]
            current_volume = tick_data.get("volume", 0)
            
            # 更新价格缓存
            if symbol not in self.hourly_price_cache:
                self.hourly_price_cache[symbol] = {'close': [], 'high': [], 'low': []}
                self.hourly_volume_cache[symbol] = []
            
            self.hourly_price_cache[symbol]['close'].append(current_price)
            self.hourly_price_cache[symbol]['high'].append(current_price)
            self.hourly_price_cache[symbol]['low'].append(current_price)
            self.hourly_volume_cache[symbol].append(current_volume)
            
            # 保持固定长度的历史数据
            max_length = self.params['hourly_lookback'] * 2
            if len(self.hourly_price_cache[symbol]['close']) > max_length:
                for key in ['close', 'high', 'low']:
                    self.hourly_price_cache[symbol][key] = \
                        self.hourly_price_cache[symbol][key][-max_length:]
                self.hourly_volume_cache[symbol] = \
                    self.hourly_volume_cache[symbol][-max_length:]
            
            # 构建当前数据
            current_data = {
                'daily_close': self.daily_price_cache[symbol]['close'],
                'daily_high': self.daily_price_cache[symbol]['high'],
                'daily_low': self.daily_price_cache[symbol]['low'],
                'daily_volume': self.daily_volume_cache[symbol],
                'hourly_close': self.hourly_price_cache[symbol]['close'],
                'hourly_high': self.hourly_price_cache[symbol]['high'],
                'hourly_low': self.hourly_price_cache[symbol]['low']
            }
            
            # 检查是否需要更新止损位
            self.current_stop = self.update_trailing_stop(current_data)
            
            # 检查是否触发止损
            if self.check_exit(current_price):
                self.logger.info(f"触发实时止损: 当前价格={current_price}, 止损价={self.current_stop}")
                current_position = self.get_position(symbol)
                if current_position > 0:
                    self.place_order(
                        symbol=symbol,
                        price=current_price,
                        quantity=-current_position,
                        reason="实时监控触发吊灯止损",
                        order_type="MARKET"
                    )
                
        except Exception as e:
            self.logger.error(f"处理Tick数据出错: {str(e)}", exc_info=True)

    def execute(self, market_data: Dict[str, Any]):
        """执行策略"""
        try:
            self.logger.debug(f"执行 ChandelierExit 策略，数据: {market_data}")
            
            symbol = market_data.get("symbol")
            if not symbol:
                self.logger.warning("市场数据缺少股票代码")
                return
            
            # 合并历史数据和实时数据
            current_data = {
                'daily_close': [market_data.get('close', 0)],
                'daily_high': [market_data.get('high', 0)],
                'daily_low': [market_data.get('low', 0)],
                'daily_volume': [market_data.get('volume', 0)],
                'hourly_close': [market_data.get('close', 0)],
                'hourly_high': [market_data.get('high', 0)],
                'hourly_low': [market_data.get('low', 0)]
            }
            
            if self.history_data:
                data = {
                    'daily_close': self.history_data['daily_close'] + current_data['daily_close'],
                    'daily_high': self.history_data['daily_high'] + current_data['daily_high'],
                    'daily_low': self.history_data['daily_low'] + current_data['daily_low'],
                    'daily_volume': self.history_data['daily_volume'] + current_data['daily_volume'],
                    'hourly_close': current_data['hourly_close'],  # 小时线数据不需要合并历史数据
                    'hourly_high': current_data['hourly_high'],
                    'hourly_low': current_data['hourly_low']
                }
            else:
                self.logger.warning("没有历史数据，使用单个数据点")
                data = current_data
            
            current_price = market_data.get('close', 0)
            position = self.position
            
            # 如果没有持仓，寻找入场机会
            if position == 0:
                if self.check_entry(data):
                    self.entry_price = current_price
                    size = self.calculate_position_size(current_price, self.current_stop)
                    self.place_order(
                        symbol=symbol,
                        price=current_price,
                        quantity=size,
                        reason="吊灯策略入场",
                        order_type="LIMIT"
                    )
            else:
                # 如果有持仓，检查是否需要调整止损或退出
                if self.check_exit(current_price):
                    self.place_order(
                        symbol=symbol,
                        price=current_price,
                        quantity=-position,
                        reason="吊灯策略止损",
                        order_type="MARKET"
                    )
                
        except Exception as e:
            self.logger.error(f"策略执行出错: {str(e)}", exc_info=True)

    def _load_history_data(self):
        """加载历史数据"""
        self.logger.debug("开始加载历史数据")
        try:
            if not self.broker or not hasattr(self.broker, 'market_client'):
                self.logger.error("broker未设置或没有market_client")
                return
            
            # 获取当前时间和30天前的时间
            end = datetime.now()
            start = end - timedelta(days=30)
            
            # 获取日线数据
            df_daily = self.broker.market_client.get_history(
                symbol=self.symbol,
                start=start,
                end=end,
                timeframe="1d"
            )
            
            if not df_daily.empty:
                self.daily_price_cache[self.symbol] = {
                    'close': df_daily['close'].values.tolist(),
                    'high': df_daily['high'].values.tolist(),
                    'low': df_daily['low'].values.tolist()
                }
                self.daily_volume_cache[self.symbol] = df_daily['volume'].values.tolist()
            
            # 获取小时线数据
            df_hourly = self.broker.market_client.get_history(
                symbol=self.symbol,
                start=start,
                end=end,
                timeframe="1h"
            )
            
            if not df_hourly.empty:
                self.hourly_price_cache[self.symbol] = {
                    'close': df_hourly['close'].values.tolist(),
                    'high': df_hourly['high'].values.tolist(),
                    'low': df_hourly['low'].values.tolist()
                }
                self.hourly_volume_cache[self.symbol] = df_hourly['volume'].values.tolist()
            
        except Exception as e:
            self.logger.error(f"加载历史数据失败: {e}", exc_info=True)