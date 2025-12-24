"""
Function Call 降级方案实现

当模型不支持 Function Calling 时，使用这些降级方案来获取实时信息。
"""

from src.tools import get_datetime_tool
from src.server.logging_setup import logger


def get_current_datetime_fallback(timezone: str = "Asia/Shanghai") -> str:
    """
    直接获取当前时间信息（降级方案）
    
    当模型不支持 Function Calling 时，使用此方法直接获取时间信息
    并注入到系统提示词中。
    
    Args:
        timezone: 时区，默认为 "Asia/Shanghai"
        
    Returns:
        格式化的时间信息字符串，例如："今天是 2024年12月11日 星期四，现在时间是 14:30:25（Asia/Shanghai）"
    """
    try:
        # 创建新的工具实例，避免单例问题
        from src.tools.datetime_tool import DateTimeTool
        tool = DateTimeTool(timezone=timezone)
        response = tool.get_datetime(timezone)
        return f"今天是 {response.date} {response.weekday}，现在时间是 {response.time}（{response.timezone}）"
    except Exception as e:
        logger.error(f"获取时间信息失败: {e}", exc_info=True)
        # 如果获取失败，返回一个基本的提示
        return "无法获取当前时间信息"

