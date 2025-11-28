"""
共享数据模型

定义所有路由模块共享的 Pydantic 模型。
"""

from .chat_models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    MessageRole,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "MessageRole",
]

