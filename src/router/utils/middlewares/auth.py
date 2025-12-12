"""路由层安全认证中间件，专门处理请求的认证授权检查。"""

from typing import Optional, List, Callable, Awaitable

from fastapi import FastAPI, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.server.logging_setup import logger


class AuthMiddleware(BaseHTTPMiddleware):
    """
    路由层认证中间件

    专门用于路由层的安全认证检查，提供：
    1. 拦截所有请求，检查 Authorization 头
    2. 支持配置需要跳过的路径（如公开接口、健康检查等）
    3. 支持 Bearer Token 等多种认证方式
    4. 提供可扩展的认证验证逻辑
    """

    def __init__(
        self,
        app: ASGIApp,
        skip_paths: Optional[List[str]] = None,
        require_auth: bool = True,
    ):
        """
        初始化认证中间件

        Args:
            app: FastAPI 应用实例
            skip_paths: 需要跳过认证检查的路径列表（如健康检查接口、登录接口等）
            require_auth: 是否要求所有请求都必须包含 Authorization 头
        """
        super().__init__(app)
        # Normalize skip paths once to avoid repeated string work on every request
        self.skip_paths = [path.rstrip("/") or "/" for path in (skip_paths or [])]
        self.require_auth = require_auth

    def _extract_token(self, authorization: str) -> Optional[str]:
        """
        从 Authorization 头中提取 token

        支持格式：
        - Bearer <token>
        - <token>

        Args:
            authorization: Authorization 头的值

        Returns:
            提取的 token，如果格式不正确返回 None
        """
        if not authorization:
            return None

        authorization = authorization.strip()

        # 支持 Bearer Token 格式（大小写不敏感）
        bearer_prefix = "bearer "
        if authorization.lower().startswith(bearer_prefix):
            return authorization[len(bearer_prefix) :].strip() or None

        # 也支持直接传递 token
        return authorization if authorization else None

    def _validate_token(self, token: str) -> bool:
        """
        验证 token 是否有效

        这是一个基础实现，可以根据实际需求扩展：
        - JWT token 验证
        - 数据库查询验证
        - 外部认证服务验证等

        Args:
            token: 待验证的 token

        Returns:
            token 是否有效
        """
        # TODO: 实现实际的 token 验证逻辑
        # 目前只做基本的存在性检查，实际项目中应该验证 token 的有效性
        if not token or len(token.strip()) == 0:
            return False

        # 示例：这里可以添加 JWT 验证、数据库查询等逻辑
        # 例如：
        # try:
        #     decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        #     return True
        # except jwt.InvalidTokenError:
        #     return False

        return True

    def _match_skip_path(self, path: str) -> bool:
        """
        支持精确匹配和前缀匹配（形如 /public 或 /public/*）
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

    def _unauthorized_response(
        self,
        *,
        detail: str,
        code: str,
        request: Request,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> JSONResponse:
        """
        统一未授权响应，保证结构与日志一致
        """
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": detail,
                "code": code,
                "path": str(request.url.path),
                "method": request.method,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _log_auth_failure(self, msg: str, request: Request) -> None:
        logger.warning(
            "%s | 路径: %s | 方法: %s | 客户端: %s",
            msg,
            request.url.path,
            request.method,
            request.client.host if request.client else "unknown",
        )

    def _should_skip_auth(self, request: Request) -> bool:
        """
        判断是否应该跳过该请求的认证检查

        Args:
            request: 请求对象

        Returns:
            是否应该跳过认证检查
        """
        return self._match_skip_path(request.url.path)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> JSONResponse:
        """
        处理请求并检查认证

        Args:
            request: 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            HTTP 响应
        """
        # 检查是否需要跳过认证
        if self._should_skip_auth(request):
            return await call_next(request)

        # 如果不需要强制认证，直接放行
        if not self.require_auth:
            return await call_next(request)

        # 检查 Authorization 头是否存在
        authorization = request.headers.get("Authorization") or request.headers.get("authorization")

        if not authorization:
            self._log_auth_failure("认证失败：缺少 Authorization 头", request)
            return self._unauthorized_response(
                detail="缺少认证信息，请提供 Authorization 头",
                code="missing_authorization",
                request=request,
            )

        # 提取 token
        token = self._extract_token(authorization)
        if not token:
            self._log_auth_failure("认证失败：Authorization 头格式错误", request)
            return self._unauthorized_response(
                detail="Authorization 头格式错误，应使用 'Bearer <token>' 格式",
                code="invalid_authorization_format",
                request=request,
            )

        # 验证 token 有效性
        if not self._validate_token(token):
            self._log_auth_failure("认证失败：Token 无效", request)
            return self._unauthorized_response(
                detail="认证失败，Token 无效或已过期",
                code="invalid_token",
                request=request,
            )

        # 认证通过，将 token 信息存储到请求状态中，供后续处理使用
        request.state.auth_token = token

        # 继续处理请求
        return await call_next(request)


def register_router_auth_middleware(
    app: FastAPI,
    skip_paths: Optional[List[str]] = None,
    require_auth: bool = True,
) -> None:
    """
    注册路由层认证中间件到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
        skip_paths: 需要跳过认证检查的路径列表（如健康检查接口、登录接口等）
        require_auth: 是否要求所有请求都必须包含 Authorization 头
    """
    app.add_middleware(
        AuthMiddleware,
        skip_paths=skip_paths,
        require_auth=require_auth,
    )


__all__ = ["AuthMiddleware", "register_router_auth_middleware"]
