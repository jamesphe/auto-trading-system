import akshare as ak
from typing import Dict, List, Any
from datetime import datetime
import time
import logging
import pandas as pd

class AKShareDataSource:
    """AKShare行情数据源"""
    
    def __init__(self):
        self.logger = logging.getLogger("data.AKShareDataSource")
        self.last_request_time = 0
        
    def get_realtime_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
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
            
            # 获取所有股票的数据
            df = ak.stock_zh_a_spot_em()
            self.last_request_time = time.time()
            
            results = []
            for symbol in symbols:
                # 移除市场后缀
                code = symbol.split('.')[0]
                
                # 获取实时行情
                df = ak.stock_zh_a_spot_em()
                
                # 检查数据是否为空
                if df.empty:
                    self.logger.error("获取行情数据为空")
                    # 使用测试数据
                    df = pd.DataFrame({
                        '代码': [code],
                        '名称': ['测试股票'],
                        '最新价': [25.0],
                        '涨跌幅': [1.5],
                        '成交量': [10000],
                        '成交额': [250000],
                        '最高': [25.5],
                        '最低': [24.5],
                        '今开': [24.8],
                        '昨收': [24.6]
                    })
                    self.logger.warning("使用测试数据替代")
                    continue
                    
                # 打印原始数据的形状
                self.logger.debug(f"获取行情数据: {len(df)} 条记录")
                                
                stock_data = df[df['代码'] == code]
                
                if stock_data.empty:
                    self.logger.warning(f"未找到股票行情数据: {symbol}")
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
                
                # 避免请求过于频繁
                time.sleep(0.5)
                
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