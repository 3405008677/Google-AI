"""
工具模組

提供各種可用的工具，包括：
1. Tavily 搜索 - 聯網搜索最新信息
2. 時間日期工具 - 獲取當前日期和時間
3. 其他工具（可擴展）

使用方式：
    from src.tools import get_tavily_search, search_web
    
    # 獲取 Tavily 搜索工具
    search_tool = get_tavily_search()
    
    # 直接執行搜索
    results = await search_web("最新 AI 技術")
    
    # 獲取當前時間
    from src.tools import get_current_datetime, get_datetime_tool
    time_info = get_current_datetime()
    
    # 使用工具對象（用於 LangChain）
    tool = get_datetime_tool()
    result = tool.invoke({"timezone": "Asia/Shanghai"})

工具註冊機制：
    工具定義和配置已移至 src/common/function_calls/config.yaml
    使用 src/common/function_calls 模組來獲取工具定義
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
    # 時間日期工具
    "DateTimeTool",
    "DateTimeResponse",
    "get_datetime_tool",
    "get_current_datetime",
    "get_current_datetime_simple",
]

