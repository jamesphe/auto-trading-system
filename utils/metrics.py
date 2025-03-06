import time
import threading
from typing import Dict, Any, List
import logging
import json
import os
from datetime import datetime

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 指标存储
        self.counters = {}  # 计数器
        self.gauges = {}    # 仪表盘
        self.histograms = {}  # 直方图
        
        # 指标导出配置
        self.export_interval = self.config.get("export_interval", 60)  # 导出间隔(秒)
        self.export_path = self.config.get("export_path", "metrics")
        
        # 确保导出目录存在
        os.makedirs(self.export_path, exist_ok=True)
        
        # 启动导出线程
        self.running = True
        self.export_thread = threading.Thread(
            target=self._export_loop,
            name="MetricsExporter",
            daemon=True
        )
        self.export_thread.start()
    
    def increment(self, name: str, labels: Dict[str, str] = None, value: float = 1.0):
        """增加计数器"""
        key = self._get_key(name, labels or {})
        if key not in self.counters:
            self.counters[key] = {
                "name": name,
                "labels": labels or {},
                "value": 0.0,
                "type": "counter"
            }
        self.counters[key]["value"] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """设置仪表盘值"""
        key = self._get_key(name, labels or {})
        self.gauges[key] = {
            "name": name,
            "labels": labels or {},
            "value": value,
            "type": "gauge"
        }
    
    def observe(self, name: str, value: float, labels: Dict[str, str] = None):
        """观察直方图值"""
        key = self._get_key(name, labels or {})
        if key not in self.histograms:
            self.histograms[key] = {
                "name": name,
                "labels": labels or {},
                "values": [],
                "type": "histogram"
            }
        
        self.histograms[key]["values"].append(value)
        
        # 限制存储的值的数量
        max_values = 1000
        if len(self.histograms[key]["values"]) > max_values:
            self.histograms[key]["values"] = self.histograms[key]["values"][-max_values:]
    
    def _get_key(self, name: str, labels: Dict[str, str]) -> str:
        """获取指标键"""
        labels_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}:{labels_str}"
    
    def _calculate_histogram_stats(self, values: List[float]) -> Dict[str, float]:
        """计算直方图统计信息"""
        if not values:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0
            }
        
        sorted_values = sorted(values)
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[len(values) // 2],
            "p90": sorted_values[int(len(values) * 0.9)],
            "p95": sorted_values[int(len(values) * 0.95)],
            "p99": sorted_values[int(len(values) * 0.99)]
        }
    
    def _export_metrics(self):
        """导出指标"""
        try:
            # 创建导出目录
            os.makedirs(self.export_path, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            metrics_file = os.path.join(self.export_path, f"metrics_{timestamp}.json")
            latest_file = os.path.join(self.export_path, "metrics_latest.json")
            
            # 收集所有指标
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "counters": self.counters,
                "gauges": self.gauges,
                "histograms": {
                    name: self._calculate_histogram_stats(hist["values"])
                    for name, hist in self.histograms.items()
                }
            }
            
            # 写入新文件
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
            # 更新软链接
            try:
                # 使用相对路径创建软链接
                metrics_filename = os.path.basename(metrics_file)
                try:
                    os.remove(latest_file)  # 先尝试删除
                except FileNotFoundError:
                    pass  # 如果文件不存在就忽略
                except PermissionError:
                    self.logger.warning("无权限删除旧的软链接文件")
                    return
                
                try:
                    os.symlink(metrics_filename, latest_file)
                except OSError as e:
                    if e.errno == 17:  # 文件已存在
                        os.replace(latest_file, latest_file + '.bak')  # 备份旧文件
                        os.symlink(metrics_filename, latest_file)  # 重新创建软链接
                    else:
                        raise
            except Exception as e:
                self.logger.warning(f"创建指标软链接失败: {e}")
                
        except Exception as e:
            self.logger.error(f"导出指标失败: {e}")
    
    def _export_loop(self):
        """指标导出循环"""
        while self.running:
            try:
                self._export_metrics()
            except Exception as e:
                self.logger.error(f"导出指标失败: {e}")
            time.sleep(self.export_interval)
    
    def stop(self):
        """停止指标收集器"""
        self.running = False
        if self.export_thread:
            self.export_thread.join(timeout=1.0)
        self._export_metrics()  # 最后导出一次 

def monitor_strategy_performance():
    metrics = {
        "win_rate": wins / total_trades,
        "profit_factor": total_profit / total_loss,
        "max_drawdown": calculate_max_drawdown(),
        "sharpe_ratio": calculate_sharpe_ratio()
    }
    return metrics 