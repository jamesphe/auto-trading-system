from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class OrderModel(Base):
    """订单数据库模型"""
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    order_id = Column(String(50), unique=True)
    symbol = Column(String(20))
    price = Column(Float)
    quantity = Column(Integer)
    order_type = Column(String(20))
    strategy_id = Column(String(50))
    status = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Order {self.order_id}>" 