"""
自建模型 API 路由（集成智能调度）

前缀: /SelfHosted
接口：
- POST /SelfHosted/chat         同步返回完整回复（智能调度）
- POST /SelfHosted/chat/stream  SSE 流式返回回复（智能调度）
- POST /SelfHosted/chat/terminate 终止聊天会话

说明：
所有请求都会先经过智能调度系统（Orchestrator）判断意图：
- 如果是搜索意图：先调用 Tavily 搜索，然后将结果给 SelfHosted 处理
- 如果是数据库意图：先查询数据库，然后将结果给 SelfHosted 处理
- 如果是聊天意图：直接使用 SelfHosted 模型

所有结果最终都通过 SelfHosted 模型返回给用户。
"""
from fastapi import FastAPI

from ..base_router import BaseAIChatRouter
from .services.smart_chat_service import SmartChatService


class SelfHostedRouter(BaseAIChatRouter):
    """自建模型路由类（集成智能调度）"""

    def __init__(self):
        super().__init__(
            service_name="SelfHosted",
            service_class=SmartChatService,
            enable_terminate=True,
            enable_access_log=True,
            log_filename="SelfHosted.log",
        )

    def get_chat_service(self) -> SmartChatService:
        """获取智能聊天服务实例（集成调度功能）"""
        return SmartChatService()


# 创建路由实例
_self_hosted_router = SelfHostedRouter()


def initSelfHosted(app: FastAPI, prefix: str = ""):
    """初始化并注册自建模型路由"""
    _self_hosted_router.init_router(app, prefix)


__all__ = ["initSelfHosted"]

