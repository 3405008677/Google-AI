"""
Function Call 降级方案模块

当模型不支持 Function Calling 时，提供降级方案来获取实时信息。
"""

from .fallback import get_current_datetime_fallback
from .fallback_manager import FallbackManager, get_fallback_manager

__all__ = [
    "get_current_datetime_fallback",
    "FallbackManager",
    "get_fallback_manager",
]

