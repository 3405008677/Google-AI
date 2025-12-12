"""集中定义路由层的业务异常类型与全局处理器。"""

import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from src.server.logging_setup import logger


class RouterError(Exception):
    """路由业务异常基类，用于在路由层抛出可控的错误响应。"""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "router_error",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.code = code
        self.extra = extra or {}


def _serialize_traceback(error_traceback: str) -> Dict[str, Any]:
    """将异常堆栈序列化为列表，便于前端逐行展示。"""
    traceback_lines = [line.strip() for line in error_traceback.split("\n") if line.strip()]
    return {"traceback": traceback_lines}


def register_router_exception_handlers(app) -> None:
    """
    为 FastAPI 应用注册统一的异常处理器，确保路由层响应格式一致。
    
    Args:
        app: FastAPI 应用实例（不是 APIRouter）
    """

    @app.exception_handler(RouterError)
    async def router_error_handler(request: Request, exc: RouterError):
        """处理显式抛出的路由业务异常。"""
        request_path = str(request.url.path)
        logger.warning(
            "路由业务异常 - 路径: %s, 方法: %s, 代码: %s, 详情: %s",
            request_path,
            request.method,
            exc.code,
            exc.detail,
        )

        response_content: Dict[str, Any] = {
            "detail": exc.detail,
            "code": exc.code,
            "path": request_path,
            "method": request.method,
        }
        if exc.extra:
            response_content["extra"] = exc.extra

        return JSONResponse(status_code=exc.status_code, content=response_content)

    @app.exception_handler(Exception)
    async def router_unhandled_exception_handler(request: Request, exc: Exception):
        """兜底处理路由层未捕获的异常。"""
        request_path = str(request.url.path)
        request_method = request.method
        error_traceback = traceback.format_exc()

        logger.error(
            "路由未处理的异常 - 路径: %s, 方法: %s, 错误: %s\n%s",
            request_path,
            request_method,
            str(exc),
            error_traceback,
        )

        debug_mode = getattr(request.app, "debug", False)
        if debug_mode:
            response_content: Dict[str, Any] = {
                "detail": str(exc),
                "code": "router_internal_error",
                "path": request_path,
                "method": request_method,
                **_serialize_traceback(error_traceback),
            }
        else:
            response_content = {
                "detail": "路由内部错误，请稍后重试。",
                "code": "router_internal_error",
            }

        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=response_content)


__all__ = ["RouterError", "register_router_exception_handlers"]
