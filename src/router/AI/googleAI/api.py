"""
Google AI API 路由

前缀: /GoogleAI
接口：
- POST /GoogleAI/chat         同步返回完整回复
- POST /GoogleAI/chat/stream  SSE 流式返回回复
"""
from fastapi import FastAPI

from ..base_router import BaseAIChatRouter
from .services.chat_service import ChatService


class GoogleAIRouter(BaseAIChatRouter):
    """Google AI 路由类"""

    def __init__(self):
        super().__init__(
            service_name="GoogleAI",
            service_class=ChatService,
            enable_terminate=False,  # GoogleAI 不需要 terminate 端点
            enable_access_log=False,  # GoogleAI 不需要访问日志
        )

    def get_chat_service(self) -> ChatService:
        """获取 Google AI 聊天服务实例"""
        return ChatService()


# 创建路由实例
_google_ai_router = GoogleAIRouter()


def initGoogleAI(app: FastAPI, prefix: str = ""):
    """初始化并注册 Google AI 路由"""
    _google_ai_router.init_router(app, prefix)


__all__ = ["initGoogleAI"]

