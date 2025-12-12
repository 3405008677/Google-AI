"""
路由模块主入口文件

此模块负责：
1. 定义主路由器和基础 API 端点
2. 注册所有子路由模块
3. 提供统一的 API 前缀管理
4. 配置中间件（按正确顺序注册）

中间件执行顺序说明：
- FastAPI 中间件按注册的逆序执行（后注册的先执行）
- 推荐顺序：限流 -> 认证 -> 追踪（最先注册的最后执行）
- 这样限流会最先拦截，避免消耗认证资源
"""

from typing import List, Optional
from fastapi import APIRouter
from src.router.utils.core.exceptions import RouterError, register_router_exception_handlers
from src.router.utils.middlewares.tracing import register_router_tracing_middleware
from src.router.utils.middlewares.auth import register_router_auth_middleware
from src.router.utils.middlewares.rate_limit import register_router_rate_limit_middleware
from src.router.agents.AI.Customize.index import initCustomize
from src.router.agents.AI.Qwen.index import initQwen
from src.router.agents.AI.Gemini.index import initGemini
from src.router.health import init_health_routes
from src.router.services.authorization.index import register_authorization_routes
from src.server.logging_setup import logger


# 创建主路由器实例
router = APIRouter()

# 需要跳过认证和限流的公共路径
PUBLIC_PATHS: List[str] = [
    "/health",
    "/ready",
    "/status",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    # 授权相关端点（登录、刷新、验证不需要认证）
    "/auth/login",
    "/auth/refresh",
    "/auth/validate",
]

# 定义模块的公共接口
__all__ = ["initRouter", "RouterError", "PUBLIC_PATHS"]


def initRouter(
    app,
    skip_auth_paths: Optional[List[str]] = None,
    skip_rate_limit_paths: Optional[List[str]] = None,
    require_auth: bool = True,
    enable_rate_limit: bool = True,
    requests_per_minute: int = 60,
    requests_per_second: int = 10,
):
    """
    初始化路由系统

    注册顺序很重要！FastAPI 中间件按注册的逆序执行：
    1. 先注册追踪中间件（最后执行，记录完整请求信息）
    2. 再注册认证中间件（在追踪之前执行）
    3. 最后注册限流中间件（最先执行，快速拦截恶意请求）

    Args:
        app: FastAPI 应用实例
        skip_auth_paths: 跳过认证的路径列表
        skip_rate_limit_paths: 跳过限流的路径列表
        require_auth: 是否要求认证
        enable_rate_limit: 是否启用限流
        requests_per_minute: 每分钟最大请求数
        requests_per_second: 每秒最大请求数
    """
    # 合并默认跳过路径
    auth_skip = list(set(PUBLIC_PATHS + (skip_auth_paths or [])))
    rate_limit_skip = list(set(PUBLIC_PATHS + (skip_rate_limit_paths or [])))

    # === 步骤 1: 注册中间件（按执行顺序的逆序注册）===

    # 1.1 追踪中间件（最后执行，记录完整请求周期）
    register_router_tracing_middleware(
        app,
        skip_paths=["/health", "/ready"],  # 健康检查不需要追踪
        enable_trace_id=True,
    )
    logger.info("✓ 已注册追踪中间件")

    # 1.2 认证中间件
    register_router_auth_middleware(
        app,
        skip_paths=auth_skip,
        require_auth=require_auth,
    )
    logger.info(f"✓ 已注册认证中间件 (require_auth={require_auth})")

    # 1.3 限流中间件（最先执行，快速拦截）
    register_router_rate_limit_middleware(
        app,
        requests_per_minute=requests_per_minute,
        requests_per_second=requests_per_second,
        skip_paths=rate_limit_skip,
        enable_rate_limit=enable_rate_limit,
    )
    logger.info(
        f"✓ 已注册限流中间件 (enable={enable_rate_limit}, rpm={requests_per_minute}, rps={requests_per_second})"
    )

    # === 步骤 2: 注册异常处理器 ===
    register_router_exception_handlers(app)  # 注册到 FastAPI 应用，不是路由器
    logger.info("✓ 已注册异常处理器")

    # === 步骤 3: 注册健康检查路由（优先级最高）===
    init_health_routes(app)
    logger.info("✓ 已注册健康检查路由")

    # === 步骤 4: 注册主路由 ===
    app.include_router(router)

    # === 步骤 5: 注册 AI 模型路由 ===
    initCustomize(app, prefix="/Customize")
    initQwen(app, prefix="/Qwen")
    initGemini(app, prefix="/Gemini")

    # === 步骤 5.5: 注册授权服务路由 ===
    register_authorization_routes(app, prefix="/auth")

    # === 步骤 6: 注册 Agent 路由 ===
    try:
        from src.router.agents.api import register_agent_routes

        register_agent_routes(app, prefix="")
        logger.info("✓ 已注册 Agent 路由")
    except Exception as e:
        logger.warning(f"Agent 路由注册失败: {e}")

    logger.info("✓ 路由系统初始化完成")
