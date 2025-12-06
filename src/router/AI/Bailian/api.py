"""
阿里云百炼 API 路由

前缀: /Bailian
接口：
- POST /Bailian/chat         同步返回完整回复
- POST /Bailian/chat/stream  SSE 流式返回回复
- POST /Bailian/chat/terminate 终止聊天会话
"""
from fastapi import FastAPI

from ..base_router import BaseAIChatRouter
from .services.chat_service import BailianChatService


class BailianRouter(BaseAIChatRouter):
    """百炼路由类"""

    def __init__(self):
        super().__init__(
            service_name="Bailian",
            service_class=BailianChatService,
            enable_terminate=True,
            enable_access_log=True,
            log_filename="Bailian.log",
        )

    def get_chat_service(self) -> BailianChatService:
        """获取百炼聊天服务实例"""
        return BailianChatService()


# 创建路由实例
_bailian_router = BailianRouter()


def initBailian(app: FastAPI, prefix: str = ""):
    """初始化并注册百炼路由"""
    _bailian_router.init_router(app, prefix)


__all__ = ["initBailian"]

