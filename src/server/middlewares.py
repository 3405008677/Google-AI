"""集中定义 FastAPI 中间件，方便在应用创建时统一挂载。"""

import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .logging_setup import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录每个进入的请求和返回的响应，包含请求耗时、客户端信息等关键数据，
    便于追踪请求流程和排查问题。
    """

    def __init__(self, app, skip_paths: Optional[list] = None):
        """
        初始化日志中间件

        Args:
            app: FastAPI 应用实例
            skip_paths: 需要跳过日志记录的路径列表（如健康检查接口）
        """
        super().__init__(app)
        self.skip_paths = skip_paths or []

    async def dispatch(self, request: Request, call_next) -> Response:
        # 跳过指定路径的日志记录
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # 获取请求的关键信息
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        request_id = request.headers.get("X-Request-ID", "unknown")

        # 记录请求开始信息
        logger.info(
            "请求开始 | ID: %s | 客户端: %s | 方法: %s | 路径: %s | UA: %s",
            request_id,
            client_ip,
            request.method,
            request.url.path,
            user_agent[:100],  # 限制UA长度，避免日志过长
        )

        start_time = time.perf_counter()

        try:
            # 处理请求
            response = await call_next(request)

            # 计算请求耗时
            process_time = time.perf_counter() - start_time

            # 记录响应信息
            logger.info(
                "请求完成 | ID: %s | 状态码: %d | 耗时: %.3fms | 方法: %s | 路径: %s",
                request_id,
                response.status_code,
                process_time * 1000,
                request.method,
                request.url.path,
            )

            # 添加响应头记录耗时
            response.headers["X-Process-Time"] = f"{process_time * 1000:.3f}"

            return response

        except Exception as exc:
            # 记录异常信息
            process_time = time.perf_counter() - start_time
            logger.exception(
                "请求异常 | ID: %s | 耗时: %.3fms | 方法: %s | 路径: %s | 异常: %s",
                request_id,
                process_time * 1000,
                request.method,
                request.url.path,
                str(exc)[:200],
            )
            raise
