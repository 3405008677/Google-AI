"""路由层限流中间件，专门处理请求频率限制，防止恶意刷接口。"""

import time
from collections import defaultdict, deque
from typing import Optional, List, Callable, Awaitable

from fastapi import FastAPI, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.server.logging_setup import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    路由层限流中间件

    专门用于路由层的请求频率限制，提供：
    1. 基于 IP 地址的请求频率限制
    2. 滑动窗口算法，精确控制请求频率
    3. 恶意请求直接返回 429，不耗费后续资源
    4. 支持配置跳过限流的路径（如健康检查接口）
    5. 自动清理过期的请求记录，避免内存泄漏
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        skip_paths: Optional[List[str]] = None,
        enable_rate_limit: bool = True,
    ):
        """
        初始化限流中间件

        Args:
            app: FastAPI 应用实例
            requests_per_minute: 每分钟允许的最大请求数（默认 60）
            requests_per_second: 每秒允许的最大请求数（默认 10）
            skip_paths: 需要跳过限流检查的路径列表（如健康检查接口、静态文件等）
            enable_rate_limit: 是否启用限流（默认 True）
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_second
        self.skip_paths = [path.rstrip("/") or "/" for path in (skip_paths or [])]
        self.enable_rate_limit = enable_rate_limit

        # 使用字典存储每个 IP 的请求时间戳队列
        # key: IP 地址, value: deque 存储请求时间戳
        self._request_history: dict[str, deque[float]] = defaultdict(lambda: deque())

        # 上次清理时间，用于定期清理过期记录
        self._last_cleanup_time = time.time()
        self._cleanup_interval = 300  # 每 5 分钟清理一次过期记录

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实 IP 地址

        优先检查 X-Forwarded-For 和 X-Real-IP 头（适用于反向代理场景）

        Args:
            request: 请求对象

        Returns:
            客户端 IP 地址
        """
        # 检查 X-Forwarded-For 头（可能包含多个 IP，取第一个）
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For 可能包含多个 IP，用逗号分隔，取第一个
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        # 检查 X-Real-IP 头
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # 回退到直接连接的客户端 IP
        if request.client:
            return request.client.host

        return "unknown"

    def _match_skip_path(self, path: str) -> bool:
        """
        检查路径是否应该跳过限流检查

        支持精确匹配和前缀匹配（形如 /public 或 /public/*）

        Args:
            path: 请求路径

        Returns:
            是否应该跳过限流检查
        """
        normalized_path = path.rstrip("/") or "/"
        for rule in self.skip_paths:
            # 显式精确匹配
            if normalized_path == rule:
                return True
            # 前缀匹配（将 /rule/* 视为 /rule 的子路径）
            if normalized_path.startswith(f"{rule}/"):
                return True
        return False

    def _cleanup_expired_records(self) -> None:
        """
        清理过期的请求记录，避免内存泄漏

        删除超过 1 分钟的请求时间戳记录
        """
        current_time = time.time()

        # 定期清理，避免频繁操作
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return

        self._last_cleanup_time = current_time
        cutoff_time = current_time - 60  # 保留最近 1 分钟的记录

        # 清理每个 IP 的过期记录
        ips_to_remove = []
        for ip, timestamps in self._request_history.items():
            # 移除超过 1 分钟的记录
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()

            # 如果该 IP 没有剩余记录，标记为删除
            if not timestamps:
                ips_to_remove.append(ip)

        # 删除没有记录的 IP
        for ip in ips_to_remove:
            del self._request_history[ip]

    def _check_rate_limit(self, ip: str) -> tuple[bool, Optional[str]]:
        """
        检查 IP 是否超过限流阈值

        使用滑动窗口算法：
        - 检查最近 1 秒内的请求数是否超过 requests_per_second
        - 检查最近 1 分钟内的请求数是否超过 requests_per_minute

        Args:
            ip: 客户端 IP 地址

        Returns:
            (是否允许, 错误信息)
        """
        current_time = time.time()
        timestamps = self._request_history[ip]

        # 清理该 IP 的过期记录（超过 1 分钟）
        cutoff_time_minute = current_time - 60
        while timestamps and timestamps[0] < cutoff_time_minute:
            timestamps.popleft()

        # 检查每分钟请求数限制
        if len(timestamps) >= self.requests_per_minute:
            return False, f"请求过于频繁：每分钟最多允许 {self.requests_per_minute} 次请求"

        # 清理该 IP 的过期记录（超过 1 秒）
        cutoff_time_second = current_time - 1
        recent_timestamps = [ts for ts in timestamps if ts >= cutoff_time_second]

        # 检查每秒请求数限制
        if len(recent_timestamps) >= self.requests_per_second:
            return False, f"请求过于频繁：每秒最多允许 {self.requests_per_second} 次请求"

        # 记录当前请求时间戳
        timestamps.append(current_time)

        return True, None

    def _rate_limit_exceeded_response(
        self,
        *,
        detail: str,
        code: str,
        request: Request,
        retry_after: Optional[int] = None,
    ) -> JSONResponse:
        """
        统一限流超限响应，返回 429 状态码

        Args:
            detail: 错误详情
            code: 错误代码
            request: 请求对象
            retry_after: 建议重试时间（秒），用于 Retry-After 响应头

        Returns:
            JSONResponse with 429 status code
        """
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": detail,
                "code": code,
                "path": str(request.url.path),
                "method": request.method,
            },
            headers=headers,
        )

    def _log_rate_limit_exceeded(self, msg: str, request: Request, ip: str) -> None:
        """
        记录限流超限日志

        Args:
            msg: 日志消息
            request: 请求对象
            ip: 客户端 IP 地址
        """
        logger.warning(
            "%s | 路径: %s | 方法: %s | 客户端IP: %s | User-Agent: %s",
            msg,
            request.url.path,
            request.method,
            ip,
            request.headers.get("user-agent", "unknown"),
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        处理请求并检查限流

        Args:
            request: 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            HTTP 响应
        """
        # 如果未启用限流，直接放行
        if not self.enable_rate_limit:
            return await call_next(request)

        # 检查是否需要跳过限流
        if self._match_skip_path(request.url.path):
            return await call_next(request)

        # 获取客户端 IP
        client_ip = self._get_client_ip(request)

        # 定期清理过期记录
        self._cleanup_expired_records()

        # 检查限流
        allowed, error_msg = self._check_rate_limit(client_ip)

        if not allowed:
            # 记录限流超限日志
            self._log_rate_limit_exceeded("限流拦截：请求频率超限", request, client_ip)

            # 直接返回 429，不继续处理后续逻辑，节省资源
            return self._rate_limit_exceeded_response(
                detail=error_msg or "请求频率超限，请稍后再试",
                code="rate_limit_exceeded",
                request=request,
                retry_after=60,  # 建议 60 秒后重试
            )

        # 限流检查通过，继续处理请求
        return await call_next(request)


def register_router_rate_limit_middleware(
    app: FastAPI,
    requests_per_minute: int = 60,
    requests_per_second: int = 10,
    skip_paths: Optional[List[str]] = None,
    enable_rate_limit: bool = True,
) -> None:
    """
    注册路由层限流中间件到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
        requests_per_minute: 每分钟允许的最大请求数（默认 60）
        requests_per_second: 每秒允许的最大请求数（默认 10）
        skip_paths: 需要跳过限流检查的路径列表（如健康检查接口、静态文件等）
        enable_rate_limit: 是否启用限流（默认 True）
    """
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=requests_per_minute,
        requests_per_second=requests_per_second,
        skip_paths=skip_paths,
        enable_rate_limit=enable_rate_limit,
    )


__all__ = ["RateLimitMiddleware", "register_router_rate_limit_middleware"]

