"""
Google AI 聊天服务模块

继承自 PromptBasedService，实现 Gemini 特定的提示词组合逻辑。
"""

from ....modules.base_chat_service import PromptBasedService
from ..models.gemini_client import get_gemini_client


class ChatService(PromptBasedService):
    """
    Google AI 聊天服务类
    
    使用 PromptBasedService 基类，需要实现提示词组合逻辑。
    """

    def __init__(self):
        super().__init__("GoogleAI")
        self.gemini_client = get_gemini_client()

    def _compose_prompt(self, request) -> str:
        """
        组合完整的提示词（Gemini 特定实现）
        
        将 ChatRequest 转换为字符串提示词。
        """
        segments = []
        
        # 添加系统提示（如果存在）
        if request.system_prompt:
            segments.append(f"[System]\n{request.system_prompt.strip()}")
        
        # 添加历史消息
        for msg in request.history:
            role = msg.role.value.capitalize()
            segments.append(f"[{role}]\n{msg.content.strip()}")
        
        # 添加当前用户输入
        user_text = (request.text or "").strip()
        if not user_text:
            raise ValueError("Empty prompt")
        segments.append(f"[User]\n{user_text}")
        
        return "\n\n".join(segments)

    async def _call_client_generate(self, input_data: str) -> str:
        """调用 Gemini 客户端生成文本"""
        return self.gemini_client.generate_text(input_data)

    async def _call_client_stream(self, input_data: str):
        """流式调用 Gemini 客户端（返回同步生成器）"""
        return self.gemini_client.stream_text(input_data)
