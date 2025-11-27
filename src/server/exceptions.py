"""集中注册 FastAPI 的全局异常处理，保持主程序干净。"""

import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .logging_setup import logger


def _serialize_traceback(error_traceback: str) -> Dict[str, Any]:
    """序列化异常堆栈信息，转为列表格式方便前端逐行展示。"""
    # 过滤空行，避免前端展示多余空内容
    traceback_lines = [line.strip() for line in error_traceback.split("\n") if line.strip()]
    return {"traceback": traceback_lines}


def register_exception_handlers(app: FastAPI, config, custom_500_msg: Optional[str] = None) -> None:
    """
    为 FastAPI 应用注册全局异常处理器

    Args:
        app: FastAPI 应用实例
        config: 配置对象（需包含 debug 属性）
        custom_500_msg: 自定义 500 错误提示语（生产环境用）
    """

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理器：捕获所有未处理的异常"""
        error_msg = str(exc)
        error_traceback = traceback.format_exc()
        request_path = str(request.url.path)
        request_method = request.method

        # 日志记录：包含请求信息+完整堆栈，便于问题定位
        logger.error(
            "未处理的异常 - 路径: %s, 方法: %s, 错误信息: %s\n%s",
            request_path,
            request_method,
            error_msg,
            error_traceback,
        )

        # 调试模式：返回详细错误信息（含堆栈）
        if config.debug:
            response_content: Dict[str, Any] = {
                "detail": error_msg,
                "path": request_path,
                "method": request_method,
                **_serialize_traceback(error_traceback),
            }
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=response_content)

        # 生产模式：返回友好提示（支持自定义消息）
        default_msg = "内部服务器错误，请查看日志获取详细信息。"
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": custom_500_msg or default_msg}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求数据验证异常处理器：处理参数/请求体验证失败"""
        request_path = str(request.url.path)
        # 日志记录验证错误详情（包含字段、错误原因、位置）
        logger.warning("请求验证失败 - 路径: %s, 方法: %s, 错误详情: %s", request_path, request.method, exc.errors())

        # 标准化验证错误响应格式，包含字段、消息、位置信息
        formatted_errors = [
            {
                "field": ".".join(map(str, err["loc"])),  # 字段路径（如 body.name）
                "message": err["msg"],  # 错误提示
                "type": err["type"],  # 错误类型（如 value_error.str.regex）
            }
            for err in exc.errors()
        ]

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "请求参数验证失败", "errors": formatted_errors},
        )
