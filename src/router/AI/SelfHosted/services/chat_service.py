"""
自建模型聊天服务模块

继承自 MessagesBasedService，只需实现客户端调用逻辑。
"""

from typing import List, Dict

from ....modules.base_chat_service import MessagesBasedService
from ..models.self_hosted_client import get_self_hosted_client


class SelfHostedChatService(MessagesBasedService):
    """
    自建模型聊天服务类

    使用 MessagesBasedService 基类，自动处理消息数组的转换。
    只需要实现客户端调用方法。
    """

    def __init__(self):
        super().__init__("SelfHosted")
        self.client = get_self_hosted_client()

    async def _call_client_generate(self, input_data: List[Dict[str, str]]) -> str:
        """调用自建模型客户端生成文本"""
        return self.client.generate_text(input_data)

    async def _call_client_stream(self, input_data: List[Dict[str, str]]):
        """流式调用自建模型客户端（返回同步生成器）"""
        return self.client.stream_text(input_data)
