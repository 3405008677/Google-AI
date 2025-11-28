"""
工具函数模块

包含各种辅助函数，用于支持聊天功能。
"""
import logging
from typing import Any, Dict, Optional

def setup_logging(level: int = logging.INFO) -> None:
    """
    配置日志记录
    
    Args:
        level: 日志级别，默认为 INFO
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def validate_request(data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    验证请求数据
    
    Args:
        data: 要验证的请求数据
        
    Returns:
        Optional[Dict[str, str]]: 如果验证失败，返回错误信息；否则返回 None
    """
    if not data.get('text'):
        return {'error': 'Missing required field: text'}
    
    if not isinstance(data.get('text', ''), str):
        return {'error': 'Field "text" must be a string'}
        
    return None

def format_error_response(error: Exception) -> Dict[str, str]:
    """
    格式化错误响应
    
    Args:
        error: 异常对象
        
    Returns:
        Dict[str, str]: 格式化的错误响应
    """
    error_type = error.__class__.__name__
    return {
        'error': str(error),
        'type': error_type
    }
