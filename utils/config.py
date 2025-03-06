import os
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def load_stock_configs(config_dir: str) -> Dict[str, Any]:
    """加载股票配置文件
    
    Args:
        config_dir: 配置文件目录
        
    Returns:
        Dict[str, Any]: 股票配置字典
    """
    stock_configs = {}
    
    try:
        # 确保目录存在
        if not os.path.exists(config_dir):
            logger.error(f"股票配置目录不存在: {config_dir}")
            return {}
            
        # 遍历目录下的所有.json文件
        for filename in os.listdir(config_dir):
            if not filename.endswith('.json'):
                continue
                
            symbol = filename[:-5]  # 移除.json后缀
            file_path = os.path.join(config_dir, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    stock_config = json.load(f)
                    stock_configs[symbol] = stock_config
                    logger.info(f"加载股票配置: {symbol}")
                    
            except Exception as e:
                logger.error(f"加载股票配置文件失败 {file_path}: {str(e)}")
                continue
                
        return stock_configs
        
    except Exception as e:
        logger.error(f"加载股票配置目录失败: {str(e)}")
        return {}

def get_symbols_from_config(config: Dict[str, Any]) -> List[str]:
    """从配置中获取股票代码列表"""
    stocks_config_dir = config.get("strategy", {}).get("stocks_config_dir")
    if not stocks_config_dir:
        return []
        
    stock_configs = load_stock_configs(stocks_config_dir)
    return list(stock_configs.keys()) 