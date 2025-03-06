def test_high_open_strategy():
    # 初始化策略
    config = {
        "symbols": ["600580.SH"],
        "threshold": 0.02,
        "profit_target": 0.05,
        "stop_loss": 0.02
    }
    strategy = HighOpenStrategy(config)
    
    # 模拟开盘K线数据
    kline_data = {
        "symbol": "600580.SH",
        "timestamp": "2025-03-02T09:30:00",
        "open": 25.0,
        "high": 25.5,
        "low": 24.8,
        "close": 25.2,
        "volume": 50000,
        "data_type": "kline"
    }
    
    # 测试策略反应
    strategy.on_kline(kline_data)
    
    # 验证结果
    assert len(strategy.positions) == 1 