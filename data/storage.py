import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import json
import os
from datetime import datetime
import sqlite3
import threading

class DataStorage:
    """数据存储基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"storage.{self.__class__.__name__}")
    
    def save(self, collection: str, data: Dict[str, Any]) -> bool:
        """保存数据
        
        Args:
            collection: 集合/表名
            data: 要保存的数据
            
        Returns:
            bool: 是否成功
        """
        raise NotImplementedError("子类必须实现save方法")
    
    def find(self, collection: str, query: Dict[str, Any], 
            limit: int = 100) -> List[Dict[str, Any]]:
        """查询数据
        
        Args:
            collection: 集合/表名
            query: 查询条件
            limit: 返回记录数量限制
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        raise NotImplementedError("子类必须实现find方法")
    
    def update(self, collection: str, query: Dict[str, Any], 
              update: Dict[str, Any]) -> int:
        """更新数据
        
        Args:
            collection: 集合/表名
            query: 查询条件
            update: 更新内容
            
        Returns:
            int: 更新的记录数
        """
        raise NotImplementedError("子类必须实现update方法")
    
    def delete(self, collection: str, query: Dict[str, Any]) -> int:
        """删除数据
        
        Args:
            collection: 集合/表名
            query: 查询条件
            
        Returns:
            int: 删除的记录数
        """
        raise NotImplementedError("子类必须实现delete方法")

class SQLiteStorage(DataStorage):
    """SQLite存储实现"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.db_path = self.config.get("db_path", "trading.db")
        self.conn = None
        self.lock = threading.RLock()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with self.lock:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # 启用外键约束
            self.conn.execute("PRAGMA foreign_keys = ON")
            # 创建基本表结构
            self._create_tables()
    
    def _create_tables(self):
        """创建表结构"""
        with self.lock:
            cursor = self.conn.cursor()
            
            # 行情数据表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data_type TEXT NOT NULL,
                price REAL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                amount REAL,
                created_at TEXT NOT NULL
            )
            ''')
            
            # 订单表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                broker_order_id TEXT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                order_type TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                status TEXT NOT NULL,
                filled_quantity INTEGER NOT NULL,
                avg_fill_price REAL,
                commission REAL,
                create_time TEXT NOT NULL,
                update_time TEXT NOT NULL,
                metadata TEXT
            )
            ''')
            
            # 策略配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT UNIQUE NOT NULL,
                config TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            ''')
            
            # 创建索引
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp 
            ON market_data (symbol, timestamp)
            ''')
            
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_orders_strategy_id 
            ON orders (strategy_id)
            ''')
            
            self.conn.commit()
    
    def save(self, collection: str, data: Dict[str, Any]) -> bool:
        """保存数据到SQLite
        
        Args:
            collection: 表名
            data: 要保存的数据
            
        Returns:
            bool: 是否成功
        """
        with self.lock:
            try:
                cursor = self.conn.cursor()
                
                # 构建INSERT语句
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                values = tuple(data.values())
                
                sql = f"INSERT INTO {collection} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                self.conn.commit()
                return True
            except Exception as e:
                self.logger.error(f"保存数据失败: {e}")
                return False
    
    def find(self, collection: str, query: Dict[str, Any], 
            limit: int = 100) -> List[Dict[str, Any]]:
        """查询SQLite数据
        
        Args:
            collection: 表名
            query: 查询条件
            limit: 返回记录数量限制
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        with self.lock:
            try:
                cursor = self.conn.cursor()
                
                # 构建WHERE子句
                where_clauses = []
                values = []
                
                for key, value in query.items():
                    where_clauses.append(f"{key} = ?")
                    values.append(value)
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                sql = f"SELECT * FROM {collection} WHERE {where_sql} LIMIT {limit}"
                cursor.execute(sql, tuple(values))
                
                # 获取列名
                columns = [desc[0] for desc in cursor.description]
                
                # 构建结果
                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    results.append(result)
                
                return results
            except Exception as e:
                self.logger.error(f"查询数据失败: {e}")
                return []
    
    def update(self, collection: str, query: Dict[str, Any], 
              update: Dict[str, Any]) -> int:
        """更新SQLite数据
        
        Args:
            collection: 表名
            query: 查询条件
            update: 更新内容
            
        Returns:
            int: 更新的记录数
        """
        with self.lock:
            try:
                cursor = self.conn.cursor()
                
                # 构建SET子句
                set_clauses = []
                set_values = []
                
                for key, value in update.items():
                    set_clauses.append(f"{key} = ?")
                    set_values.append(value)
                
                # 构建WHERE子句
                where_clauses = []
                where_values = []
                
                for key, value in query.items():
                    where_clauses.append(f"{key} = ?")
                    where_values.append(value)
                
                set_sql = ", ".join(set_clauses)
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                sql = f"UPDATE {collection} SET {set_sql} WHERE {where_sql}"
                cursor.execute(sql, tuple(set_values + where_values))
                self.conn.commit()
                
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"更新数据失败: {e}")
                return 0
    
    def delete(self, collection: str, query: Dict[str, Any]) -> int:
        """删除SQLite数据
        
        Args:
            collection: 表名
            query: 查询条件
            
        Returns:
            int: 删除的记录数
        """
        with self.lock:
            try:
                cursor = self.conn.cursor()
                
                # 构建WHERE子句
                where_clauses = []
                values = []
                
                for key, value in query.items():
                    where_clauses.append(f"{key} = ?")
                    values.append(value)
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                sql = f"DELETE FROM {collection} WHERE {where_sql}"
                cursor.execute(sql, tuple(values))
                self.conn.commit()
                
                return cursor.rowcount
            except Exception as e:
                self.logger.error(f"删除数据失败: {e}")
                return 0
    
    def get_market_data(self, symbol: str, start_time: str, 
                       end_time: str, data_type: str = 'kline') -> pd.DataFrame:
        """获取市场数据
        
        Args:
            symbol: 标的代码
            start_time: 开始时间
            end_time: 结束时间
            data_type: 数据类型
            
        Returns:
            pd.DataFrame: 市场数据
        """
        with self.lock:
            try:
                sql = '''
                SELECT * FROM market_data 
                WHERE symbol = ? AND data_type = ? 
                AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
                '''
                
                df = pd.read_sql_query(
                    sql, 
                    self.conn, 
                    params=(symbol, data_type, start_time, end_time)
                )
                
                return df
            except Exception as e:
                self.logger.error(f"获取市场数据失败: {e}")
                return pd.DataFrame()
    
    def save_order(self, order: Dict[str, Any]) -> bool:
        """保存订单
        
        Args:
            order: 订单数据
            
        Returns:
            bool: 是否成功
        """
        # 处理元数据字段
        if 'metadata' in order and isinstance(order['metadata'], dict):
            order['metadata'] = json.dumps(order['metadata'])
        
        return self.save('orders', order)
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def debug_market_data(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最新的市场数据用于调试
        
        Args:
            symbol: 标的代码
            limit: 返回的记录数量
            
        Returns:
            List[Dict[str, Any]]: 最新的市场数据记录
        """
        with self.lock:
            try:
                sql = '''
                SELECT * FROM market_data 
                WHERE symbol = ?
                AND timestamp >= datetime('now', '-1 minute')
                ORDER BY timestamp DESC
                LIMIT ?
                '''
                
                cursor = self.conn.cursor()
                cursor.execute(sql, (symbol, limit))
                
                # 获取列名
                columns = [desc[0] for desc in cursor.description]
                
                # 构建结果
                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    results.append(result)
                
                return results
            except Exception as e:
                self.logger.error(f"获取调试数据失败: {e}")
                return [] 