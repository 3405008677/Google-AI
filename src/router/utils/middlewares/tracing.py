"""路由层日志与追踪中间件，专门处理路由相关的请求追踪和日志记录。"""

import time
import uuid
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.server.logging_setup import logger


class RouterTracingMiddleware(BaseHTTPMiddleware):
    """
    路由层追踪中间件

    专门用于路由层的请求追踪和日志记录，提供：
    1. 自动生成或使用请求追踪ID
    2. 记录路由层特定的请求信息（路由路径、参数等）
    3. 追踪请求在路由层的处理时间
    4. 记录路由层的性能指标和上下文信息
    """

    def __init__(self, app, skip_paths: Optional[list] = None, enable_trace_id: bool = True):
        """
        初始化路由追踪中间件

        Args:
            app: FastAPI 应用实例
            skip_paths: 需要跳过追踪的路径列表（如健康检查接口）
            enable_trace_id: 是否自动生成追踪ID（如果请求头中没有）
        """
        super().__init__(app)
        self.skip_paths = skip_paths or []
        self.enable_trace_id = enable_trace_id

    def _generate_trace_id(self) -> str:
        """生成唯一的追踪ID"""
        return str(uuid.uuid4())

    def _get_trace_id(self, request: Request) -> str:
        """获取或生成请求追踪ID"""
        # 优先使用请求头中的追踪ID
        trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")

        if not trace_id and self.enable_trace_id:
            trace_id = self._generate_trace_id()

        return trace_id or "unknown"

    def _extract_route_info(self, request: Request) -> Dict[str, Any]:
        """提取路由相关信息"""
        route_info = {
            "path": str(request.url.path),
            "method": request.method,
            "query_params": dict(request.query_params) if request.query_params else {},
        }

        # 如果路由已解析，添加路由名称和路径参数
        if hasattr(request, "scope") and "route" in request.scope:
            route = request.scope.get("route")
            if route:
                route_info["route_name"] = getattr(route, "name", None)
                route_info["route_path"] = getattr(route, "path", None)

        # 添加路径参数（如果存在）
        if hasattr(request, "path_params"):
            route_info["path_params"] = request.path_params

        return route_info

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并记录追踪信息"""
        # 跳过指定路径的追踪
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # 获取或生成追踪ID
        trace_id = self._get_trace_id(request)

        # 将追踪ID添加到请求状态中，供后续处理使用
        request.state.trace_id = trace_id

        # 提取路由信息
        route_info = self._extract_route_info(request)

        # 获取客户端信息
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # 记录路由请求开始
        logger.info(
            "路由请求开始 | TraceID: %s | 路径: %s | 方法: %s | 客户端: %s | 路由: %s | 查询参数: %s",
            trace_id,
            route_info["path"],
            route_info["method"],
            client_ip,
            route_info.get("route_name", "unknown"),
            route_info.get("query_params", {}),
        )

        start_time = time.perf_counter()

        try:
            # 处理请求
            response = await call_next(request)

            # 计算路由层处理耗时
            process_time = time.perf_counter() - start_time

            # 记录路由请求完成
            logger.info(
                "路由请求完成 | TraceID: %s | 路径: %s | 方法: %s | 状态码: %d | 耗时: %.3fms | 路由: %s",
                trace_id,
                route_info["path"],
                route_info["method"],
                response.status_code,
                process_time * 1000,
                route_info.get("route_name", "unknown"),
            )

            # 添加追踪相关的响应头
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Router-Process-Time"] = f"{process_time * 1000:.3f}"

            # 如果路由信息可用，添加到响应头
            if route_info.get("route_name"):
                response.headers["X-Route-Name"] = route_info["route_name"]

            return response

        except Exception as exc:
            # 记录路由层异常
            process_time = time.perf_counter() - start_time
            logger.exception(
                "路由请求异常 | TraceID: %s | 路径: %s | 方法: %s | 耗时: %.3fms | 路由: %s | 异常: %s",
                trace_id,
                route_info["path"],
                route_info["method"],
                process_time * 1000,
                route_info.get("route_name", "unknown"),
                str(exc)[:200],
            )
            raise


def register_router_tracing_middleware(
    app: FastAPI,
    skip_paths: Optional[list] = None,
    enable_trace_id: bool = True,
) -> None:
    """
    注册路由层追踪中间件到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
        skip_paths: 需要跳过追踪的路径列表（如健康检查接口）
        enable_trace_id: 是否自动生成追踪ID（如果请求头中没有）
    """
    app.add_middleware(
        RouterTracingMiddleware,
        skip_paths=skip_paths,
        enable_trace_id=enable_trace_id,
    )


__all__ = ["RouterTracingMiddleware", "register_router_tracing_middleware"]
