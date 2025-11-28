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
    if not data.get('text'):
        return 'Missing required field: text'
    
    if not isinstance(data.get('text', ''), str):
        return 'Field "text" must be a string'
        
    return None

