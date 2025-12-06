"""
自建模型 API 路由

前缀: /SelfHosted
接口：
- POST /SelfHosted/chat         同步返回完整回复
- POST /SelfHosted/chat/stream  SSE 流式返回回复
- POST /SelfHosted/chat/terminate 终止聊天会话
"""
from fastapi import FastAPI

from ..base_router import BaseAIChatRouter
from .services.chat_service import SelfHostedChatService


class SelfHostedRouter(BaseAIChatRouter):
    """自建模型路由类"""

    def __init__(self):
        super().__init__(
            service_name="SelfHosted",
            service_class=SelfHostedChatService,
            enable_terminate=True,
            enable_access_log=True,
            log_filename="SelfHosted.log",
        )

    def get_chat_service(self) -> SelfHostedChatService:
        """获取自建模型聊天服务实例"""
        return SelfHostedChatService()


# 创建路由实例
_self_hosted_router = SelfHostedRouter()


def initSelfHosted(app: FastAPI, prefix: str = ""):
    """初始化并注册自建模型路由"""
    _self_hosted_router.init_router(app, prefix)


__all__ = ["initSelfHosted"]

