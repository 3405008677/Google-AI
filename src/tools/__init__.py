"""
工具模组

提供各种可用的工具，包括：
1. Tavily 搜索 - 联网搜索最新信息
2. 时间日期工具 - 获取当前日期和时间
3. 其他工具（可扩展）

使用方式：
    from src.tools import get_tavily_search, search_web
    
    # 获取 Tavily 搜索工具
    search_tool = get_tavily_search()
    
    # 直接执行搜索
    results = await search_web("最新 AI 技术")
    
    # 获取当前时间
    from src.tools import get_current_datetime, get_datetime_tool
    time_info = get_current_datetime()
    
    # 使用工具对象（用于 LangChain）
    tool = get_datetime_tool()
    result = tool.invoke({"timezone": "Asia/Shanghai"})

工具注册机制：
    工具定义和配置已移至 src/common/function_calls/config.yaml
    使用 src/common/function_calls 模组来获取工具定义
"""

from src.tools.search import (
    TavilySearchTool,
    SearchResult,
    SearchResponse,
    get_tavily_search,
    search_web,
    is_tavily_configured,
)

from src.tools.datetime_tool import (
    DateTimeTool,
    DateTimeResponse,
    get_datetime_tool,
    get_current_datetime,
    get_current_datetime_simple,
)

__all__ = [
    # 搜索工具
    "TavilySearchTool",
    "SearchResult",
    "SearchResponse",
    "get_tavily_search",
    "search_web",
    "is_tavily_configured",
    # 时间日期工具
    "DateTimeTool",
    "DateTimeResponse",
    "get_datetime_tool",
    "get_current_datetime",
    "get_current_datetime_simple",
]

