"""
请求处理工具函数

包含所有与请求处理相关的通用工具函数。
"""
import uuid
from typing import List

from ..common.models.chat_models import ChatRequest, MessageRole


def generate_request_id() -> str:
    """生成唯一的请求ID"""
    return uuid.uuid4().hex


def format_sse_event(event_type: str, data: str, request_id: str) -> str:
    """
    格式化SSE事件
    
    Args:
        event_type: 事件类型（message/error/end）
        data: 事件数据
        request_id: 请求ID
        
    Returns:
        str: 格式化后的SSE事件字符串
    """
    return f"id: {request_id}\nevent: {event_type}\ndata: {data}\n\n"


def extract_latest_question(chat_request: ChatRequest) -> str:
    """
    从聊天请求中提取最新的用户问题
    
    Args:
        chat_request: 聊天请求对象
        
    Returns:
        str: 最新的用户问题，如果找不到则返回空字符串
    """
    if chat_request.text:
        return chat_request.text.strip()

    def _from_messages(messages):
        for msg in reversed(messages):
            role = msg.role if isinstance(msg.role, str) else msg.role.value
            if role == MessageRole.USER.value:
                return msg.content.strip()
        return ""

    if chat_request.messages:
        question = _from_messages(chat_request.messages)
        if question:
            return question

    if chat_request.history:
        question = _from_messages(chat_request.history)
        if question:
            return question

    return ""

