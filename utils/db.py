import os
import sys
import json
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from models.order import Base, OrderModel

# 从配置文件加载数据库配置
def load_config():
    config_path = os.path.join(project_root, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

config = load_config()
db_url = config.get('storage', {}).get('db_path', 'trading.db')
DATABASE_URL = f'sqlite:///{db_url}'  # 构造 SQLite URL

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.drop_all(engine)  # 删除所有现有的表
    Base.metadata.create_all(engine)  # 创建新表

@contextmanager
def get_session():
    """获取数据库会话的上下文管理器"""
    session = Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# 如果这个文件被直接运行，则初始化数据库
if __name__ == "__main__":
    init_db()
    print(f"数据库初始化完成，使用URL: {DATABASE_URL}")