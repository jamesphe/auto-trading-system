"""
auto-trading-system/
├── core/
│   ├── __init__.py
│   ├── engine.py        # 规则引擎
│   ├── strategy.py      # 策略基类
│   ├── order.py         # 订单管理
│   └── risk.py          # 风控模块
├── data/
│   ├── __init__.py
│   ├── market.py        # 行情数据接口
│   └── storage.py       # 数据存储
├── gateway/
│   ├── __init__.py
│   └── broker.py        # 券商网关
├── utils/
│   ├── __init__.py
│   ├── logger.py        # 日志工具
│   └── metrics.py       # 监控指标
├── strategies/
│   ├── __init__.py
│   └── high_open.py     # 示例策略
├── tests/
│   ├── __init__.py
│   ├── test_strategy.py # 策略测试
│   └── test_engine.py   # 引擎测试
├── .env                 # 环境变量
├── requirements.txt     # 依赖列表
├── docker-compose.yml   # 开发环境配置
└── docker-compose.prod.yml # 生产环境配置
""" 