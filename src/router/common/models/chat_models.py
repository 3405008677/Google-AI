"""
聊天相关数据模型

定义与聊天功能相关的 Pydantic 模型，用于请求和响应数据的验证和序列化。
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """单条聊天消息模型"""
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求模型"""

    text: Optional[str] = Field(None, description="用户输入的提示词")
    system_prompt: Optional[str] = Field(None, description="系统提示，用于设定AI行为")
    history: List[ChatMessage] = Field(
        default_factory=list, description="对话历史记录（旧版字段）"
    )
    messages: Optional[List[ChatMessage]] = Field(
        default=None,
        description="OpenAI 兼容的消息数组。当存在时将覆盖 text/system/history 拼接逻辑。",
    )

    @model_validator(mode="after")
    def _validate_content(self) -> "ChatRequest":
        if self.text is not None:
            text = self.text.strip()
            self.text = text or None

        messages = self.messages or []

        if not messages and not self.text:
            raise ValueError("Either `text` or `messages` must be provided.")

        return self


class ChatResponse(BaseModel):
    """同步聊天响应模型"""
    request_id: str = Field(..., description="请求ID，用于追踪和日志记录")
    text: str = Field(..., description="AI生成的文本内容")
    latency_ms: int = Field(..., description="请求处理耗时（毫秒）")

