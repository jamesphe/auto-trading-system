import akshare as ak
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import logging
import pandas as pd

class AKShareDataSource:
    """AKShare行情数据源"""
    
    def __init__(self):
        self.logger = logging.getLogger("data.AKShareDataSource")
        self.logger.setLevel(logging.DEBUG)
        self.last_request_time = 0
        
    def get_realtime_quotes(self, symbols: List[str], max_retries: int = 3) -> List[Dict[str, Any]]:
        """获取实时行情数据
        
        Args:
            symbols: 股票代码列表,如 ["600580.SH"]
            
        Returns:
            List[Dict]: 行情数据列表
        """
        try:
            # 检查距离上次请求的时间间隔
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            
            # 如果间隔太短，等待一段时间
            if time_since_last_request < 30:  # 30秒限制
                wait_time = 30 - time_since_last_request
                self.logger.debug(f"等待 {wait_time:.1f} 秒以遵守频率限制")
                time.sleep(wait_time)
            
            # 获取所有A股实时行情数据
            df = None
            for retry in range(max_retries):
                try:
                    # 首先尝试腾讯数据源
                    try:
                        self.logger.debug("尝试使用腾讯数据源获取数据...")
                        df = ak.stock_zh_a_spot_qq()
                        if len(df) > 1000:
                            self.logger.debug(f"腾讯数据源成功获取 {len(df)} 条记录")
                            break
                        else:
                            self.logger.warning(
                                f"腾讯数据源返回数据不完整: 只有 {len(df)} 条记录"
                            )
                    except Exception as e:
                        self.logger.warning(f"腾讯数据源获取失败: {str(e)}")
                    
                    # 如果腾讯数据源失败，尝试东方财富数据源
                    try:
                        self.logger.debug("尝试使用东方财富数据源获取数据...")
                        df = ak.stock_zh_a_spot_em()
                        if len(df) > 1000:
                            self.logger.debug(f"东方财富数据源成功获取 {len(df)} 条记录")
                            break
                        else:
                            self.logger.warning(
                                f"东方财富数据源返回数据不完整: 只有 {len(df)} 条记录"
                            )
                    except Exception as e:
                        self.logger.warning(f"东方财富数据源获取失败: {str(e)}")
                    
                    # 如果两个数据源都获取失败或数据不完整，等待后重试
                    if retry < max_retries - 1:
                        wait_time = 5 * (retry + 1)  # 递增等待时间
                        self.logger.warning(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    
                except Exception as e:
                    self.logger.error(f"第 {retry + 1} 次获取数据时发生错误: {str(e)}")
                    if retry < max_retries - 1:
                        wait_time = 5 * (retry + 1)
                        time.sleep(wait_time)
                    continue
            
            if df is None or len(df) <= 1000:
                self.logger.error("无法获取完整的行情数据")
                return []
            
            self.last_request_time = time.time()
            
            self.logger.debug(f"获取行情数据: {len(df)} 条记录")
            # 打印部分代码示例用于调试
            self.logger.debug(f"数据示例:\n代码列: {df['代码'].head().tolist()}")
            
            # 在获取数据后立即打印
            self.logger.debug(f"数据源返回总记录数: {len(df)}")
            self.logger.debug(f"数据源代码列格式示例:\n{df['代码'].head(10).to_string()}")
            
            results = []
            for symbol in symbols:
                # 移除市场后缀并处理代码格式
                code = symbol.split('.')[0]
                # 确保代码是6位数字格式
                code = code.zfill(6)
                
                # 查找对应的股票数据
                # 在查找之前，先打印实际的代码格式以便调试
                self.logger.debug(f"当前股票代码: {code}")
                self.logger.debug(f"数据源中的代码格式示例: {df['代码'].head().tolist()}")
                
                # 修改查找逻辑，使用更灵活的匹配方式
                code_variants = [
                    code,                    # 原始6位代码
                    code.lstrip('0'),        # 去掉前导零
                    str(int(code)),          # 数字形式
                    f"{int(code):06d}"       # 补零到6位
                ]
                
                stock_data = None
                for variant in code_variants:
                    self.logger.debug(f"尝试匹配代码变体: {variant}")
                    temp_data = df[df['代码'].astype(str) == variant]
                    if not temp_data.empty:
                        stock_data = temp_data
                        self.logger.debug(f"成功匹配到代码: {variant}")
                        break
                
                if stock_data is None or stock_data.empty:
                    self.logger.warning(
                        f"未找到股票行情数据: {symbol}\n"
                        f"尝试过的代码格式: {code_variants}"
                    )
                    continue
                
                stock_data = stock_data.iloc[0]
                
                # 打印完整的数据行以便调试
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("\n股票实时行情:")
                    self.logger.debug("=" * 50)
                    self.logger.debug(f"股票代码: {symbol}")
                    self.logger.debug(f"股票名称: {stock_data['名称']}")
                    self.logger.debug("-" * 30)
                    self.logger.debug("价格信息:")
                    self.logger.debug(f"  最新价: {stock_data['最新价']:>10.2f}")
                    self.logger.debug(f"  涨跌幅: {stock_data['涨跌幅']:>10.2f}%")
                    self.logger.debug(f"  涨跌额: {stock_data['涨跌额']:>10.2f}")
                    self.logger.debug(f"    今开: {stock_data['今开']:>10.2f}")
                    self.logger.debug(f"    最高: {stock_data['最高']:>10.2f}")
                    self.logger.debug(f"    最低: {stock_data['最低']:>10.2f}")
                    self.logger.debug(f"    昨收: {stock_data['昨收']:>10.2f}")
                    self.logger.debug("-" * 30)
                    self.logger.debug("成交信息:")
                    self.logger.debug(f"  成交量: {stock_data['成交量']:>10,.0f}")
                    self.logger.debug(f"  成交额: {stock_data['成交额']:>10,.0f}")
                    self.logger.debug(f"  换手率: {stock_data['换手率']:>10.2f}%")
                    self.logger.debug(f"    量比: {stock_data['量比']:>10.2f}")
                    self.logger.debug("-" * 30)
                    self.logger.debug("其他指标:")
                    self.logger.debug(f"  市盈率: {stock_data['市盈率-动态']:>10.2f}")
                    self.logger.debug(f"  市净率: {stock_data['市净率']:>10.2f}")
                    self.logger.debug(f"  总市值: {stock_data['总市值']/100000000:>10.2f}亿")
                    self.logger.debug(f"  流通值: {stock_data['流通市值']/100000000:>10.2f}亿")
                    self.logger.debug("=" * 50)
                
                # 构建标准格式的tick数据
                tick_data = {
                    "symbol": symbol,
                    "timestamp": datetime.now().isoformat(),
                    "price": float(stock_data['最新价']),    
                    "open": float(stock_data['今开']),      
                    "high": float(stock_data['最高']),      
                    "low": float(stock_data['最低']),       
                    "close": float(stock_data['最新价']),   
                    "volume": int(stock_data['成交量']),    
                    "amount": float(stock_data['成交额']),  
                    "data_type": "tick"
                }
                results.append(tick_data)
                
                # 同时生成对应的K线数据
                kline_data = {
                    "symbol": symbol,
                    "timestamp": datetime.now().isoformat(),
                    "open": tick_data["open"],
                    "high": tick_data["high"],
                    "low": tick_data["low"],
                    "close": tick_data["close"],
                    "volume": tick_data["volume"],
                    "amount": tick_data["amount"],
                    "data_type": "kline"
                }
                results.append(kline_data)
                
            return results
        except Exception as e:
            self.logger.error(f"获取行情数据失败: {e}", exc_info=True)
            return []
            
    def get_history_data(self, symbol: str, 
                        start_date: str,
                        end_date: str = None) -> List[Dict[str, Any]]:
        """获取历史K线数据
        
        Args:
            symbol: 股票代码,如 "600580.SH"
            start_date: 开始日期,如 "20250301" 
            end_date: 结束日期,如 "20250302"
            
        Returns:
            List[Dict]: K线数据列表
        """
        try:
            code = symbol.split('.')[0]
            
            # 获取日线数据
            df = ak.stock_zh_a_hist(symbol=code, 
                                  start_date=start_date,
                                  end_date=end_date)
            
            results = []
            for _, row in df.iterrows():
                kline_data = {
                    "symbol": symbol,
                    "timestamp": row['日期'].isoformat(),
                    "open": float(row['开盘']),
                    "high": float(row['最高']),
                    "low": float(row['最低']), 
                    "close": float(row['收盘']),
                    "volume": int(row['成交量'])
                }
                results.append(kline_data)
                
            return results
        except Exception as e:
            self.logger.error(f"获取历史数据失败: {e}")
            return []

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情数据"""
        try:
            # 从股票代码中提取数字部分和市场代码
            code = symbol.split('.')[0]
            market = symbol.split('.')[-1]
            
            self.logger.debug(
                f"获取实时行情:\n"
                f"  原始代码: {symbol}\n"
                f"  代码: {code}\n"
                f"  市场: {market}"
            )
            
            # 尝试多种代码格式
            try:
                # 使用东方财富数据源获取所有A股实时行情
                df = ak.stock_zh_a_spot_em()
                
                # 打印所有代码的前几个，用于调试
                self.logger.debug(f"东方财富数据源代码示例: {df['代码'].head(10).tolist()}")
                
                # 尝试不同的代码格式
                stock_codes = [
                    code,                # 原始代码
                    code.zfill(6),       # 补零到6位
                    code.lstrip('0'),    # 去掉前导零
                ]
                
                for stock_code in stock_codes:
                    self.logger.debug(f"尝试匹配代码: {stock_code}")
                    filtered_df = df[df['代码'] == stock_code]
                    
                    if not filtered_df.empty:
                        self.logger.info(f"成功匹配到股票代码: {stock_code}")
                        
                        # 转换数据格式
                        data = {
                            'symbol': symbol,
                            'timestamp': pd.Timestamp.now(),
                            'open': float(filtered_df['开盘'].iloc[0]),
                            'high': float(filtered_df['最高'].iloc[0]),
                            'low': float(filtered_df['最低'].iloc[0]),
                            'close': float(filtered_df['最新价'].iloc[0]),
                            'volume': float(filtered_df['成交量'].iloc[0]),
                            'amount': float(filtered_df['成交额'].iloc[0])
                        }
                        
                        self.logger.debug(
                            f"获取到实时行情:\n"
                            f"  股票: {symbol}\n"
                            f"  价格: {data['close']}\n"
                            f"  成交量: {data['volume']}"
                        )
                        
                        return data
                
                self.logger.warning(f"东方财富数据源未找到股票: {code}")
                raise ValueError("未找到股票数据")
                
            except Exception as e:
                self.logger.warning(f"东方财富数据源失败: {str(e)}")
                
                # 尝试使用腾讯数据源
                df = ak.stock_zh_a_spot_qq()
                
                # 打印所有代码的前几个，用于调试
                self.logger.debug(f"腾讯数据源代码示例: {df['code'].head(10).tolist()}")
                
                # 尝试不同的代码格式
                market_code = 'sz' if market == 'SZ' else 'sh'
                stock_codes = [
                    f"{market_code}{code}",              # 原始代码
                    f"{market_code}{code.zfill(6)}",     # 补零到6位
                    f"{market_code}{code.lstrip('0')}",  # 去掉前导零
                ]
                
                for stock_code in stock_codes:
                    self.logger.debug(f"尝试匹配代码: {stock_code}")
                    filtered_df = df[df['code'] == stock_code]
                    
                    if not filtered_df.empty:
                        self.logger.info(f"成功匹配到股票代码: {stock_code}")
                        
                        # 转换数据格式
                        data = {
                            'symbol': symbol,
                            'timestamp': pd.Timestamp.now(),
                            'open': float(filtered_df['open'].iloc[0]),
                            'high': float(filtered_df['high'].iloc[0]),
                            'low': float(filtered_df['low'].iloc[0]),
                            'close': float(filtered_df['price'].iloc[0]),
                            'volume': float(filtered_df['volume'].iloc[0]),
                            'amount': float(filtered_df['amount'].iloc[0])
                        }
                        
                        self.logger.debug(
                            f"获取到实时行情:\n"
                            f"  股票: {symbol}\n"
                            f"  价格: {data['close']}\n"
                            f"  成交量: {data['volume']}"
                        )
                        
                        return data
                
                raise ValueError(f"未找到股票实时行情: {symbol}")
                
        except Exception as e:
            self.logger.error(
                f"获取实时行情失败:\n"
                f"  股票: {symbol}\n"
                f"  错误: {str(e)}\n",
                exc_info=True
            )
            
            # 返回模拟数据，避免程序崩溃
            self.logger.warning(f"使用模拟数据替代: {symbol}")
            return {
                'symbol': symbol,
                'timestamp': pd.Timestamp.now(),
                'open': 10.0,
                'high': 10.5,
                'low': 9.8,
                'close': 10.2,
                'volume': 100000.0,
                'amount': 1020000.0
            } 