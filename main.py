import os.path
import argparse
import logging
import json
import time
import signal
import threading
import os
import sys
from datetime import datetime

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from simulate_market import MarketSimulator, prices  # 导入 MarketSimulator 类和 prices 字典
from utils.logger import setup_logger
from core.engine import RuleEngine
from core.risk import RiskManager
from data.storage import SQLiteStorage
from strategies.high_open import HighOpenStrategy
from data.market import MarketDataClient
from utils.config import load_stock_configs
from gateway.broker import TradeGateway, SimulatedTradeGateway
from strategies.auto_trade import AutoTradeStrategy

logger = logging.getLogger("main")

def load_config():
    config = {}
    stocks_config = {}
    
    # 加载股票配置
    stocks_dir = "config/stocks"
    for file in os.listdir(stocks_dir):
        if file.endswith(".json"):
            symbol = file.replace(".json", "")
            with open(os.path.join(stocks_dir, file)) as f:
                stock_config = json.load(f)
                stocks_config[symbol] = stock_config
    
    # 添加基本配置
    config["stocks"] = stocks_config
    config["symbols"] = list(stocks_config.keys())
    
    # 添加市场数据配置
    config["market_data"] = {
        "data_source": "akshare",
        "stocks_config_dir": "config/stocks",
        "update_interval": 30,
        "debug_mode": True,
        "use_real_data": True,
        "symbols": list(stocks_config.keys()),
        "rate_limit": {
            "enabled": True,
            "requests_per_minute": 2
        },
        "storage": {
            "db_path": "trading.db",
            "save_market_data": True,
            "save_interval": 60
        }
    }
    
    # 添加策略配置
    config["strategy"] = {
        "stocks": stocks_config,
        "high_open": {
            "enabled": True
        }
    }
    
    # 添加风控配置
    config["risk"] = {
        "max_position_value": 1000000,  # 最大持仓市值
        "max_order_value": 100000,      # 最大单笔交易额
        "min_order_interval": 3         # 最小下单间隔(秒)
    }
    
    # 添加存储配置
    config["storage"] = {
        "db_path": "trading.db",
        "save_market_data": True,
        "save_interval": 60
    }
    
    return config

def signal_handler(signum, frame):
    """信号处理函数
    
    Args:
        signum: 信号编号
        frame: 当前栈帧
    """
    global running
    running = False
    logger.info(f"接收到信号 {signum}，准备退出...")

def setup_logging(verbose: bool):
    """设置日志配置"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 确保关键模块的日志级别正确设置
    logging.getLogger("engine").setLevel(log_level)
    logging.getLogger("strategy").setLevel(log_level)
    logging.getLogger("market").setLevel(log_level)

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="自动化交易系统")
    parser.add_argument("-c", "--config", default="config.json", help="配置文件路径")
    parser.add_argument("-m", "--mode", default="backtest", choices=["live", "paper", "backtest"], help="交易模式")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.verbose)
    # 获取logger实例
    logger = logging.getLogger("main")
    
    # 加载配置
    config = load_config()
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化运行状态
    global running
    running = True
    
    # 创建市场数据客户端
    market_config = config["market_data"].copy()
    market_config["use_real_data"] = True
    market_config["data_source"] = "akshare"
    market_config["mode"] = args.mode
    
    market_client = MarketDataClient(market_config)
    
    # 创建交易网关并设置market_client
    gateway = SimulatedTradeGateway(config.get("trade", {}))
    gateway.set_market_client(market_client)
    
    # 创建规则引擎，传入交易网关
    engine = RuleEngine(gateway=gateway)
    
    # 创建风控管理器
    risk_manager = RiskManager(config.get("risk", {}))
    engine.set_risk_manager(risk_manager)
    
    # 如果是live模式，添加调试代码
    if args.mode == "live":
        run_flag = {"running": True}  # 使用字典来共享状态
        def debug_market_data():
            while run_flag["running"]:
                for symbol in config["market_data"]["symbols"]:
                    # 直接打印基本信息
                    logger.info(f"\n监控股票: {symbol}")
                    time.sleep(config["market_data"]["update_interval"])
        
        # 启动调试线程
        debug_thread = threading.Thread(
            target=debug_market_data,
            name="MarketDataDebug",
            daemon=True
        )
        debug_thread.start()
        logger.info("启动行情数据调试线程")
    
    # 如果是回测模式，添加调试代码
    if args.mode == "backtest":
        run_flag = {"running": True}  # 使用字典来共享状态
        
        def debug_backtest():
            """回测调试函数"""
            while run_flag["running"]:
                # 获取最新持仓
                for strategy_id, strategy in engine.strategies.items():
                    positions = strategy.positions
                    if positions:
                        logger.info(f"\n{'='*50}")
                        logger.info(f"策略 {strategy_id} 当前持仓:")
                        logger.info(f"{'-'*30}")
                        for symbol, pos in positions.items():
                            profit = (prices[symbol] - pos.avg_price) * pos.volume
                            profit_rate = (prices[symbol]/pos.avg_price - 1) * 100
                            logger.info(
                                f"股票代码: {symbol}\n"
                                f"持仓数量: {pos.volume:,d}\n"
                                f"持仓均价: {pos.avg_price:>10.2f}\n"
                                f"当前价格: {prices[symbol]:>10.2f}\n"
                                f"浮动盈亏: {profit:>10.2f} ({profit_rate:>6.2f}%)"
                            )
                        logger.info(f"{'='*50}\n")
                
                # 获取最新订单
                active_orders = engine.order_manager.get_active_orders()
                if active_orders:
                    logger.info(f"\n{'='*50}")
                    logger.info("活跃订单列表:")
                    logger.info(f"{'-'*30}")
                    for order in active_orders:
                        logger.info(
                            f"订单编号: {order.order_id}\n"
                            f"交易股票: {order.symbol}\n"
                            f"交易方向: {order.direction}\n"
                            f"委托价格: {order.price:>10.2f}\n"
                            f"委托数量: {order.quantity:>10,d}\n"
                            f"订单状态: {order.status}"
                        )
                    logger.info(f"{'-'*30}")
                    logger.info(f"{'='*50}\n")
                
                # 获取账户信息
                account = engine.trade_gateway.get_account()
                balance = account.get('balance', 0)
                positions = engine.trade_gateway.get_positions()
                positions_value = sum(
                    pos.get('quantity', 0) * prices.get(symbol, 0)
                    for symbol, pos in positions.items()
                )
                total_assets = balance + positions_value
                
                logger.info(f"\n{'='*50}")
                logger.info("账户资金状况:")
                logger.info(f"{'-'*30}")
                logger.info(
                    f"可用资金: {balance:>15,.2f}\n"
                    f"持仓市值: {positions_value:>15,.2f}\n"
                    f"总资产值: {total_assets:>15,.2f}"
                )
                logger.info(f"{'='*50}\n")
                
                time.sleep(5)  # 每5秒更新一次
        
        # 启动回测调试线程
        debug_thread = threading.Thread(
            target=debug_backtest,
            name="BacktestDebug",
            daemon=True
        )
        debug_thread.start()
        logger.info("启动回测调试线程")
    
    # 初始化策略
    for symbol, stock_config in config["stocks"].items():
        logger.debug(f"检查股票 {symbol} 的策略配置")
        
        # 注册高开策略
        if stock_config.get("high_open", {}).get("enabled", False):
            logger.debug(f"股票 {symbol} 启用了高开策略")
            strategy_config = {
                "type": "HighOpen",
                "symbols": [symbol],
                "stocks": config["stocks"],
                "threshold": stock_config["high_open"]["price_threshold"],
                "profit_target": stock_config["high_open"]["profit_target"],
                "stop_loss": stock_config["high_open"]["stop_loss"],
                "enabled": True,
                "price_threshold": stock_config["high_open"]["price_threshold"],
                "high_open_ratio": stock_config["high_open"]["high_open_ratio"],
                "volume_check_window": stock_config["high_open"]["volume_check_window"],
                "sell_ratios": stock_config["high_open"]["sell_ratios"],
                "price_offsets": stock_config["high_open"]["price_offsets"]
            }
            strategy = HighOpenStrategy(strategy_config)
            strategy_id = f"high_open_{symbol}"
            engine.register_strategy(strategy_id, strategy)
            logger.info(
                f"注册策略: {strategy_id}\n"
                f"  类型: {strategy_config['type']}\n"
                f"  股票: {symbol}\n"
                f"  参数: threshold={strategy_config['threshold']}, "
                f"profit_target={strategy_config['profit_target']}, "
                f"stop_loss={strategy_config['stop_loss']}"
            )
        
        # 添加自动交易策略注册
        if stock_config.get("strategies", {}).get("auto_trade", {}).get("enabled", False):
            logger.debug(f"股票 {symbol} 启用了自动交易策略")
            strategy_config = {
                "type": "AutoTrade",
                "symbols": [symbol],
                "stocks": config["stocks"],
                "auto_trade": stock_config["strategies"]["auto_trade"]
            }
            strategy = AutoTradeStrategy(strategy_config, broker=gateway)
            strategy_id = f"auto_trade_{symbol}"
            engine.register_strategy(strategy_id, strategy)
            logger.info(
                f"注册策略: {strategy_id}\n"
                f"  类型: {strategy_config['type']}\n"
                f"  股票: {symbol}"
            )
    
    # 在启动引擎之前添加检查
    logger.debug(f"启动引擎前注册的策略数量: {len(engine.strategies)}")
    engine.start()
    logger.info("启动交易引擎")
    
    # 根据配置决定是否需要市场模拟器
    should_simulate = (
        args.mode in ["backtest", "paper"] or
        config["market_data"].get("data_source") != "akshare" or
        not config["market_data"].get("use_real_data", True)
    )

    if should_simulate:
        # 创建并启动市场模拟器
        simulator = MarketSimulator(config, engine)
        simulator.start()
        logger.info("启动市场模拟器")
    else:
        # 使用真实市场数据
        try:
            market_config = config["market_data"].copy()
            market_config["use_real_data"] = True
            market_config["data_source"] = "akshare"
            market_config["mode"] = args.mode
            
            market_client = MarketDataClient(market_config)
            
            # 定义市场数据处理函数
            def handle_market_data(data):
                """处理市场数据的回调函数"""
                data_type = data.get('data_type', 'market_data')
                # 添加调试日志
                logger.debug(f"处理市场数据: type={data_type}, data={data}")
                engine.on_market_data(data_type, data)
            
            # 开始订阅行情
            market_client.subscribe(
                symbols=config["market_data"]["symbols"],
                handlers={
                    'market_data': handle_market_data,
                    'kline': handle_market_data,
                    'tick': handle_market_data
                }
            )
            logger.info("开始接收实时行情数据")
        except Exception as e:
            logger.error(f"初始化市场数据客户端失败: {str(e)}")
            logger.error("live模式下无法回退到模拟器模式，程序退出")
            sys.exit(1)
    
    # 主循环
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号,准备退出...")
        if args.mode in ["live", "backtest"]:
            run_flag["running"] = False
    finally:
        # 停止交易系统
        engine.stop()
        logger.info("模拟结束")

if __name__ == "__main__":
    main() 