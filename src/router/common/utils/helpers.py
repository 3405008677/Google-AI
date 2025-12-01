"""
工具函数模块

包含各种辅助函数，用于支持聊天功能。
"""
from typing import Any, Dict, Optional


def validate_request(data: Dict[str, Any]) -> Optional[str]:
    """
    验证请求数据
    
    Args:
        data: 要验证的请求数据
        
    Returns:
        Optional[str]: 如果验证失败，返回错误信息字符串；否则返回 None
    """
    text = data.get("text")
    messages = data.get("messages")

    if messages:
        if not isinstance(messages, list):
            return 'Field "messages" must be a list'
        for item in messages:
            if not isinstance(item, dict):
                return 'Each entry in "messages" must be an object'
            if "role" not in item or "content" not in item:
                return 'Each message must contain "role" and "content"'
            if not isinstance(item["content"], str) or not item["content"].strip():
                return 'Message "content" must be a non-empty string'
        return None

    if not text:
        return 'Missing required field: text'
    
    if not isinstance(text, str):
        return 'Field "text" must be a string'

    if not text.strip():
        return 'Field "text" cannot be blank'
        
    return None

