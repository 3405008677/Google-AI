"""
路由模块

提供：
1. 路由初始化
2. 中间件配置
3. API 端点定义
"""

from src.router.index import initRouter, RouterError, PUBLIC_PATHS
from src.router.health import init_health_routes

__all__ = [
    "initRouter",
    "RouterError",
    "PUBLIC_PATHS",
    "init_health_routes",
]

