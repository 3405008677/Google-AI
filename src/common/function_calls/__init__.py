"""
統一 Function Call 工具管理模組

提供集中化的工具定義和管理，支持：
1. YAML 配置文件定義工具 Schema
2. 工具註冊和發現
3. LangChain 格式轉換
4. 工具執行器管理

使用方式：
    from src.common.function_calls import (
        get_tool,
        get_tools,
        get_tool_executor,
        register_tool,
    )
    
    # 獲取單個工具定義
    tool = get_tool("get_current_datetime")
    
    # 獲取多個工具定義
    tools = get_tools(["get_current_datetime", "web_search"])
    
    # 獲取工具執行器
    executor = get_tool_executor("get_current_datetime")
    result = await executor.ainvoke({"timezone": "Asia/Shanghai"})
    
    # 註冊自定義工具
    register_tool("my_tool", schema, executor)
"""

from src.common.function_calls.registry import (
    ToolRegistry,
    get_tool_registry,
    get_tool,
    get_tools,
    get_all_tools,
    get_worker_tools,
    list_tools,
    get_tools_for_langchain,
    get_tool_executor,
    register_tool,
    reload_tools,
)

__all__ = [
    "ToolRegistry",
    "get_tool_registry",
    "get_tool",
    "get_tools",
    "get_all_tools",
    "get_worker_tools",
    "list_tools",
    "get_tools_for_langchain",
    "get_tool_executor",
    "register_tool",
    "reload_tools",
]

