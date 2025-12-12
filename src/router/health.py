"""
健康检查路由模块

提供：
1. /health - 基础健康检查（liveness probe）
2. /ready - 就绪检查（readiness probe）
3. /status - 详细状态信息

符合 Kubernetes 健康检查最佳实践。
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Response, status

from src.server.logging_setup import logger

# 创建路由器
router = APIRouter(tags=["Health"])

# 启动时间记录
_start_time = time.time()


def _get_uptime() -> str:
    """获取服务运行时间"""
    uptime_seconds = int(time.time() - _start_time)
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)


def _check_redis() -> Dict[str, Any]:
    """检查 Redis 连接"""
    try:
        from src.router.agents.performance_layer import get_performance_layer
        layer = get_performance_layer()
        if layer.semantic_cache and layer.semantic_cache.redis_client:
            layer.semantic_cache.redis_client.ping()
            return {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
    return {"status": "not_configured"}


def _check_workers() -> Dict[str, Any]:
    """检查 Worker 注册状态"""
    try:
        from src.router.agents.supervisor import get_registry
        registry = get_registry()
        return {
            "status": "healthy" if not registry.is_empty() else "no_workers",
            "count": registry.count(),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.get("/health")
async def health_check():
    """
    基础健康检查（Liveness Probe）
    
    只检查服务是否存活，不检查依赖服务。
    适用于 Kubernetes liveness probe。
    
    Returns:
        200: 服务存活
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check(response: Response):
    """
    就绪检查（Readiness Probe）
    
    检查服务是否准备好接收流量。
    如果关键依赖不可用，返回 503。
    
    Returns:
        200: 服务就绪
        503: 服务未就绪
    """
    checks = {
        "workers": _check_workers(),
    }
    
    # 判断是否就绪
    is_ready = all(
        check.get("status") in ("healthy", "not_configured", "no_workers")
        for check in checks.values()
    )
    
    result = {
        "status": "ready" if is_ready else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return result


@router.get("/status")
async def status_check():
    """
    详细状态信息
    
    返回服务的详细状态，包括：
    - 运行时间
    - 依赖服务状态
    - Worker 信息
    - 配置信息
    
    Returns:
        服务详细状态
    """
    from src.config import get_config
    
    config = get_config()
    
    return {
        "status": "running",
        "version": "1.0.0",
        "uptime": _get_uptime(),
        "environment": {
            "debug": config.debug,
            "router_enabled": config.enable_router,
            "ssl_enabled": config.ssl_enabled,
        },
        "dependencies": {
            "redis": _check_redis(),
            "workers": _check_workers(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
async def metrics_endpoint():
    """
    性能指标端点
    
    返回服务的性能指标，包括：
    - 请求统计（计数、延迟、成功率）
    - Worker 执行指标
    - 缓存命中率
    - Supervisor 运行指标
    
    Returns:
        性能指标数据
    """
    from src.core.metrics import get_metrics_collector
    
    collector = get_metrics_collector()
    return collector.get_metrics()


def init_health_routes(app, prefix: str = ""):
    """
    注册健康检查路由
    
    Args:
        app: FastAPI 应用实例
        prefix: 路由前缀
    """
    app.include_router(router, prefix=prefix)
    logger.info(f"已注册健康检查路由，前缀: {prefix or '/'}")


__all__ = ["router", "init_health_routes"]

