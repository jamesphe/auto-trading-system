# 自动化交易系统开发文档

[![GitHub Release](https://img.shields.io/github/v/release/yourorg/auto-trading-system)](https://github.com/yourorg/auto-trading-system)
[![CI/CD Status](https://github.com/yourorg/auto-trading-system/actions/workflows/build.yml/badge.svg)](https://github.com/yourorg/auto-trading-system/actions)
[![Code Coverage](https://codecov.io/gh/yourorg/auto-trading-system/branch/main/graph/badge.svg)](https://codecov.io/gh/yourorg/auto-trading-system)

## 1. 架构设计
### 1.1 系统拓扑
```mermaid
flowchart TB
    subgraph 数据层
        A[(行情数据库)] -->|实时推送| B[规则引擎]
        C[(交易记录库)] -->|持久化| D[风控模块]
    end
    
    subgraph 核心层
        B -->|事件触发| E[策略执行器]
        E -->|指令传递| F[订单管理器]
    end
    
    subgraph 接口层
        F -->|协议转换| G[券商网关]
        H[行情接收器] -->|数据清洗| A
    end
```

### 1.2 技术栈
| 组件     | 技术选型             | 版本要求   |
| -------- | -------------------- | ---------- |
| 规则引擎 | durable-rules        | ≥3.0.0     |
| 数据存储 | PostgreSQL + Redis   | PG14+/6.2+ |
| 消息队列 | RabbitMQ             | 3.11+      |
| 监控系统 | Prometheus + Grafana | 2.40+/9.3+ |

## 2. 环境配置
### 2.1 开发环境
```bash
# 使用conda创建虚拟环境
conda create -n trading python=3.10
conda activate trading

# 安装核心依赖
pip install -r requirements.txt

# 配置本地环境变量
echo "TRADE_MODE=SANDBOX" > .env
echo "DB_URL=postgresql://user:pass@localhost:5432/trading" >> .env
```

### 2.2 生产部署
```yaml
# docker-compose.prod.yml
services:
  engine:
    image: trading-engine:v1.2
    environment:
      - RULE_WORKERS=8
      - MAX_ORDERS_PER_SEC=50
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

## 3. API规范
### 3.1 行情接口
```python
class MarketDataClient:
    def subscribe(self, symbols: list[str], handlers: dict):
        """
        实时行情订阅接口
        
        :param symbols: 标的代码列表 ['000001.SZ', '600000.SH']
        :param handlers: 事件处理器字典 {
            'tick': on_tick_event,
            'kline': on_kline_event
        }
        """

    def get_history(self, symbol: str, 
                   start: datetime, 
                   end: datetime, 
                   timeframe: str) -> pd.DataFrame:
        """
        获取历史K线数据
        返回字段包括 [timestamp, open, high, low, close, volume]
        """
```

### 3.2 交易接口
```python
class TradeGateway:
    class OrderStatus(Enum):
        PENDING = 1
        PARTIAL_FILLED = 2
        COMPLETED = 3
        CANCELLED = 4

    def place_order(self, order: Order) -> str:
        """
        下单接口
        
        :param order: Order对象包含
            - symbol: 标的代码
            - price: 委托价格
            - quantity: 委托数量
            - order_type: 订单类型 (LIMIT/MARKET)
        :return: 交易所订单ID
        """
```

## 4. 策略开发
### 4.1 决策图语法
```mermaid
graph TD
    A[[策略入口]] --> B{条件判断}
    B -->|满足| C[执行动作]
    B -->|不满足| D[备选路径]
    
    style A fill:#4CAF50,stroke:#388E3C
    style B fill:#2196F3,stroke:#1976D2
    style C fill:#FF9800,stroke:#F57C00
```

### 4.2 策略模板
```python
from core.strategy import BaseStrategy

class CustomStrategy(BaseStrategy):
    def initialize(self):
        self.register_event('开盘事件', self.on_market_open)
        
    def on_market_open(self, event):
        if event.open_price > self.config['threshold']:
            self.place_order(...)
            
    def on_order_update(self, order):
        if order.status == OrderStatus.FILLED:
            self.logger.info(f"订单完成: {order}")
```

## 5. 测试验证
### 5.1 单元测试
```python
def test_high_open_strategy():
    # 模拟高开场景
    simulator = BacktestEngine()
    simulator.feed_data({
        'open_price': 75.0,
        'volume': 500000
    })
    
    strategy = HighOpenStrategy(config={'threshold': 74.5})
    result = simulator.run(strategy)
    
    assert result.orders.count == 1
    assert result.profit > 0
```

### 5.2 回测报告
| 指标     | 说明             | 合格标准 |
| -------- | ---------------- | -------- |
| 最大回撤 | 历史最大亏损幅度 | <20%     |
| 夏普比率 | 风险调整后收益   | >1.5     |
| 胜率     | 盈利交易占比     | >55%     |

## 6. 运维监控
### 6.1 监控指标
```prometheus
# HELP rule_trigger_total Total triggered rules
# TYPE rule_trigger_total counter
rule_trigger_total{strategy="high_open"} 23

# HELP order_latency_seconds Order processing latency
# TYPE order_latency_seconds histogram
order_latency_seconds_bucket{le="0.1"} 12
```

### 6.2 告警规则
```yaml
alerting:
  rules:
    - alert: HighOrderLatency
      expr: order_latency_seconds{quantile="0.9"} > 0.5
      for: 5m
      labels:
        severity: critical
```

## 7. 附录
### 7.1 术语表
| 术语     | 定义                       |
| -------- | -------------------------- |
| 滑点     | 预期价格与实际成交价的差异 |
| 篮子订单 | 批量执行的一组关联订单     |
| 策略穿透 | 策略在历史数据上的模拟执行 |

