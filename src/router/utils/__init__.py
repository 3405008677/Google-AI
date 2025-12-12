"""
路由工具模块

提供：
1. 核心异常处理
2. 中间件
"""

from src.router.utils.core.exceptions import RouterError, register_router_exception_handlers
from src.router.utils.middlewares.auth import AuthMiddleware, register_router_auth_middleware
from src.router.utils.middlewares.rate_limit import RateLimitMiddleware, register_router_rate_limit_middleware
from src.router.utils.middlewares.tracing import RouterTracingMiddleware, register_router_tracing_middleware

__all__ = [
    # 异常
    "RouterError",
    "register_router_exception_handlers",
    
    # 中间件
    "AuthMiddleware",
    "register_router_auth_middleware",
    "RateLimitMiddleware",
    "register_router_rate_limit_middleware",
    "RouterTracingMiddleware",
    "register_router_tracing_middleware",
]

