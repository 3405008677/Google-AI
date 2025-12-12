"""
性能指标收集模块

提供：
1. 请求计数器
2. 响应时间统计
3. 错误率统计
4. Worker 执行指标
5. 缓存命中率统计

注意：这是一个轻量级的内存指标收集器。
对于生产环境，建议集成 Prometheus 或其他专业监控系统。
"""

import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from contextlib import contextmanager


@dataclass
class LatencyStats:
    """延迟统计"""
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    
    def record(self, latency_ms: float) -> None:
        """记录一次延迟"""
        self.count += 1
        self.total_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)
    
    @property
    def avg_ms(self) -> float:
        """平均延迟"""
        return self.total_ms / self.count if self.count > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "count": self.count,
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float('inf') else 0,
            "max_ms": round(self.max_ms, 2),
        }


@dataclass
class CounterStats:
    """计数器统计"""
    total: int = 0
    success: int = 0
    failure: int = 0
    
    def record_success(self) -> None:
        """记录成功"""
        self.total += 1
        self.success += 1
    
    def record_failure(self) -> None:
        """记录失败"""
        self.total += 1
        self.failure += 1
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.success / self.total if self.total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total": self.total,
            "success": self.success,
            "failure": self.failure,
            "success_rate": round(self.success_rate * 100, 2),
        }


class MetricsCollector:
    """
    指标收集器
    
    线程安全的指标收集器，支持：
    - 请求计数
    - 响应延迟
    - 错误率
    - Worker 执行指标
    - 缓存命中率
    """
    
    _instance: Optional['MetricsCollector'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._lock = threading.Lock()
        
        # 请求指标
        self._request_counter = CounterStats()
        self._request_latency: Dict[str, LatencyStats] = defaultdict(LatencyStats)
        
        # Worker 指标
        self._worker_counter: Dict[str, CounterStats] = defaultdict(CounterStats)
        self._worker_latency: Dict[str, LatencyStats] = defaultdict(LatencyStats)
        
        # 缓存指标
        self._cache_hits = 0
        self._cache_misses = 0
        self._rule_engine_hits = 0
        
        # Supervisor 指标
        self._supervisor_iterations: List[int] = []
        self._task_plan_sizes: List[int] = []
        
        # 启动时间
        self._start_time = time.time()
        
        self._initialized = True
    
    # === 请求指标 ===
    
    def record_request(
        self,
        path: str,
        method: str,
        latency_ms: float,
        status_code: int,
    ) -> None:
        """
        记录请求指标
        
        Args:
            path: 请求路径
            method: HTTP 方法
            latency_ms: 延迟（毫秒）
            status_code: 响应状态码
        """
        with self._lock:
            # 计数
            if 200 <= status_code < 400:
                self._request_counter.record_success()
            else:
                self._request_counter.record_failure()
            
            # 延迟（按路径分组）
            key = f"{method} {path}"
            self._request_latency[key].record(latency_ms)
    
    @contextmanager
    def measure_request(self, path: str, method: str):
        """
        请求计时上下文管理器
        
        Usage:
            with metrics.measure_request("/api/chat", "POST") as measure:
                # 处理请求
                pass
            # measure.record(status_code) 会自动调用
        """
        start = time.perf_counter()
        result = {"status_code": 200}
        
        try:
            yield result
        except Exception:
            result["status_code"] = 500
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            self.record_request(path, method, latency_ms, result["status_code"])
    
    # === Worker 指标 ===
    
    def record_worker_execution(
        self,
        worker_name: str,
        latency_ms: float,
        success: bool,
    ) -> None:
        """
        记录 Worker 执行指标
        
        Args:
            worker_name: Worker 名称
            latency_ms: 执行时间（毫秒）
            success: 是否成功
        """
        with self._lock:
            if success:
                self._worker_counter[worker_name].record_success()
            else:
                self._worker_counter[worker_name].record_failure()
            
            self._worker_latency[worker_name].record(latency_ms)
    
    @contextmanager
    def measure_worker(self, worker_name: str):
        """
        Worker 计时上下文管理器
        """
        start = time.perf_counter()
        success = True
        
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            self.record_worker_execution(worker_name, latency_ms, success)
    
    # === 缓存指标 ===
    
    def record_cache_hit(self) -> None:
        """记录缓存命中"""
        with self._lock:
            self._cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """记录缓存未命中"""
        with self._lock:
            self._cache_misses += 1
    
    def record_rule_engine_hit(self) -> None:
        """记录规则引擎命中"""
        with self._lock:
            self._rule_engine_hits += 1
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self._cache_hits + self._cache_misses
        return self._cache_hits / total if total > 0 else 0.0
    
    # === Supervisor 指标 ===
    
    def record_supervisor_run(self, iterations: int, task_plan_size: int) -> None:
        """
        记录 Supervisor 运行指标
        
        Args:
            iterations: 迭代次数
            task_plan_size: 任务计划大小
        """
        with self._lock:
            self._supervisor_iterations.append(iterations)
            self._task_plan_sizes.append(task_plan_size)
            
            # 只保留最近 1000 条记录
            if len(self._supervisor_iterations) > 1000:
                self._supervisor_iterations = self._supervisor_iterations[-1000:]
                self._task_plan_sizes = self._task_plan_sizes[-1000:]
    
    # === 汇总 ===
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取所有指标
        
        Returns:
            指标字典
        """
        with self._lock:
            uptime_seconds = int(time.time() - self._start_time)
            
            # 计算 Supervisor 平均值
            avg_iterations = (
                sum(self._supervisor_iterations) / len(self._supervisor_iterations)
                if self._supervisor_iterations else 0
            )
            avg_task_plan_size = (
                sum(self._task_plan_sizes) / len(self._task_plan_sizes)
                if self._task_plan_sizes else 0
            )
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": uptime_seconds,
                
                "requests": {
                    "summary": self._request_counter.to_dict(),
                    "latency_by_endpoint": {
                        k: v.to_dict() for k, v in self._request_latency.items()
                    },
                },
                
                "workers": {
                    name: {
                        "counter": self._worker_counter[name].to_dict(),
                        "latency": self._worker_latency[name].to_dict(),
                    }
                    for name in set(self._worker_counter.keys()) | set(self._worker_latency.keys())
                },
                
                "cache": {
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "hit_rate": round(self.cache_hit_rate * 100, 2),
                    "rule_engine_hits": self._rule_engine_hits,
                },
                
                "supervisor": {
                    "runs": len(self._supervisor_iterations),
                    "avg_iterations": round(avg_iterations, 2),
                    "avg_task_plan_size": round(avg_task_plan_size, 2),
                },
            }
    
    def reset(self) -> None:
        """重置所有指标"""
        with self._lock:
            self._request_counter = CounterStats()
            self._request_latency.clear()
            self._worker_counter.clear()
            self._worker_latency.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            self._rule_engine_hits = 0
            self._supervisor_iterations.clear()
            self._task_plan_sizes.clear()


# 全局指标收集器实例
metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    return metrics


__all__ = [
    "MetricsCollector",
    "metrics",
    "get_metrics_collector",
    "LatencyStats",
    "CounterStats",
]

