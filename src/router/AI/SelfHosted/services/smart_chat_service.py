"""
智能聊天服务

将 Orchestrator 集成到 SelfHosted 服务中，作为统一入口。
所有请求都会先经过意图判断，然后统一通过 SelfHosted 模型返回。
"""

from typing import AsyncGenerator

from ....common.models.chat_models import ChatRequest, ChatResponse
from ....modules.base_chat_service import BaseChatService
from ...Orchestrator.services.orchestrator_service import OrchestratorService


class SmartChatService(BaseChatService):
    """
    智能聊天服务类
    
    继承 BaseChatService 以保持接口兼容性，
    但实际使用 OrchestratorService 进行智能调度。
    所有请求都会先经过意图判断，然后统一通过 SelfHosted 模型返回。
    """

    def __init__(self):
        super().__init__("SelfHosted")
        self.orchestrator = OrchestratorService()

    def _prepare_input(self, request: ChatRequest):
        """
        准备输入数据
        
        这个方法不会被直接调用，因为我们会使用 orchestrator 的方法。
        但为了满足抽象基类的要求，需要实现它。
        """
        # 这个方法不会被使用，因为我们会重写 generate_response 和 stream_response
        # 返回一个占位符
        return []

    async def _call_client_generate(self, input_data) -> str:
        """
        这个方法不会被直接调用，因为我们会使用 orchestrator 的方法。
        """
        raise NotImplementedError("This method should not be called directly")

    async def _call_client_stream(self, input_data) -> AsyncGenerator[str, None]:
        """
        这个方法不会被直接调用，因为我们会使用 orchestrator 的方法。
        """
        raise NotImplementedError("This method should not be called directly")

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """
        重写基类方法，使用 Orchestrator 进行智能调度
        
        所有请求都会：
        1. 先经过意图判断
        2. 根据意图准备上下文（搜索/数据库）
        3. 统一通过 SelfHosted 模型处理
        """
        return await self.orchestrator.generate_response(request)

    async def stream_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        重写基类方法，使用 Orchestrator 进行智能调度（流式）
        """
        async for chunk in self.orchestrator.stream_response(request):
            yield chunk

