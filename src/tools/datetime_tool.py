"""
时间日期工具模组

提供获取当前日期和时间的功能，用于 Agent Function Calling。

使用方式：
    from src.tools.datetime_tool import get_current_datetime, DateTimeTool
    
    # 方式 1：直接调用
    result = get_current_datetime()
    
    # 方式 2：获取工具实例（用于 LangChain）
    tool = DateTimeTool()
    result = tool.invoke({})
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from src.server.logging_setup import logger


@dataclass
class DateTimeResponse:
    """时间日期响应"""
    date: str           # 2024年12月11日
    time: str           # 14:30:25
    weekday: str        # 星期四
    timezone: str       # Asia/Shanghai
    timestamp: float    # Unix 时间戳
    iso_format: str     # ISO 8601 格式
    
    def to_text(self) -> str:
        """转换为文本格式"""
        return (
            f"📅 当前时间信息：\n"
            f"- 日期：{self.date}\n"
            f"- 星期：{self.weekday}\n"
            f"- 时间：{self.time}\n"
            f"- 时区：{self.timezone}\n"
            f"- ISO 格式：{self.iso_format}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "date": self.date,
            "time": self.time,
            "weekday": self.weekday,
            "timezone": self.timezone,
            "timestamp": self.timestamp,
            "iso_format": self.iso_format,
        }


# 星期对照表
WEEKDAY_NAMES = {
    0: "星期一",
    1: "星期二",
    2: "星期三",
    3: "星期四",
    4: "星期五",
    5: "星期六",
    6: "星期日",
}


class DateTimeTool:
    """
    时间日期工具
    
    提供获取当前日期和时间的功能。
    支持 LangChain 工具调用格式。
    """
    
    def __init__(self, timezone: str = "Asia/Shanghai"):
        """
        初始化时间日期工具
        
        Args:
            timezone: 默认时区
        """
        self.default_timezone = timezone
    
    def get_datetime(self, timezone: Optional[str] = None) -> DateTimeResponse:
        """
        获取当前日期和时间
        
        Args:
            timezone: 时区（如 "Asia/Shanghai", "UTC"）
            
        Returns:
            DateTimeResponse 时间响应
        """
        tz_name = timezone or self.default_timezone
        
        try:
            # Python 3.9+ 使用 zoneinfo
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
        except ImportError:
            # 降级方案：使用本地时间
            logger.warning("zoneinfo 不可用，使用本地时间")
            now = datetime.now()
            tz_name = "Local"
        except Exception as e:
            logger.warning(f"无法解析时区 {tz_name}: {e}，使用本地时间")
            now = datetime.now()
            tz_name = "Local"
        
        logger.info(f"🕐 [DateTimeTool] 获取当前时间: {now.isoformat()}")
        
        return DateTimeResponse(
            date=now.strftime("%Y年%m月%d日"),
            time=now.strftime("%H:%M:%S"),
            weekday=WEEKDAY_NAMES.get(now.weekday(), now.strftime("%A")),
            timezone=tz_name,
            timestamp=now.timestamp(),
            iso_format=now.isoformat(),
        )
    
    # LangChain 兼容接口
    def invoke(self, input_data: Union[str, Dict[str, Any], None] = None) -> str:
        """
        LangChain 同步调用接口
        
        Args:
            input_data: 输入参数（可选）
            
        Returns:
            时间信息文本
        """
        timezone = None
        if isinstance(input_data, dict):
            timezone = input_data.get("timezone")
        
        response = self.get_datetime(timezone)
        return response.to_text()
    
    async def ainvoke(self, input_data: Union[str, Dict[str, Any], None] = None) -> str:
        """
        LangChain 异步调用接口
        
        Args:
            input_data: 输入参数（可选）
            
        Returns:
            时间信息文本
        """
        # 获取时间是同步操作，无需异步
        return self.invoke(input_data)
    
    def __repr__(self) -> str:
        return f"DateTimeTool(timezone={self.default_timezone})"


# === 全局实例和便捷函数 ===

_datetime_instance: Optional[DateTimeTool] = None


def get_datetime_tool(timezone: str = "Asia/Shanghai") -> DateTimeTool:
    """
    获取时间日期工具实例
    
    Args:
        timezone: 默认时区
        
    Returns:
        DateTimeTool 实例
    """
    global _datetime_instance
    
    if _datetime_instance is None:
        _datetime_instance = DateTimeTool(timezone=timezone)
    
    return _datetime_instance


def get_current_datetime(timezone: str = "Asia/Shanghai") -> str:
    """
    获取当前日期和时间（便捷函数）
    
    Args:
        timezone: 时区
        
    Returns:
        格式化的时间信息文本
        
    Examples:
        result = get_current_datetime()
        print(result)
        # 📅 当前时间信息：
        # - 日期：2024年12月11日
        # - 星期：星期四
        # - 时间：14:30:25
        # - 时区：Asia/Shanghai
        # - ISO 格式：2024-12-11T14:30:25+08:00
    """
    tool = DateTimeTool(timezone=timezone)
    return tool.invoke(None)


def get_current_datetime_simple(timezone: str = "Asia/Shanghai") -> str:
    """
    获取简单的日期时间字符串
    
    Args:
        timezone: 时区
        
    Returns:
        简单格式：2024年12月11日 星期四 14:30
    """
    tool = DateTimeTool(timezone=timezone)
    response = tool.get_datetime(timezone)
    return f"{response.date} {response.weekday} {response.time[:5]}"

