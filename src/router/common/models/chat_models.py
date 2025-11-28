"""
聊天相关数据模型

定义与聊天功能相关的 Pydantic 模型，用于请求和响应数据的验证和序列化。
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


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
    text: str = Field(..., min_length=1, description="用户输入的提示词")
    system_prompt: Optional[str] = Field(None, description="系统提示，用于设定AI行为")
    history: List[ChatMessage] = Field(default_factory=list, description="对话历史记录")


class ChatResponse(BaseModel):
    """同步聊天响应模型"""
    request_id: str = Field(..., description="请求ID，用于追踪和日志记录")
    text: str = Field(..., description="AI生成的文本内容")
    latency_ms: int = Field(..., description="请求处理耗时（毫秒）")

