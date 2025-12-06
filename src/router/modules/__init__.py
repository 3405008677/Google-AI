"""
公共模块

包含所有 AI 路由模块共享的工具函数和基类。

职责说明：
- base_chat_service: 定义服务基类（无业务逻辑，只有通用流程）
- logging_utils: 日志工具函数（无业务逻辑）
- request_utils: 请求处理工具函数（无业务逻辑）
"""

from .base_chat_service import (
    BaseChatService,
    MessagesBasedService,
    PromptBasedService,
)
from .logging_utils import init_access_logger, log_request_metadata
from .request_utils import extract_latest_question, format_sse_event, generate_request_id

__all__ = [
    "BaseChatService",
    "MessagesBasedService",
    "PromptBasedService",
    "init_access_logger",
    "log_request_metadata",
    "extract_latest_question",
    "format_sse_event",
    "generate_request_id",
]

